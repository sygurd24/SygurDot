#!/usr/bin/env python3
"""Hardened local IR facial recognition engine using InsightFace buffalo_sc ONNX models.

Security features:
- Direct Linux V4L2 mmap streaming on the dedicated IR sensor (/dev/video2)
- Strict ArcFace 512-dim matching: max similarity >= 0.55 AND top-3 mean >= 0.50
- 2-frame consensus (never trusts a single noisy frame)
- IR anti-spoofing heuristics: landmark geometry check, sharpness (Laplacian),
  glossy/specular glare rejection, and active IR face-vs-frame contrast check
"""

from __future__ import annotations

import fcntl
import mmap
import os
import select
import struct
import time
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np
import onnxruntime as ort

ort.set_default_logger_severity(3)

SYSTEM_OPT_DIR = Path("/opt/face-auth")
SYSTEM_DATA_DIR = Path("/var/lib/face-auth")
USER_DATA_DIR = Path.home() / ".local" / "share" / "face-auth"

MODELS_DIR = SYSTEM_OPT_DIR / "models" if (SYSTEM_OPT_DIR / "models").exists() else USER_DATA_DIR / "models"
EMBEDDINGS_PATH = SYSTEM_DATA_DIR / "embeddings.npz" if SYSTEM_DATA_DIR.exists() else USER_DATA_DIR / "embeddings.npz"
DEFAULT_DEVICE = os.environ.get("FACE_AUTH_DEVICE", "")


def detect_ir_device() -> str:
    """Auto-detect an 8-bit grayscale (GREY/Y800) V4L2 IR camera device."""
    if DEFAULT_DEVICE and Path(DEFAULT_DEVICE).exists():
        return DEFAULT_DEVICE

    candidates: list[tuple[int, str]] = []
    for dev_path in sorted(Path("/dev").glob("video*")):
        dev_str = str(dev_path)
        fd = -1
        try:
            fd = os.open(dev_str, os.O_RDWR | os.O_NONBLOCK)
            fmt = bytearray(208)
            struct.pack_into("<I", fmt, 0, _V4L2_BUF_TYPE_VIDEO_CAPTURE)
            fcntl.ioctl(fd, _VIDIOC_G_FMT, fmt)
            width, height, pixfmt = struct.unpack_from("<III", fmt, 8)
            fourcc = struct.pack("<I", pixfmt)
            if width > 0 and height > 0 and fourcc in (b"GREY", b"Y800", b"Y8  "):
                name_file = Path(f"/sys/class/video4linux/{dev_path.name}/name")
                name = name_file.read_text(errors="ignore").strip().lower() if name_file.exists() else ""
                priority = 0 if ("ir" in name or "infrared" in name or name.endswith(" i")) else 1
                candidates.append((priority, dev_str))
        except OSError:
            pass
        finally:
            if fd >= 0:
                try:
                    os.close(fd)
                except OSError:
                    pass

    if candidates:
        candidates.sort()
        return candidates[0][1]
    return "/dev/video2"

# Stricter security defaults (real user IR scores are ~0.70-0.85; strangers <0.25)
DEFAULT_THRESHOLD = 0.55
DEFAULT_TOP3_THRESHOLD = 0.50
DEFAULT_REQUIRED_MATCHES = 2
MIN_FACE_PX = 75.0

# V4L2 constants (Linux x86_64)
_V4L2_BUF_TYPE_VIDEO_CAPTURE = 1
_V4L2_MEMORY_MMAP = 1
_VIDIOC_G_FMT = 0xC0D05604
_VIDIOC_REQBUFS = 0xC0145608
_VIDIOC_QUERYBUF = 0xC0585609
_VIDIOC_QBUF = 0xC058560F
_VIDIOC_DQBUF = 0xC0585611
_VIDIOC_STREAMON = 0x40045612
_VIDIOC_STREAMOFF = 0x40045613

