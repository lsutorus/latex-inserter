/* update_helper.c — Swap a running exe with a new version.
 * Usage: update_helper.exe --pid <PID> --src <new_exe> --dst <old_exe>
 * Compile: gcc -o update_helper.exe update_helper.c -lkernel32 -mwindows -Os -s
 */
#include <windows.h>
#include <stdio.h>
#include <string.h>

int main(int argc, char *argv[]) {
    DWORD pid = 0;
    const char *src = NULL;
    const char *dst = NULL;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--pid") == 0 && i + 1 < argc)
            pid = (DWORD)atoi(argv[++i]);
        else if (strcmp(argv[i], "--src") == 0 && i + 1 < argc)
            src = argv[++i];
        else if (strcmp(argv[i], "--dst") == 0 && i + 1 < argc)
            dst = argv[++i];
    }

    if (!pid || !src || !dst) {
        fprintf(stderr, "Usage: update_helper.exe --pid <PID> --src <new_exe> --dst <old_exe>\n");
        return 1;
    }

    /* Wait for main process to exit */
    HANDLE hProcess = OpenProcess(SYNCHRONIZE, FALSE, pid);
    if (hProcess) {
        WaitForSingleObject(hProcess, 30000);
        CloseHandle(hProcess);
    }
    Sleep(500); /* Grace period for file handles to close */

    /* Remove stale .bak if present */
    char bak_path[MAX_PATH];
    snprintf(bak_path, MAX_PATH, "%s.bak", dst);
    DeleteFileA(bak_path);

    /* Rename current exe to .bak (rollback point) */
    if (!MoveFileA(dst, bak_path)) {
        fprintf(stderr, "Failed to rename old exe: %lu\n", GetLastError());
        return 1;
    }

    /* Copy new exe into place */
    if (!CopyFileA(src, dst, FALSE)) {
        fprintf(stderr, "Failed to copy new exe: %lu\n", GetLastError());
        /* Rollback: restore from .bak */
        MoveFileA(bak_path, dst);
        return 1;
    }

    /* Relaunch the updated exe with elevation */
    ShellExecuteA(NULL, "runas", dst, NULL, NULL, SW_SHOWNORMAL);

    /* Clean up .bak and temp download */
    DeleteFileA(bak_path);
    char src_dir[MAX_PATH];
    snprintf(src_dir, MAX_PATH, "%s", src);
    char *last_slash = strrchr(src_dir, '\\');
    if (last_slash) {
        *last_slash = '\0';
        /* Best-effort: remove downloaded files from temp dir */
        DeleteFileA(src);
        RemoveDirectoryA(src_dir);
    }

    return 0;
}
