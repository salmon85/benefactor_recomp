/* test_input_bindings.c — regression test for game-controller binding parsing.
 *
 * Bug this pins: pad axis directions ending in '+' ("LeftX+", "LeftY+") were
 * split at the '+' that also separates chord keys, so RIGHT and DOWN could never
 * fire from the thumbstick while LEFT and UP (names ending in '-') worked.
 *
 * The config file is cached on first load, so the config phase runs in a fresh
 * child process (execv of this same binary with mode "config").
 *
 * Build & run (needs SDL2 headers; no SDL window is created):
 *   cc -I src -D_REENTRANT tools/test_input_bindings.c src/port/input.c \
 *      src/port/config.c $(sdl2-config --cflags --libs) -o /tmp/test_bindings
 *   /tmp/test_bindings
 */
#include "port/input.h"

#include <SDL2/SDL.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

static int s_fail;

#define CHECK(cond, ...) do { \
    if (!(cond)) { printf("FAIL: "); printf(__VA_ARGS__); printf("\n"); s_fail++; } \
    else         { printf("ok:   "); printf(__VA_ARGS__); printf("\n"); } \
} while (0)

static int axis(int a, int positive) { return PI_PAD_AXIS_CODE(a, positive); }
static void press(int code)  { pc_input_pad_button(code, 1); }
static void clear_pad(void)  { pc_input_pad_clear(); }

static void write_cfg(const char *path, const char *body)
{
    FILE *f = fopen(path, "wb");
    if (!f) { perror(path); exit(2); }
    fputs(body, f);
    fclose(f);
}

/* Phase 2: explicit JSON config (child process, BENEFACTOR_CONFIG already set). */
static int run_config_phase(void)
{
    pc_input_load();
    clear_pad();

    press(axis(SDL_CONTROLLER_AXIS_LEFTX, 1));
    CHECK(pc_input_active_dev(PI_DEV_PAD, PI_RIGHT), "configured 'DPRight, LeftX+' fires PI_RIGHT");
    clear_pad();
    press(SDL_CONTROLLER_BUTTON_DPAD_RIGHT);
    CHECK(pc_input_active_dev(PI_DEV_PAD, PI_RIGHT), "configured d-pad right fires PI_RIGHT");
    clear_pad();
    press(axis(SDL_CONTROLLER_AXIS_LEFTY, 1));
    CHECK(pc_input_active_dev(PI_DEV_PAD, PI_DOWN), "configured 'DPDown, LeftY+' fires PI_DOWN");
    clear_pad();

    /* Keyboard chords must still split on '+' (the sign fold is pad-only). */
    pc_input_key(SDLK_LCTRL, 1);
    CHECK(!pc_input_active_dev(PI_DEV_KB, PI_FIRE), "Ctrl alone does not fire FIRE (chord needs Space)");
    pc_input_key(SDLK_SPACE, 1);
    CHECK(pc_input_active_dev(PI_DEV_KB, PI_FIRE), "Ctrl+Space chord fires FIRE");
    pc_input_key(SDLK_SPACE, 0);
    pc_input_key(SDLK_LCTRL, 0);

    char buf[128];
    pc_input_binding_str(PI_DEV_PAD, PI_RIGHT, buf, sizeof buf);
    printf("pad_right renders as \"%s\"\n", buf);
    CHECK(strstr(buf, "LeftX+") != NULL, "pad_right display keeps the '+' direction");

    printf(s_fail ? "FAILED (%d)\n" : "PASS input bindings (config phase)\n", s_fail);
    return s_fail ? 1 : 0;
}

int main(int argc, char **argv)
{
    if (argc > 1 && !strcmp(argv[1], "config"))
        return run_config_phase();

    /* Phase 1: built-in defaults, no config file at all. This is the exact
     * reported failure: right/down must work from the thumbstick.
     * Run from an empty directory so the default "benefactor.json" is absent. */
    char tmpdir[] = "/tmp/benefactor-bindings-XXXXXX";
    if (!mkdtemp(tmpdir)) { perror("mkdtemp"); return 2; }
    if (chdir(tmpdir) != 0) { perror("chdir"); return 2; }
    unsetenv("BENEFACTOR_CONFIG");
    pc_input_load();
    clear_pad();

    press(axis(SDL_CONTROLLER_AXIS_LEFTX, 1));
    CHECK(pc_input_active_dev(PI_DEV_PAD, PI_RIGHT), "default stick right fires PI_RIGHT (LeftX+)");
    CHECK(!pc_input_active_dev(PI_DEV_PAD, PI_LEFT), "stick right does not fire PI_LEFT");
    clear_pad();

    press(axis(SDL_CONTROLLER_AXIS_LEFTY, 1));
    CHECK(pc_input_active_dev(PI_DEV_PAD, PI_DOWN), "default stick down fires PI_DOWN (LeftY+)");
    CHECK(!pc_input_active_dev(PI_DEV_PAD, PI_UP), "stick down does not fire PI_UP");
    clear_pad();

    press(axis(SDL_CONTROLLER_AXIS_LEFTX, 0));
    CHECK(pc_input_active_dev(PI_DEV_PAD, PI_LEFT), "stick left still fires PI_LEFT (LeftX-)");
    clear_pad();

    press(axis(SDL_CONTROLLER_AXIS_LEFTY, 0));
    CHECK(pc_input_active_dev(PI_DEV_PAD, PI_UP), "stick up still fires PI_UP (LeftY-)");
    clear_pad();

    /* Phase 2 in a child process so config.c reads the test file fresh. */
    const char *cfg = "test-bindings.json";
    write_cfg(cfg,
        "{\n"
        "  \"pad_right\": \"DPRight, LeftX+\",\n"
        "  \"pad_left\": \"DPLeft, LeftX-\",\n"
        "  \"pad_up\": \"DPUp, LeftY-\",\n"
        "  \"pad_down\": \"DPDown, LeftY+\",\n"
        "  \"pad_fire\": \"A, RightTrigger\",\n"
        "  \"bind_fire\": \"Z, LCtrl+Space\"\n"
        "}\n");
    setenv("BENEFACTOR_CONFIG", cfg, 1);
    fflush(NULL);
    pid_t pid = fork();
    if (pid == 0) {
        char *args[] = { argv[0], "config", NULL };
        execv(argv[0], args);
        _exit(127);
    }
    int status = 0;
    waitpid(pid, &status, 0);
    remove(cfg);
    if (!WIFEXITED(status) || WEXITSTATUS(status) != 0)
        s_fail++;
    rmdir(tmpdir);

    printf(s_fail ? "FAILED (%d)\n" : "PASS input bindings\n", s_fail);
    return s_fail ? 1 : 0;
}
