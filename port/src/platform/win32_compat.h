/* win32_compat.h — the small POSIX surface the port uses, on Windows.
 *
 * The engine was written against POSIX threads and SIGALRM. Windows has
 * neither, so this header maps the used subset onto Win32:
 *   - pthread mutex / condition variable / thread create-join-detach-exit
 *   - signal(SIGINT|SIGTERM|SIGALRM) + alarm() watchdog
 *   - unistd bits (usleep)
 * Only what the game actually calls is provided; this is not a pthreads port.
 */
#ifndef BENEFACTOR_WIN32_COMPAT_H
#define BENEFACTOR_WIN32_COMPAT_H

#ifdef _WIN32

#include <windows.h>
#include <process.h>
#include <stdint.h>
#include <stdlib.h>

/* ---- threads ---------------------------------------------------------- */
typedef HANDLE pthread_t;
typedef SRWLOCK pthread_mutex_t;
typedef CONDITION_VARIABLE pthread_cond_t;
typedef void *pthread_attr_t;

#define PTHREAD_MUTEX_INITIALIZER SRWLOCK_INIT
#define PTHREAD_COND_INITIALIZER  CONDITION_VARIABLE_INIT

static inline int pthread_mutex_init(pthread_mutex_t *m, const void *a) {
    (void)a; InitializeSRWLock(m); return 0;
}
static inline int pthread_mutex_destroy(pthread_mutex_t *m) { (void)m; return 0; }
static inline int pthread_mutex_lock(pthread_mutex_t *m) { AcquireSRWLockExclusive(m); return 0; }
static inline int pthread_mutex_unlock(pthread_mutex_t *m) { ReleaseSRWLockExclusive(m); return 0; }

static inline int pthread_cond_init(pthread_cond_t *c, const void *a) {
    (void)a; InitializeConditionVariable(c); return 0;
}
static inline int pthread_cond_destroy(pthread_cond_t *c) { (void)c; return 0; }
static inline int pthread_cond_broadcast(pthread_cond_t *c) {
    WakeAllConditionVariable(c); return 0;
}
static inline int pthread_cond_signal(pthread_cond_t *c) {
    WakeConditionVariable(c); return 0;
}
static inline int pthread_cond_wait(pthread_cond_t *c, pthread_mutex_t *m) {
    SleepConditionVariableSRW(c, m, INFINITE, 0);
    return 0;
}

typedef struct {
    void *(*fn)(void *);
    void  *arg;
} win32_thread_start_t;

static inline unsigned __stdcall win32_thread_trampoline(void *p) {
    win32_thread_start_t s = *(win32_thread_start_t *)p;
    free(p);
    s.fn(s.arg);
    return 0;
}

static inline int pthread_create(pthread_t *t, const void *attr,
                                 void *(*fn)(void *), void *arg) {
    (void)attr;
    win32_thread_start_t *s = (win32_thread_start_t *)malloc(sizeof *s);
    if (!s) return -1;
    s->fn = fn; s->arg = arg;
    uintptr_t h = _beginthreadex(NULL, 0, win32_thread_trampoline, s, 0, NULL);
    if (h == 0) { free(s); return -1; }
    *t = (HANDLE)h;
    return 0;
}
static inline int pthread_join(pthread_t t, void **ret) {
    WaitForSingleObject(t, INFINITE);
    CloseHandle(t);
    if (ret) *ret = NULL;
    return 0;
}
static inline int pthread_detach(pthread_t t) { CloseHandle(t); return 0; }
static inline void pthread_exit(void *ret) { (void)ret; ExitThread(0); }

/* ---- signals / alarm -------------------------------------------------- */
#ifndef SIGINT
#define SIGINT  2
#endif
#ifndef SIGTERM
#define SIGTERM 15
#endif
#ifndef SIGALRM
#define SIGALRM 14
#endif

typedef void (*benefactor_sighandler_t)(int);
benefactor_sighandler_t signal(int sig, benefactor_sighandler_t handler);
unsigned alarm(unsigned seconds);

/* ---- unistd ------------------------------------------------------------ */
static inline int usleep(unsigned usec) { Sleep(usec / 1000u); return 0; }

/* ---- sys/stat ---------------------------------------------------------- */
/* POSIX mkdir(path, mode); Win32 _mkdir(path) has no mode. */
#include <sys/stat.h>
#include <direct.h>
#ifndef BENEFACTOR_NO_MKDIR_SHIM
#define mkdir(path, mode) _mkdir(path)
#endif

#endif /* _WIN32 */
#endif /* BENEFACTOR_WIN32_COMPAT_H */