# Standard ArcFace 112x112 5-point alignment target landmarks
ARCFACE_DST = np.array(
    [
        [38.2946, 51.6963],
        [73.5318, 51.5014],
        [56.0252, 71.7366],
        [41.5493, 92.3655],
        [70.7299, 92.2041],
    ],
    dtype=np.float32,
)


def _nms(boxes: np.ndarray, scores: np.ndarray, iou_thresh: float = 0.4) -> list[int]:
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    areas = np.maximum(0.0, x2 - x1 + 1.0) * np.maximum(0.0, y2 - y1 + 1.0)
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size > 0:
        i = int(order[0])
        keep.append(i)
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        w = np.maximum(0.0, xx2 - xx1 + 1.0)
        h = np.maximum(0.0, yy2 - yy1 + 1.0)
        inter = w * h
        iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-6)
        order = order[np.where(iou <= iou_thresh)[0] + 1]
    return keep


class RawV4L2Camera:
    """Zero-overhead Linux V4L2 mmap reader for 8-bit grayscale IR cameras (Y800/GREY)."""

    def __init__(self, device: str = DEFAULT_DEVICE, num_buffers: int = 2) -> None:
        self.device = device
        self.num_buffers = num_buffers
        self.fd: int = -1
        self.bufs: list[tuple[mmap.mmap, int]] = []
        self.width: int = 640
        self.height: int = 360
        self.bytesperline: int = 640
        self.streaming: bool = False
        self._open()

    def _open(self) -> None:
        self.fd = os.open(self.device, os.O_RDWR)
        try:
            fmt = bytearray(208)
            struct.pack_into("<I", fmt, 0, _V4L2_BUF_TYPE_VIDEO_CAPTURE)
            fcntl.ioctl(self.fd, _VIDIOC_G_FMT, fmt)
            width, height, pixfmt, _field, bpl = struct.unpack_from("<IIIII", fmt, 8)
            if width > 0 and height > 0:
                self.width = width
                self.height = height
                self.bytesperline = bpl if bpl >= width else width
            fourcc = struct.pack("<I", pixfmt)
            if fourcc not in (b"GREY", b"Y800", b"Y8  "):
                raise ValueError(f"Unsupported raw IR pixelformat: {fourcc!r}")

            req = bytearray(20)
            struct.pack_into("<III", req, 0, self.num_buffers, _V4L2_BUF_TYPE_VIDEO_CAPTURE, _V4L2_MEMORY_MMAP)
            fcntl.ioctl(self.fd, _VIDIOC_REQBUFS, req)
            count = struct.unpack_from("<I", req, 0)[0]
            if count < 1:
                raise RuntimeError("V4L2 returned 0 buffers")

            for i in range(count):
                buf = bytearray(88)
                struct.pack_into("<II", buf, 0, i, _V4L2_BUF_TYPE_VIDEO_CAPTURE)
                struct.pack_into("<I", buf, 60, _V4L2_MEMORY_MMAP)
                fcntl.ioctl(self.fd, _VIDIOC_QUERYBUF, buf)
                length = struct.unpack_from("<I", buf, 72)[0]
                offset = struct.unpack_from("<I", buf, 64)[0]
                mm = mmap.mmap(self.fd, length, mmap.PROT_READ | mmap.PROT_WRITE, mmap.MAP_SHARED, offset=offset)
                self.bufs.append((mm, length))
                fcntl.ioctl(self.fd, _VIDIOC_QBUF, buf)

            btype = struct.pack("<I", _V4L2_BUF_TYPE_VIDEO_CAPTURE)
            fcntl.ioctl(self.fd, _VIDIOC_STREAMON, btype)
            self.streaming = True
        except Exception:
            self.release()
            raise

    def isOpened(self) -> bool:
        return self.fd >= 0 and self.streaming

    def read(self, timeout_sec: float = 1.5) -> Tuple[bool, Optional[np.ndarray]]:
        if not self.isOpened():
            return False, None
        r, _, _ = select.select([self.fd], [], [], timeout_sec)
        if not r:
            return False, None

        dq = bytearray(88)
        struct.pack_into("<I", dq, 4, _V4L2_BUF_TYPE_VIDEO_CAPTURE)
        struct.pack_into("<I", dq, 60, _V4L2_MEMORY_MMAP)
        try:
            fcntl.ioctl(self.fd, _VIDIOC_DQBUF, dq)
        except OSError:
            return False, None

        idx = struct.unpack_from("<I", dq, 0)[0]
        mm, _length = self.bufs[idx]
        expected = self.bytesperline * self.height
        raw = np.frombuffer(mm[:expected], dtype=np.uint8).reshape((self.height, self.bytesperline))
        frame = raw[:, : self.width].copy()

        try:
            fcntl.ioctl(self.fd, _VIDIOC_QBUF, dq)
        except OSError:
            pass
        return True, frame

    def release(self) -> None:
        if self.fd >= 0 and self.streaming:
            try:
                btype = struct.pack("<I", _V4L2_BUF_TYPE_VIDEO_CAPTURE)
                fcntl.ioctl(self.fd, _VIDIOC_STREAMOFF, btype)
            except OSError:
                pass
            self.streaming = False
        for mm, _ in self.bufs:
            try:
                mm.close()
            except Exception:
                pass
        self.bufs.clear()
        if self.fd >= 0:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = -1


