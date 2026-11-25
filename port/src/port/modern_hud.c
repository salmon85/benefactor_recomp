/* pc_modern_hud.c — optional vector HUD in the widescreen side margin.
 *
 * This is original PC-side artwork, not replacement game art. It deliberately
 * lives outside the 352px playfield and registers a light overlay rect so the
 * Vulkan per-sprite path can keep rendering the world underneath it.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "common/game_state.h"
#include "engine/rt.h"
#include "port/config.h"
#include "port/port.h"
#include "port/modern_hud.h"

#define FB_W 352
#define PANEL_W 56
#define PANEL_H 136
#define PANEL_Y 64

extern int pc_overlay_w(void);
extern int pc_overlay_h(void);
extern int pc_draw_text(uint32_t *fb, int x, int y, const char *s, int scale, uint32_t argb);
extern void hw_overlay_rect(int x, int y, int w, int h);

static void blend_pixel(uint32_t *fb, int w, int h, int x, int y,
                        uint32_t r, uint32_t g, uint32_t b, uint32_t a)
{
    if (x < 0 || x >= w || y < 0 || y >= h) return;
    uint32_t *dst = &fb[(size_t)y * w + x];
    uint32_t dr = (*dst >> 16) & 0xFFu;
    uint32_t dg = (*dst >> 8) & 0xFFu;
    uint32_t db = *dst & 0xFFu;
    uint32_t nr = (dr * (255u - a) + r * a + 127u) / 255u;
    uint32_t ng = (dg * (255u - a) + g * a + 127u) / 255u;
    uint32_t nb = (db * (255u - a) + b * a + 127u) / 255u;
    *dst = 0xFF000000u | (nr << 16) | (ng << 8) | nb;
}

static int rounded_inside(int x, int y, int w, int h, int r)
{
    if (x < 0 || x >= w || y < 0 || y >= h) return 0;
    int cx = x < r ? r : (x >= w - r ? w - r - 1 : x);
    int cy = y < r ? r : (y >= h - r ? h - r - 1 : y);
    int dx = x - cx, dy = y - cy;
    return dx * dx + dy * dy <= r * r;
}

static void panel_rect(uint32_t *fb, int w, int h, int px, int py)
{
    for (int y = 0; y < PANEL_H; y++) {
        for (int x = 0; x < PANEL_W; x++) {
            if (!rounded_inside(x, y, PANEL_W, PANEL_H, 7)) continue;
            uint32_t shade = (uint32_t)(18u + (uint32_t)y * 10u / PANEL_H);
            blend_pixel(fb, w, h, px + x, py + y, 8, 14, shade, 218u);
        }
    }
    for (int y = 0; y < PANEL_H; y++) {
        for (int x = 0; x < PANEL_W; x++) {
            if (!rounded_inside(x, y, PANEL_W, PANEL_H, 7)) continue;
            int edge = x == 0 || y == 0 || x == PANEL_W - 1 || y == PANEL_H - 1;
            if (!edge) continue;
            blend_pixel(fb, w, h, px + x, py + y, 76, 196, 226, 235u);
        }
    }
}

static void hex_icon(uint32_t *fb, int w, int h, int cx, int cy)
{
    for (int y = -8; y <= 8; y++) {
        for (int x = -8; x <= 8; x++) {
            int ax = x < 0 ? -x : x;
            int ay = y < 0 ? -y : y;
            if (ax > 7 || ay > 8 || ax + ay > 11) continue;
            blend_pixel(fb, w, h, cx + x, cy + y, 83, 215, 238, 255u);
        }
    }
    for (int y = -3; y <= 3; y++)
        for (int x = -3; x <= 3; x++)
            if (abs(x) + abs(y) <= 3)
                blend_pixel(fb, w, h, cx + x, cy + y, 10, 20, 31, 255u);
}

static void centered_text(uint32_t *fb, int cx, int y, const char *text,
                          int scale, uint32_t argb)
{
    int width = (int)strlen(text) * 6 * scale;
    pc_draw_text(fb, cx - width / 2, y, text, scale, argb);
}

int pc_modern_hud_active(void)
{
    return pc_cfg_bool("modern_hud", 0) && g_gameplay_active &&
           pc_overlay_w() >= FB_W + 96;
}

void pc_modern_hud_overlay(uint32_t *fb)
{
    if (!pc_modern_hud_active()) return;
    int ow = pc_overlay_w(), oh = pc_overlay_h();
    int margin = (ow - FB_W) / 2;
    int panel_w = margin - 16;
    if (panel_w < 48 || oh < PANEL_Y + PANEL_H + 8) return;
    if (panel_w > PANEL_W) panel_w = PANEL_W;
    int px = ow - margin + 8;
    if (px + panel_w > ow - 4) px = ow - panel_w - 4;

    panel_rect(fb, ow, oh, px, PANEL_Y);
    hex_icon(fb, ow, oh, px + panel_w / 2, PANEL_Y + 17);

    int level = g_mem ? (((int)g_mem[0x20] << 8) | g_mem[0x21]) : 1;
    if (level < 1 || level > PC_NUM_LEVELS) level = 1;
    int world = 0, liw = 0;
    pc_level_split(level, &world, &liw);

    char value[16];
    snprintf(value, sizeof value, "%02d", world + 1);
    centered_text(fb, px + panel_w / 2, PANEL_Y + 31, "WORLD", 1, 0xFF9FC4D4u);
    centered_text(fb, px + panel_w / 2, PANEL_Y + 41, value, 2, 0xFFEAF7FFu);

    for (int x = 7; x < panel_w - 7; x++)
        blend_pixel(fb, ow, oh, px + x, PANEL_Y + 61, 76, 196, 226, 110u);

    snprintf(value, sizeof value, "%02d", level);
    centered_text(fb, px + panel_w / 2, PANEL_Y + 69, "LEVEL", 1, 0xFF9FC4D4u);
    centered_text(fb, px + panel_w / 2, PANEL_Y + 79, value, 2, 0xFFEAF7FFu);

    int count = pc_levels_in_world(world);
    int gap = 1, seg_w = (panel_w - 14 - (count - 1) * gap) / count;
    if (seg_w < 1) seg_w = 1;
    int sx = px + 7;
    for (int i = 0; i < count; i++) {
        uint32_t r = i <= liw ? 83u : 44u;
        uint32_t g = i <= liw ? 215u : 62u;
        uint32_t b = i <= liw ? 238u : 78u;
        for (int yy = 0; yy < 4; yy++)
            for (int xx = 0; xx < seg_w; xx++)
                blend_pixel(fb, ow, oh, sx + xx, PANEL_Y + 103 + yy,
                            r, g, b, i <= liw ? 255u : 190u);
        sx += seg_w + gap;
    }
    centered_text(fb, px + panel_w / 2, PANEL_Y + 116, "HD", 1, 0xFF55C6D9u);

    hw_overlay_rect(px - 2, PANEL_Y - 2, panel_w + 4, PANEL_H + 4);
}
