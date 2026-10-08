"""Read-only Windows input privilege preflight for the verified game process."""
import ctypes
from ctypes import wintypes


def process_is_elevated(process):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    advapi = ctypes.WinDLL('advapi32', use_last_error=True)
    advapi.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    advapi.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    token = wintypes.HANDLE()
    if not advapi.OpenProcessToken(process, 8, ctypes.byref(token)):
        raise PermissionError('无法检查游戏输入权限；请以管理员身份运行可可助手后重试')
    try:
        value, size = wintypes.DWORD(), wintypes.DWORD()
        if not advapi.GetTokenInformation(token, 20, ctypes.byref(value), ctypes.sizeof(value), ctypes.byref(size)):
            raise PermissionError('无法检查游戏输入权限；请以管理员身份运行可可助手后重试')
        return bool(value.value)
    finally:
        kernel.CloseHandle(token)


def require_matching_input_privilege(game_process):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    if process_is_elevated(game_process) and not process_is_elevated(kernel.GetCurrentProcess()):
        raise PermissionError('游戏以管理员权限运行，Windows 阻止普通权限鼠标输入；请关闭可可助手并以管理员身份运行，再切回装备背包重试')