def check_ir_liveness(gray: np.ndarray, box: np.ndarray, kps: np.ndarray) -> Tuple[bool, str]:
    """Validate IR face quality and anti-spoofing properties on a grayscale IR frame."""
    h_img, w_img = gray.shape[:2]
    x1 = max(0, int(box[0]))
    y1 = max(0, int(box[1]))
    x2 = min(w_img, int(box[2]))
    y2 = min(h_img, int(box[3]))
    fw = x2 - x1
    fh = y2 - y1
    if fw < MIN_FACE_PX or fh < MIN_FACE_PX:
        return False, "face_too_small"

    aspect = fw / float(max(fh, 1))
    if aspect < 0.50 or aspect > 1.25:
        return False, "bad_aspect"

    # 1. Landmark geometry sanity: eyes above nose above mouth, reasonable inter-ocular distance
    left_eye, right_eye, nose, left_mouth, right_mouth = kps
    eye_dist = float(np.linalg.norm(right_eye - left_eye))
    if eye_dist < fw * 0.22 or eye_dist > fw * 0.75:
        return False, "bad_eye_geometry"
    eye_mid_y = 0.5 * (left_eye[1] + right_eye[1])
    mouth_mid_y = 0.5 * (left_mouth[1] + right_mouth[1])
    if not (eye_mid_y < nose[1] < mouth_mid_y):
        return False, "bad_landmark_order"

    roi = gray[y1:y2, x1:x2]
    if roi.size == 0:
        return False, "empty_roi"

    # 2. Active IR illumination contrast: real face close to the IR emitter has
    #    meaningful dynamic range (rejects flat/washed-out photos and dark noise)
    roi_std = float(roi.std())
    roi_mean = float(roi.mean())
    if roi_mean < 12.0 or roi_std < 12.0:
        return False, "low_ir_contrast"

    # 3. Glossy glare / photo paper / blown-out white frame rejection
    #    Normal dark-room IR face sits around 10-15% >=250; >30% indicates glare or saturation.
    clipped_ratio = float(np.mean(roi >= 250))
    if clipped_ratio > 0.30:
        return False, "specular_glare"

    # 4. Focus / texture sharpness via Laplacian variance (rejects blurry printouts)
    lap_var = float(cv2.Laplacian(roi, cv2.CV_64F).var())
    if lap_var < 12.0:
        return False, "too_blurry"

    return True, "ok"


