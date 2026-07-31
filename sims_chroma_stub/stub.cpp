#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <windows.h>

#include <cctype>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <string>


static void log_line(const char* format, ...)
{
    char temp_path[MAX_PATH] = {};
    char log_path[MAX_PATH] = {};
    GetTempPathA(MAX_PATH, temp_path);
    snprintf(log_path, sizeof(log_path), "%sardor_chroma_stub.log", temp_path);

    FILE* file = nullptr;
    fopen_s(&file, log_path, "a");
    if (!file) {
        return;
    }

    SYSTEMTIME now = {};
    GetLocalTime(&now);
    fprintf(
        file,
        "%04u-%02u-%02u %02u:%02u:%02u.%03u ",
        now.wYear,
        now.wMonth,
        now.wDay,
        now.wHour,
        now.wMinute,
        now.wSecond,
        now.wMilliseconds
    );

    va_list args;
    va_start(args, format);
    vfprintf(file, format, args);
    va_end(args);

    fputc('\n', file);
    fclose(file);
}


static bool copy_maybe_string(const void* ptr, char* output, size_t output_size)
{
    if (!ptr) {
        return false;
    }

    __try {
        const unsigned char* bytes = static_cast<const unsigned char*>(ptr);
        if (bytes[0] != 0 && bytes[1] == 0) {
            const wchar_t* text = static_cast<const wchar_t*>(ptr);
            WideCharToMultiByte(
                CP_UTF8,
                0,
                text,
                -1,
                output,
                static_cast<int>(output_size),
                nullptr,
                nullptr
            );
            output[output_size - 1] = '\0';
            return true;
        }

        const char* text = static_cast<const char*>(ptr);
        strncpy_s(output, output_size, text, _TRUNCATE);
        return true;
    }
    __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}


static std::string read_maybe_string(const void* ptr)
{
    char buffer[512] = {};
    if (!copy_maybe_string(ptr, buffer, sizeof(buffer))) {
        return "";
    }
    return std::string(buffer);
}


static std::string lower_copy(std::string value)
{
    for (char& ch : value) {
        ch = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
    }
    return value;
}


static bool contains(const std::string& text, const char* needle)
{
    return text.find(needle) != std::string::npos;
}


static void choose_rgb(const std::string& event_name, int& red, int& green, int& blue)
{
    std::string name = lower_copy(event_name);

    red = 233;
    green = 233;
    blue = 233;

    if (name.find("blank") != std::string::npos || name.find("stop") != std::string::npos) {
        red = 0;
        green = 0;
        blue = 0;
    } else if (contains(name, "angry") || contains(name, "anger") || contains(name, "showeffect1")) {
        // Angry, #C3192B.
        red = 195;
        green = 25;
        blue = 43;
    } else if (contains(name, "uncomfortable")) {
        // Uncomfortable, #E26246.
        red = 226;
        green = 98;
        blue = 70;
    } else if (contains(name, "tense") || contains(name, "showeffect2")) {
        // Tense, #DF841C.
        red = 223;
        green = 132;
        blue = 28;
    } else if (contains(name, "embarrassed")) {
        // Embarrassed, #E1C043.
        red = 225;
        green = 192;
        blue = 67;
    } else if (contains(name, "energized")) {
        // Energized, #9DC948.
        red = 157;
        green = 201;
        blue = 72;
    } else if (contains(name, "happy") || contains(name, "idle")) {
        // Happy, #28B552.
        red = 40;
        green = 181;
        blue = 82;
    } else if (contains(name, "inspired") || contains(name, "showeffect4")) {
        // Inspired, #33BCC1.
        red = 51;
        green = 188;
        blue = 193;
    } else if (contains(name, "confident")) {
        // Confident, #448CC8.
        red = 68;
        green = 140;
        blue = 200;
    } else if (contains(name, "sad") || contains(name, "showeffect3")) {
        // Sad, #2C44AA.
        red = 44;
        green = 68;
        blue = 170;
    } else if (contains(name, "focused") || contains(name, "focus") || contains(name, "showeffect5")) {
        // Focused, #7038EC.
        red = 112;
        green = 56;
        blue = 236;
    } else if (contains(name, "dazed")) {
        // Dazed, #816DCC.
        red = 129;
        green = 109;
        blue = 204;
    } else if (contains(name, "playful")) {
        // Playful, #B646AD.
        red = 182;
        green = 70;
        blue = 173;
    } else if (contains(name, "flirty") || contains(name, "showeffect6")) {
        // Flirty, #EE5DA5.
        red = 238;
        green = 93;
        blue = 165;
    } else if (contains(name, "scared") || contains(name, "terrified")) {
        // Scared, #7E1260.
        red = 126;
        green = 18;
        blue = 96;
    } else if (contains(name, "bored")) {
        // Bored, #818785.
        red = 129;
        green = 135;
        blue = 133;
    } else if (contains(name, "asleep") || contains(name, "possessed") || contains(name, "recharge")) {
        // Asleep / Possessed / Recharge, #4D4D70.
        red = 77;
        green = 77;
        blue = 112;
    }
}


