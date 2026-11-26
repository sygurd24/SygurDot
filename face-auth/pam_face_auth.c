/*
 * Native Linux PAM module for hardened local IR facial verification (pam_face_auth.so).
 *
 * Security behavior:
 * - Retrieves PAM_AUTHTOK via pam_get_authtok() so i3lock supplies the typed
 *   password buffer and PAM caches it for pam_unix (try_first_pass).
 * - If a non-empty password was typed, returns PAM_IGNORE immediately (<0.05ms)
 *   without activating the IR camera.
 * - If empty password (Enter pressed in i3lock), connects to the root-owned
 *   system daemon socket /run/face-auth/face-auth.sock (verified root-owned dir),
 *   sends "VERIFY\n", and returns PAM_SUCCESS only on "OK".
 */

#define PAM_SM_AUTH
#include <pwd.h>
#include <security/pam_ext.h>
#include <security/pam_modules.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <sys/un.h>
#include <unistd.h>

#define SYSTEM_SOCK_DIR  "/run/face-auth"
#define SYSTEM_SOCK_PATH "/run/face-auth/face-auth.sock"

static int query_face_daemon(void) {
    /* Ensure socket directory is owned by root (anti-spoofing of socket path) */
    struct stat st;
    if (lstat(SYSTEM_SOCK_DIR, &st) != 0 || !S_ISDIR(st.st_mode) || st.st_uid != 0) {
        return PAM_IGNORE;
    }

    int fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (fd < 0) {
        return PAM_IGNORE;
    }

    struct timeval tv;
    tv.tv_sec = 4;
    tv.tv_usec = 0;
    setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
    setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv));

    struct sockaddr_un addr;
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    strncpy(addr.sun_path, SYSTEM_SOCK_PATH, sizeof(addr.sun_path) - 1);

    if (connect(fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        close(fd);
        return PAM_IGNORE;
    }

    const char *req = "VERIFY\n";
    if (write(fd, req, strlen(req)) != (ssize_t)strlen(req)) {
        close(fd);
        return PAM_IGNORE;
    }

    char resp[128];
    ssize_t r = read(fd, resp, sizeof(resp) - 1);
    close(fd);
    if (r <= 0) {
        return PAM_IGNORE;
    }
    resp[r] = '\0';

    if (strncmp(resp, "OK", 2) == 0 && (resp[2] == ' ' || resp[2] == '\n' || resp[2] == '\0')) {
        return PAM_SUCCESS;
    }
    return PAM_AUTH_ERR;
}

PAM_EXTERN int pam_sm_authenticate(pam_handle_t *pamh, int flags, int argc, const char **argv) {
    (void)flags;
    (void)argc;
    (void)argv;

    const char *user = NULL;
    if (pam_get_user(pamh, &user, NULL) != PAM_SUCCESS || user == NULL) {
        return PAM_IGNORE;
    }

    const char *authtok = NULL;
    int rc = pam_get_authtok(pamh, PAM_AUTHTOK, &authtok, NULL);
    if (rc != PAM_SUCCESS) {
        return PAM_IGNORE;
    }

    /* Non-empty password -> skip IR scan and let pam_unix verify it */
    if (authtok != NULL && authtok[0] != '\0') {
        return PAM_IGNORE;
    }

    return query_face_daemon();
}

PAM_EXTERN int pam_sm_setcred(pam_handle_t *pamh, int flags, int argc, const char **argv) {
    (void)pamh;
    (void)flags;
    (void)argc;
    (void)argv;
    return PAM_SUCCESS;
}
