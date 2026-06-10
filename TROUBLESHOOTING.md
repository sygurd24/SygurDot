# Error Log (Troubleshooting)

🌍 Languages: [English](TROUBLESHOOTING.md) | [Español](REGISTRO_DE_ERRORES.md)

This document records the most complex blocks encountered during the development of **SygurDot** and explains the definitive solutions implemented in the codebase, serving as a historical and technical guide.

---

## Incident: Complete Freeze and "X-shaped Mouse" after `startx` on ASUS VivoBook 15 (Tiger Lake + NVIDIA MX350, Kernel 6.12+)

### Symptom Description
1. When running `startx`, the system managed to show the Wallpaper and start Polybar. However, Polybar **did not update its modules** (staying empty on CPU, RAM, etc.) and the process consumed a huge CPU spike.
2. The mouse cursor transformed into a **giant "X" (crosshair)**, ignoring default themes, and furthermore **no keyboard shortcut (`sxhkd`) worked**, leaving the environment completely frozen.
3. Only vital sign: clicking and holding with the "X" over the empty screen and dragging a selection box caused Polybar to come back to life and update its clock **for a single second**, before refreezing.
4. All of this was accompanied by a previous history of severe kernel errors (`Timeout waiting for PHY ready`) when booting the laptop.

### Anatomy of the Problem (The Domino Effect)
Live investigation via SSH revealed that the failure was not one, but **three independent critical bugs operating at the same time**, each camouflaging the other:

#### 1. The "Windows BOM" Bug and the Screen Hijacker (ImageMagick)
* **The Cause:** The monitoring scripts created in Python (`system-monitor.py` and `bspwm-dynamic.py`) had been previously edited using a code editor on Windows. Windows saved these files quietly injecting a phantom encoding character at the beginning of the file: a **UTF-8 BOM (`\xef\xbb\xbf`)** and CRLF line endings.
* **The Effect:** Upon arriving in Linux, the kernel detected these phantom bytes and consequently considered the "Shebang" (`#!/usr/bin/env python3`) corrupt, refusing to execute the file using Python. Faced with the failure, the standard Linux terminal (`/bin/sh`) tried to process the file by force and read the main line of the Python code: `import sys`. Totally out of context, for Linux, **`import` is a binary tool from the `ImageMagick` utility**, whose sole function is to change the cursor to a crosshair shape (`X`) to capture the screen waiting for the user to draw a rectangle with the mouse. When drawing the box, Polybar unfroze but moved on to the next instruction `import subprocess`, repeating the process and "freezing" Xorg inputs infinitely.
* **The Solution:** The final stage of the installer (`install.sh`) was re-engineered. It now automatically submits the entire repository to a native surgical wash using an advanced `Perl` and `Sed` expression engine. All traces of BOM or CRLF imported from other systems are eliminated and destroyed from the raw clone **before** the binary takes execution rights.

#### 2. Internal KMS Deadlock (`nvidia-drm modeset=1`)
* **The Cause:** Attempting to optimize the solid hybrid architecture to support modern high-performance displays and laptops (e.g. HP Victus with NVIDIA RTX 4000/5000), the universal policy of injecting KMS hijacking into the Kernel was introduced in the installer: `options nvidia-drm modeset=1`.
* **The Effect:** On Intel Iris generation equipment (like the ASUS VivoBook), whose physical panel connector resides completely on the integrated graphics, this injection forced NVIDIA to usurp permissions in the background interrupting queries to the main graphics API (`DRM/KMS`). When utilities like `xrandr` or `bspwm` tried to query the monitors, the DRM channel generated a *deadlock* absolutely blocking X11 behind the scenes.
* **The Solution:** Real-time dynamic logic. Now the installer polls the computer's PCI ports and specifically identifies the conflicting Tiger Lake family (`9A49, 9A40...`). If detected, it forcefully rejects the KMS block correctly assuming a pure Software Offload native to NVIDIA, while taking care of it and continuing to deploy it optimally on computers like the HP Victus and contemporary architectures without generating bottlenecks.