static bool send_http_get(const char* path)
{
    WSADATA wsa = {};
    if (WSAStartup(MAKEWORD(2, 2), &wsa) != 0) {
        return false;
    }

    SOCKET sock = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (sock == INVALID_SOCKET) {
        WSACleanup();
        return false;
    }

    DWORD timeout_ms = 250;
    setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, reinterpret_cast<const char*>(&timeout_ms), sizeof(timeout_ms));
    setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO, reinterpret_cast<const char*>(&timeout_ms), sizeof(timeout_ms));

    sockaddr_in addr = {};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(54235);
    addr.sin_addr.s_addr = htonl(0x7F000001);

    bool ok = false;
    if (connect(sock, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) == 0) {
        char request[768] = {};
        snprintf(
            request,
            sizeof(request),
            "GET %s HTTP/1.1\r\nHost: 127.0.0.1:54235\r\nConnection: close\r\n\r\n",
            path
        );
        ok = send(sock, request, static_cast<int>(strlen(request)), 0) != SOCKET_ERROR;
    }

    closesocket(sock);
    WSACleanup();
    return ok;
}


struct HttpEvent
{
    char path[256];
};


static DWORD WINAPI http_thread(LPVOID param)
{
    HttpEvent* event = static_cast<HttpEvent*>(param);
    bool ok = send_http_get(event->path);
    log_line("bridge GET %s -> %s", event->path, ok ? "ok" : "failed");
    delete event;
    return 0;
}


static void send_color_async(int red, int green, int blue)
{
    HttpEvent* event = new HttpEvent();
    snprintf(event->path, sizeof(event->path), "/test/rgb/%d/%d/%d", red, green, blue);

    HANDLE thread = CreateThread(nullptr, 0, http_thread, event, 0, nullptr);
    if (thread) {
        CloseHandle(thread);
    } else {
        delete event;
    }
}


static bool is_keyboard_animation(const std::string& event_name)
{
    return lower_copy(event_name).find("_keyboard") != std::string::npos;
}


static bool is_blank_animation(const std::string& event_name)
{
    return lower_copy(event_name).find("blank") != std::string::npos;
}


extern "C" BOOL WINAPI DllMain(HINSTANCE, DWORD reason, LPVOID)
{
    if (reason == DLL_PROCESS_ATTACH) {
        log_line("loaded");
    } else if (reason == DLL_PROCESS_DETACH) {
        log_line("unloaded");
    }
    return TRUE;
}


extern "C" int StubReturnZero()
{
    return 0;
}


extern "C" int StubReturnOne()
{
    return 1;
}


extern "C" int StubInit(...)
{
    log_line("init");
    return 0;
}


extern "C" int StubUninit(...)
{
    log_line("uninit");
    return 0;
}


extern "C" int StubStop(...)
{
    log_line("stop");
    return 0;
}


extern "C" int StubTrace(
    uintptr_t a1 = 0,
    uintptr_t a2 = 0,
    uintptr_t a3 = 0,
    uintptr_t a4 = 0,
    uintptr_t a5 = 0,
    uintptr_t a6 = 0,
    uintptr_t a7 = 0,
    uintptr_t a8 = 0
)
{
    std::string maybe_text = read_maybe_string(reinterpret_cast<const void*>(a1));
    if (!maybe_text.empty()) {
        log_line(
            "trace a1=%p text=%s a2=%llu a3=%llu a4=%llu a5=%llu a6=%llu a7=%llu a8=%llu",
            reinterpret_cast<void*>(a1),
            maybe_text.c_str(),
            static_cast<unsigned long long>(a2),
            static_cast<unsigned long long>(a3),
            static_cast<unsigned long long>(a4),
            static_cast<unsigned long long>(a5),
            static_cast<unsigned long long>(a6),
            static_cast<unsigned long long>(a7),
            static_cast<unsigned long long>(a8)
        );
    } else {
        log_line(
            "trace a1=%llu a2=%llu a3=%llu a4=%llu a5=%llu a6=%llu a7=%llu a8=%llu",
            static_cast<unsigned long long>(a1),
            static_cast<unsigned long long>(a2),
            static_cast<unsigned long long>(a3),
            static_cast<unsigned long long>(a4),
            static_cast<unsigned long long>(a5),
            static_cast<unsigned long long>(a6),
            static_cast<unsigned long long>(a7),
            static_cast<unsigned long long>(a8)
        );
    }
    return 0;
}


extern "C" int StubAnimationName(const void* name_ptr, ...)
{
    std::string name = read_maybe_string(name_ptr);
    if (name.empty()) {
        name = "<non-string>";
    }

    int red = 0;
    int green = 0;
    int blue = 0;
    choose_rgb(name, red, green, blue);

    if (is_keyboard_animation(name)) {
        log_line("animation %s -> RGB(%d,%d,%d)", name.c_str(), red, green, blue);
    }

    if (is_keyboard_animation(name) && !is_blank_animation(name)) {
        send_color_async(red, green, blue);
    }
    return 0;
}