class FaceEngine:
    def __init__(
        self,
        det_model: Path = MODELS_DIR / "det_500m.onnx",
        rec_model: Path = MODELS_DIR / "w600k_mbf.onnx",
        det_size: Tuple[int, int] = (320, 320),
        num_threads: int = 4,
    ) -> None:
        self.det_size = det_size
        self._anchor_cache: dict[tuple[int, int, int], np.ndarray] = {}

        sess_opts = ort.SessionOptions()
        sess_opts.intra_op_num_threads = num_threads
        sess_opts.inter_op_num_threads = 1
        sess_opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        providers = ["CPUExecutionProvider"]
        self.det_sess = ort.InferenceSession(str(det_model), sess_options=sess_opts, providers=providers)
        self.rec_sess = ort.InferenceSession(str(rec_model), sess_options=sess_opts, providers=providers)
        self.det_input_name = self.det_sess.get_inputs()[0].name
        self.rec_input_name = self.rec_sess.get_inputs()[0].name

        # Warm up both sessions once so first real verify is instant
        dummy_det = np.zeros((1, 3, det_size[1], det_size[0]), dtype=np.float32)
        self.det_sess.run(None, {self.det_input_name: dummy_det})
        dummy_rec = np.zeros((1, 3, 112, 112), dtype=np.float32)
        self.rec_sess.run(None, {self.rec_input_name: dummy_rec})

    def _get_anchors(self, height: int, width: int, stride: int, num_anchors: int = 2) -> np.ndarray:
        key = (height, width, stride)
        cached = self._anchor_cache.get(key)
        if cached is not None:
            return cached
        centers = np.stack(np.mgrid[:height, :width][::-1], axis=-1).astype(np.float32)
        centers = (centers * stride).reshape((-1, 2))
        if num_anchors > 1:
            centers = np.stack([centers] * num_anchors, axis=1).reshape((-1, 2))
        self._anchor_cache[key] = centers
        return centers

    def detect_largest_face(
        self, frame_bgr: np.ndarray, score_thresh: float = 0.60, min_face_px: float = MIN_FACE_PX
    ) -> Optional[Tuple[np.ndarray, float, np.ndarray]]:
        """Return (bbox[4], score, kps[5,2]) for the largest valid face, or None."""
        orig_h, orig_w = frame_bgr.shape[:2]
        in_w, in_h = self.det_size
        im_ratio = orig_h / float(orig_w)
        model_ratio = in_h / float(in_w)
        if im_ratio > model_ratio:
            new_h = in_h
            new_w = int(new_h / im_ratio)
        else:
            new_w = in_w
            new_h = int(new_w * im_ratio)
        det_scale = float(new_h) / orig_h

        resized = cv2.resize(frame_bgr, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        det_img = np.zeros((in_h, in_w, 3), dtype=np.uint8)
        det_img[:new_h, :new_w, :] = resized

        blob = cv2.dnn.blobFromImage(
            det_img, 1.0 / 128.0, (in_w, in_h), (127.5, 127.5, 127.5), swapRB=True
        )
        outputs = self.det_sess.run(None, {self.det_input_name: blob})

        strides = (8, 16, 32)
        fmc = 3
        scores_list, bboxes_list, kps_list = [], [], []
        for idx, stride in enumerate(strides):
            scores = outputs[idx].reshape(-1)
            bbox_preds = outputs[idx + fmc].reshape((-1, 4)) * stride
            kps_preds = outputs[idx + fmc * 2].reshape((-1, 10)) * stride

            pos_inds = np.where(scores >= score_thresh)[0]
            if pos_inds.size == 0:
                continue

            feat_h = in_h // stride
            feat_w = in_w // stride
            anchors = self._get_anchors(feat_h, feat_w, stride, num_anchors=2)
            a = anchors[pos_inds]
            b = bbox_preds[pos_inds]
            k = kps_preds[pos_inds]

            x1 = a[:, 0] - b[:, 0]
            y1 = a[:, 1] - b[:, 1]
            x2 = a[:, 0] + b[:, 2]
            y2 = a[:, 1] + b[:, 3]
            boxes = np.stack([x1, y1, x2, y2], axis=-1) / det_scale

            kps = np.empty((pos_inds.size, 5, 2), dtype=np.float32)
            for p in range(5):
                kps[:, p, 0] = (a[:, 0] + k[:, p * 2]) / det_scale
                kps[:, p, 1] = (a[:, 1] + k[:, p * 2 + 1]) / det_scale

            scores_list.append(scores[pos_inds])
            bboxes_list.append(boxes)
            kps_list.append(kps)

        if not scores_list:
            return None

        all_scores = np.concatenate(scores_list, axis=0)
        all_boxes = np.concatenate(bboxes_list, axis=0)
        all_kps = np.concatenate(kps_list, axis=0)

        keep = _nms(all_boxes, all_scores, iou_thresh=0.4)
        best = None
        best_area = 0.0
        for i in keep:
            box = all_boxes[i]
            w = float(box[2] - box[0])
            h = float(box[3] - box[1])
            if w < min_face_px or h < min_face_px:
                continue
            area = w * h
            if area > best_area:
                best_area = area
                best = (box, float(all_scores[i]), all_kps[i])
        return best

    def get_embedding(self, frame_bgr: np.ndarray, kps: np.ndarray) -> np.ndarray:
        """Align face with 5 landmarks and return L2-normalized 512-dim ArcFace embedding."""
        m, _ = cv2.estimateAffinePartial2D(kps.astype(np.float32), ARCFACE_DST, method=cv2.LMEDS)
        if m is None:
            m = cv2.getAffineTransform(kps[:3].astype(np.float32), ARCFACE_DST[:3])
        aligned = cv2.warpAffine(frame_bgr, m, (112, 112), borderValue=0.0)

        blob = cv2.dnn.blobFromImage(
            aligned, 1.0 / 127.5, (112, 112), (127.5, 127.5, 127.5), swapRB=True
        )
        emb = self.rec_sess.run(None, {self.rec_input_name: blob})[0][0].astype(np.float32)
        norm = float(np.linalg.norm(emb))
        if norm > 0:
            emb /= norm
        return emb

    def extract_embedding(
        self, frame_bgr: np.ndarray, score_thresh: float = 0.60, check_liveness: bool = False
    ) -> Optional[Tuple[np.ndarray, float, np.ndarray, str]]:
        det = self.detect_largest_face(frame_bgr, score_thresh=score_thresh)
        if det is None:
            return None
        box, score, kps = det
        if check_liveness:
            gray = frame_bgr[:, :, 0]
            ok_live, live_reason = check_ir_liveness(gray, box, kps)
            if not ok_live:
                return None, score, box, live_reason  # type: ignore[return-value]
        emb = self.get_embedding(frame_bgr, kps)
        return emb, score, box, "ok"


def prepare_ir_frame(frame: np.ndarray) -> Optional[np.ndarray]:
    """Validate and convert an IR camera frame to 3-channel uint8 BGR."""
    if frame is None or frame.size == 0:
        return None
    if frame.ndim == 2:
        gray = frame
    elif frame.shape[2] == 1:
        gray = frame[:, :, 0]
    else:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    mean_val = float(gray.mean())
    std_val = float(gray.std())
    if mean_val < 5.0 or std_val < 5.0:
        return None

    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def open_ir_camera(device: Optional[str] = None):
    """Prefer zero-overhead raw V4L2 mmap reader; fall back to OpenCV if needed."""
    dev = device or detect_ir_device()
    try:
        return RawV4L2Camera(dev)
    except Exception:
        cap = cv2.VideoCapture(dev, cv2.CAP_V4L2)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return cap


def load_embeddings(path: Path = EMBEDDINGS_PATH) -> Optional[np.ndarray]:
    if not path.exists():
        return None
    data = np.load(str(path))
    embs = data["embeddings"].astype(np.float32)
    if embs.ndim == 1:
        embs = embs[None, :]
    norms = np.linalg.norm(embs, axis=1, keepdims=True)
    embs = embs / np.maximum(norms, 1e-6)
    return embs


def save_embeddings(embeddings: np.ndarray, path: Path = EMBEDDINGS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    tmp_path = path.with_suffix(".tmp.npz")
    np.savez(str(tmp_path), embeddings=embeddings.astype(np.float32))
    os.chmod(tmp_path, 0o600)
    os.replace(tmp_path, path)


def score_embedding(enrolled: np.ndarray, emb: np.ndarray) -> Tuple[float, float]:
    """Return (max_similarity, top3_mean_similarity) against enrolled embeddings."""
    sims = enrolled @ emb
    max_sim = float(np.max(sims))
    k = min(3, sims.shape[0])
    top_k = np.partition(sims, -k)[-k:]
    top3_mean = float(np.mean(top_k))
    return max_sim, top3_mean


def verify_live(
    engine: FaceEngine,
    enrolled: np.ndarray,
    device: Optional[str] = None,
    threshold: float = DEFAULT_THRESHOLD,
    top3_threshold: float = DEFAULT_TOP3_THRESHOLD,
    required_matches: int = DEFAULT_REQUIRED_MATCHES,
    timeout_sec: float = 1.8,
    max_warmup_timeout_sec: float = 5.5,
) -> Tuple[bool, float, int, str]:
    """Capture IR frames and require 2 agreeing frames passing liveness + ArcFace checks.

    If the Chicony IR sensor starts overexposed (e.g. right after hibernate/suspend or
    uncovering the lens), automatically extends the capture window up to
    max_warmup_timeout_sec so hardware auto-exposure can settle in a single attempt.
    """
    t0 = time.monotonic()
    cap = open_ir_camera(device)
    if not cap.isOpened():
        return False, 0.0, int((time.monotonic() - t0) * 1000), "camera_open_failed"

    best_score = 0.0
    matches = 0
    valid_frames = 0
    faces_seen = 0
    last_liveness_fail = ""
    saw_overexposed = False
    had_normal_exposure = False
    effective_timeout = timeout_sec
    try:
        while (time.monotonic() - t0) < effective_timeout:
            ok, raw = cap.read()
            if not ok or raw is None or raw.size == 0:
                time.sleep(0.005)
                continue

            raw_gray = raw if raw.ndim == 2 else (raw[:, :, 0] if raw.shape[2] == 1 else cv2.cvtColor(raw, cv2.COLOR_BGR2GRAY))
            raw_mean = float(raw_gray.mean())

            # Skip IR-OFF dark alternating frames
            if raw_mean < 5.0:
                continue

            raw_clip = float(np.mean(raw_gray >= 250))
            # Detect Chicony IR auto-exposure ramp (white-burned after hibernate/uncover, even when std < 5)
            if raw_mean >= 185.0 or raw_clip >= 0.40:
                saw_overexposed = True
                effective_timeout = max_warmup_timeout_sec
                if raw_clip >= 0.70:
                    matches = 0
                    continue

            frame_bgr = prepare_ir_frame(raw_gray)
            if frame_bgr is None:
                continue
            valid_frames += 1

            if raw_mean < 185.0 and raw_clip < 0.40:
                had_normal_exposure = True

            res = engine.extract_embedding(frame_bgr, score_thresh=0.60, check_liveness=True)
            if res is None:
                continue
            emb, _det_score, _box, live_reason = res
            if emb is None:
                last_liveness_fail = live_reason
                matches = 0
                continue

            faces_seen += 1
            max_sim, top3_mean = score_embedding(enrolled, emb)
            if max_sim > best_score:
                best_score = max_sim

            if max_sim >= threshold and top3_mean >= top3_threshold:
                matches += 1
                if matches >= required_matches:
                    elapsed_ms = int((time.monotonic() - t0) * 1000)
                    return True, best_score, elapsed_ms, "matched"
            else:
                matches = 0
    finally:
        cap.release()

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    if saw_overexposed and faces_seen == 0 and not had_normal_exposure:
        reason = "overexposed_warmup"
    elif valid_frames == 0:
        reason = "no_ir_frames"
    elif faces_seen == 0:
        reason = f"liveness_{last_liveness_fail}" if last_liveness_fail else "no_face"
    else:
        reason = "no_match"
    return False, best_score, elapsed_ms, reason