#### 3. The Dual Kernel 6.12 Conflict (`xe` vs `i915`)
* **The Cause:** Starting with kernel 6.12+ (Debian Trixie), an attempt was made to experimentally force the use of a new module (`xe`) in parallel to the already functional classic Intel graphics module (`i915`) in Linux.
* **The Effect:** Running both simultaneously caused a "Kernel Panic" fighting to seize the `intel_tc_port_lock` (The internal logistics controller for Thunderbolt / Display ports). Attempting to solve this fight with rigid bootloader boot parameters in the past blindly blocked the screen's power channel (`i915.enable_dc=0`), causing terrifying direct physical disconnects due to *Timeout*.
* **The Solution:** Isolated aseptic intervention in `install.sh`. All aggressive mitigation on Linux GRUB power was abandoned. Of the only lock required and vital today, `install.sh` will conditionally take care of silently applying a blacklist (`blacklist xe`) exclusively upon noticing Intel graphics and architectures in this generation. No more, no less, ensuring a boot in harmony, where only one Module at a time claims control.

---

## Incident: Initialization Failure and Xorg Lockup with NVIDIA Blackwell (RTX 5050 Laptop) and Ryzen AI (Debian Trixie, Kernel 6.12+)

### Symptom Description
1. The user tried to open the `nvidia-settings` utility (NVIDIA X Server Settings) but it failed, hung, or did not detect the video card.
2. The general graphical environment lacked hardware acceleration or directly failed when trying to boot `startx`.
3. When inspecting via commands or SSH, the NVIDIA process (`nvidia-smi`) hung in an uninterruptible sleep state ("D state") and the kernel logs (`dmesg`) threw severe errors like `RmInitAdapter failed` and memory conflicts with the GPU firmware.

### Anatomy of the Problem (The Generational Clash)
This incident was the particular result of combining the newest AMD processor (Ryzen AI 5 340, Zen 5 architecture) together with the most recent NVIDIA graphics architecture (RTX 5050, Blackwell family) in a modern Linux environment. The problem was divided into three key structural failures:

#### 1. Obligation of "Open Kernel Modules" for Blackwell
* **The Cause:** Traditionally, Linux users install the closed/binary (proprietary) version of NVIDIA drivers. However, starting with the Blackwell architecture (5000 Series), NVIDIA outsourced almost all physical control of the card to the **GSP (GPU System Processor)**, a microprocessor integrated into the card itself. Classic closed modules fail by design when trying to communicate with this hardware. It is strictly mandatory to use NVIDIA's new open source modules ("Open Kernel Modules").
* **The Effect:** Manual installations or via standard driver repositories hung silently or generated crashes failing to initialize the card's own embedded system (GSP).

#### 2. IOMMU Memory Conflict with Ryzen AI (Strix/Kraken)
* **The Cause:** Even using the correct module, the new AMD processor architecture and the IOMMU memory bridge were intercepting and blocking the GPU's attempts to load its firmware into virtual memory, causing lethal `IO_PAGE_FAULT` and "Invalid state" alerts.
* **The Effect:** The GPU tried to boot its GSP firmware, the CPU blocked it for memory security, and left the card in a corrupt state known as "WPR2".

#### 3. Version Bugs in Driver 570 and Package Conflict
* **The Cause:** The initial version installed (570.86.16) contained known compatibility bugs with this Zen 5 variant. Furthermore, the presence of the `firmware-nvidia-gsp` package from the Debian repositories caused version clashes against the firmware embedded in the manual NVIDIA driver installation.

---

### The Solution and Step-by-Step Procedure

To eradicate this general block and bring the GPU back to life, a surgical installation of the drivers was orchestrated following these exact measures:

1. **Evade the IOMMU Memory Lock:**
   The boot manager (`/etc/default/grub`) was permanently modified, securing the parameter `amd_iommu=off` (or `iommu=pt`) within `GRUB_CMDLINE_LINUX_DEFAULT`. This took the handcuffs off the GPU allowing it to transact with its firmware freely during system boot.

2. **Purify the Environment and Clean the WPR2 State:**
   The native firmware package was deleted (`sudo apt purge firmware-nvidia-gsp`). Additionally, it was necessary to apply a **Hard-Reset (Held 15 seconds on the physical power button)** to the laptop. This is the only reliable way to drain the power and clean the "dirty" register of the WPR2 memory so the graphics card accepts clean commands on its next boot.

