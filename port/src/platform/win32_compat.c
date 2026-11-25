/* win32_compat.c — Win32 implementations of the POSIX bits in win32_compat.h. */
#include "platform/win32_compat.h"

#ifdef _WIN32

#include <stdio.h>
#include <stdlib.h>

/* The game only registers SIGINT/SIGTERM (shutdown) and SIGALRM (watchdog). */
#define BENEFACTOR_NSIG 32
static benefactor_sighandler_t s_handlers[BENEFACTOR_NSIG];

benefactor_sighandler_t signal(int sig, benefactor_sighandler_t handler)
{
    benefactor_sighandler_t old = NULL;
    if (sig <= 0 || sig >= BENEFACTOR_NSIG)
        return NULL;
    old = s_handlers[sig];
    s_handlers[sig] = handler;
    return old;
}

/* Watchdog: alarm(n) fires the SIGALRM handler on a helper thread after n
 * seconds unless disarmed first. A generation counter makes a disarmed timer a
 * no-op even if its thread already woke up. */
static volatile LONG s_alarm_gen = 0;

static unsigned __stdcall alarm_thread(void *unused)
{
    LONG gen = (LONG)(intptr_t)unused;
    /* Deliberately simple: the caller passes the deadline in ms via a global. */
    extern volatile LONG g_alarm_ms;
    DWORD ms = (DWORD)InterlockedCompareExchange(&g_alarm_ms, 0, 0);
    Sleep(ms);
    if (InterlockedCompareExchange(&s_alarm_gen, gen, gen) == gen) {
        benefactor_sighandler_t h = s_handlers[SIGALRM];
        if (h)
            h(SIGALRM);
    }
    return 0;
}

volatile LONG g_alarm_ms = 0;

unsigned alarm(unsigned seconds)
{
    /* cancel any pending watchdog, then arm a new one if requested */
    InterlockedIncrement(&s_alarm_gen);
    InterlockedExchange(&g_alarm_ms, (LONG)(seconds * 1000u));
    if (seconds > 0) {
        LONG gen = InterlockedCompareExchange(&s_alarm_gen, 0, 0);
        uintptr_t h = _beginthreadex(NULL, 0, alarm_thread, (void *)(intptr_t)gen, 0, NULL);
        if (h)
            CloseHandle((HANDLE)h);
    }
    return 0;
}

/* The HTTP debug server is a POSIX-socket development extra; not built on
 * Windows. main.c calls this unconditionally. */
void pc_http_debug_start(void)
{
}

#endif /* _WIN32 */
