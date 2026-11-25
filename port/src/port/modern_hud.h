#ifndef PC_MODERN_HUD_H
#define PC_MODERN_HUD_H

#include <stdint.h>

/* Optional vector-drawn HUD for the extra widescreen side margin. */
int pc_modern_hud_active(void);
void pc_modern_hud_overlay(uint32_t *fb);

#endif