3. **Download and Forced Installation of the Open Module (v595.58.03):**
   Connected from TTY / SSH as `root`, hung processes were stopped and defective modules were unloaded from memory:
   ```bash
   modprobe -r nvidia_drm nvidia_modeset nvidia_uvm nvidia
   ```
   Next, the most advanced patch installation was run (`v595.58.03.run`). The vital secret of this step was to silently force DKMS to strictly compile the open modules:
   ```bash
   /tmp/nvidia_new.run --silent --dkms --kernel-module-type=open --no-questions
   ```

### Conclusion
After executing these steps, `nvidia-smi` lit up the terminal majestically recognizing the **RTX 5050 Laptop GPU**. The X Server (`startx`) was able to boot smoothly, finally enabling the `nvidia-settings` graphics panel with full control over the sensors and 3D performance of the equipment. This particular case establishes the protocol for treating "hybrid" computers of the newest generation.

---

## Incident: Screen Freezes and Window Loss on HP Victus (AMD Krackan + NVIDIA RTX 5050)

### Symptom Description
1. The screen froze suddenly during normal use. The visualization of the window content was lost or they seemed to "disappear", although the window manager frame (`bspwm`) was still visible.
2. The background system continued to operate (you could switch to a TTY), but the graphical environment was inoperable interacting with mouse or keyboard.
3. The only way to "unfreeze" the screen without losing the graphical environment was by performing a physical power cycle of the panel (closing and opening the laptop lid) or forcefully reloading the window manager (`Super + Alt + R`), which restarted the `picom` compositor.
4. The problem persisted regardless of the compositor backend (`xrender` vs `glx`) and even extreme synchronization options in Xorg (`TearFree`, `DRI 3`).

### Anatomy of the Problem (The Kernel Power Saving Failure)
The real problem was not in the window compositor (`picom`) or the Xorg configuration (the `/etc/X11/xorg.conf.d/10-hibrido.conf` file was correct and is strictly necessary in this hybrid architecture to direct rendering), but in a **Linux kernel bug with modern screen power management technologies in the new AMD iGPUs (Krackan / Radeon 800M Architecture)**.

The origin of the failure is a deep mismatch at the Direct Rendering Manager (DRM) level with two specific functions of the `amdgpu` driver:
* **Panel Self Refresh (PSR)**
* **Scatter/Gather (SG) Display**

These functions save battery by "sleeping" the physical connection between the AMD graphics and the laptop panel when the image on screen is static. The critical error in the Linux kernel occurred when the graphics tried to **"wake up" the screen** in time to process the redrawing of a window requested by the compositor (`picom`) or the window manager (`bspwm`).
When this awakening failed, the image buffer entered a *deadlock*, getting infinitely stuck waiting for a physical synchronization signal that never arrived, visually freezing the desktop.

### The Definitive Solution (Kernel-Level Patch)
Any attempt to force synchronization through Xorg (adding strict directives in `10-hibrido.conf`) or adjusting the repaint aggressiveness in `picom.conf` (like altering `use-damage`) is useless, since it attacks the symptom and not the disease.

The surgical solution implemented requires strictly deactivating these problematic screen power routines, passing direct boot parameters to the kernel through GRUB:

1. **Editing the Boot Manager (`/etc/default/grub`):**
   The `GRUB_CMDLINE_LINUX_DEFAULT` variable was modified to inject the following two key AMDGPU directives:
   * **`amdgpu.sg_display=0`**: Forcefully disables the use of Scatter/Gather Display, forcing the GPU to use memory directly and sequentially for screen buffers.
   * **`amdgpu.dcdebugmask=0x10`**: Instructs the AMD Display Core (DC) to bypass the use of Panel Self Refresh (PSR).

2. **Update and Cleanup:**
   The changes were applied to the system with `sudo update-grub`. To guarantee the cleanliness of the environment, all experimental alterations ("extreme synchronizations") made in files like `10-hibrido.conf` and `picom.conf` were removed, returning them to the original standard and safe system configuration. Upon reboot, the intermittent freezes and rendering *deadlock* disappeared completely.
