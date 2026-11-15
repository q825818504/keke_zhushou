#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>

namespace {
HMODULE module_instance{};
void WriteCallbackLog() {
    wchar_t path[32768]{};
    const DWORD length=GetModuleFileNameW(module_instance,path,static_cast<DWORD>(sizeof(path)/sizeof(path[0])));
    if (!length || length>=sizeof(path)/sizeof(path[0])) return;
    DWORD separator=length;
    while (separator && path[separator-1]!=L'\\' && path[separator-1]!=L'/') --separator;
    if (!separator || separator+32>=sizeof(path)/sizeof(path[0])) return;
    DWORD cursor=separator;
    const wchar_t prefix[]=L"bridge-";
    for (DWORD i=0;prefix[i];++i) path[cursor++]=prefix[i];
    DWORD pid=GetCurrentProcessId(); wchar_t digits[16]{}; DWORD count=0;
    do { digits[count++]=static_cast<wchar_t>(L'0'+pid%10); pid/=10; } while (pid && count<16);
    while (count) path[cursor++]=digits[--count];
    const wchar_t suffix[]=L".log";
    for (DWORD i=0;suffix[i];++i) path[cursor++]=suffix[i];
    path[cursor]=L'\0';
    HANDLE file=CreateFileW(path,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,
                            nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
    if (file!=INVALID_HANDLE_VALUE) {
        static constexpr char line[]="minimal hook callback entered\r\n";
        DWORD written{}; WriteFile(file,line,static_cast<DWORD>(sizeof(line)-1),&written,nullptr);
        CloseHandle(file);
    }
}
}

BOOL WINAPI DllMain(HINSTANCE instance,DWORD reason,LPVOID) {
    if (reason==DLL_PROCESS_ATTACH) module_instance=instance;
    return TRUE;
}

extern "C" __declspec(dllexport) LRESULT CALLBACK KekeBridgeHook(int code,WPARAM wparam,LPARAM lparam) {
    if (code>=0) WriteCallbackLog();
    return CallNextHookEx(nullptr,code,wparam,lparam);
}
