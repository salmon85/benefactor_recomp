/* harness/puae_state.h
 * Shared state snapshot used by both the PUAE side and the PC-port side.
 */
#ifndef PUAE_STATE_H
#define PUAE_STATE_H

#include <stdint.h>
#include <stddef.h>

#define HARNESS_COPLIST_WORDS 1412 /* full copper list: 705 instrs = 1410 words + end marker */

/* Paula audio state for one channel, snapped once per frame.
 * All fields are RAW register values (16-bit, as written to $DFF0Ax-$DFF0Dx). */
typedef struct AudioChanSnap {
    uint32_t lc;    /* AUDxLCH:LCL — sample start address (chip RAM) */
    uint16_t len;   /* AUDxLEN — sample length in words */
    uint16_t per;   /* AUDxPER — period (raw register, 1-65535) */
    uint16_t vol;   /* AUDxVOL — volume (0-64) */
    /* Development-oracle DMA phase.  The native mixer normally owns these,
     * but the lockstep harness seeds them so comparisons start at the same
     * byte inside a looping sample instead of restarting every channel at 0. */
    uint32_t pt;
    uint16_t wlen;
    uint8_t  state;
    uint32_t evtime;
} AudioChanSnap;

typedef struct PuaeCpuSnap {
    uint32_t pc;
    uint32_t sr;
    uint32_t d[8];
    uint32_t a[8];
} PuaeCpuSnap;

typedef struct FrameState {
    int      frame;

    /* DMA / copper */
    uint32_t cop1lc;
    uint32_t cop2lc;

    /* Bitplane control */
    uint16_t bplcon0;
    uint16_t bplcon1;
    uint16_t bplcon2;
    int16_t  bpl1mod;
    int16_t  bpl2mod;
    uint16_t diwstrt;
    uint16_t diwstop;
    uint16_t ddfstrt;
    uint16_t ddfstop;

    /* Bitplane pointers (up to 6 planes for OCS) */
    uint32_t bplpt[6];

    /* Sprite pointers (8 hardware sprites) */
    uint32_t sprpt[8];

    /* ECS palette (12-bit × 32) */
    uint16_t palette[32];

    /* First bytes of the copper list the game set this frame */
    uint16_t coplist[HARNESS_COPLIST_WORDS];
    int      coplist_valid;   /* 1 if cop1lc was readable */

    /* CRC32 of full chip RAM (512 KB) — catches bitplane/sprite data divergence.
     * Set to 0 if not available. */
    uint32_t chipram_crc;

    /* CRC32 of the active bitplane data regions (Benefactor-specific).
     * Covers: $025334+4KB (title bpls), $04F6F4+4KB (gameplay bpl1+3),
     *         $070958+8KB (gameplay bpl2).
     * Used as a DIFF trigger: if this differs, bitplane content diverged. */
    uint32_t bpl_data_crc;

    /* Paula audio channels 0-3 */
    AudioChanSnap audio[4];

    /* Sprite animation state from chip RAM — used for per-frame phase tracking */
    uint16_t flip_flop;   /* $0041A2: SWAP/noswap selector toggled by $0041A4 */
    uint16_t sprite_ctr;  /* $0042FC: counter incremented by $0052A4 */
    uint32_t anim_ptr;    /* $0042FE: animation string read pointer, advances on RESET */
} FrameState;


/* Simple CRC32 (ISO 3309 / Ethernet polynomial). */
static inline uint32_t crc32_buf(const uint8_t *data, uint32_t len)
{
    uint32_t crc = 0xFFFFFFFFu;
    for (uint32_t i = 0; i < len; i++) {
        crc ^= data[i];
        for (int b = 0; b < 8; b++)
            crc = (crc >> 1) ^ (0xEDB88320u & -(crc & 1));
    }
    return ~crc;
}

/* CRC32 over the active bitplane data regions (game-specific fixed addresses).
 * mem/size = chip RAM base and its total size in bytes. */
static inline uint32_t bpl_data_region_crc(const uint8_t *mem, uint32_t size)
{
    static const struct { uint32_t start; uint32_t len; } regions[] = {
        { 0x025334u, 4096u }, /* title screen bitplanes (4-plane, lines 44-89) */
        { 0x04F6F4u, 4096u }, /* gameplay bpl1+3 */
        { 0x070958u, 8192u }, /* gameplay bpl2 (larger — more blitter output here) */
    };
    uint32_t crc = 0xFFFFFFFFu;
    for (int r = 0; r < 3; r++) {
        uint32_t off = regions[r].start;
        uint32_t len = regions[r].len;
        if (off + len > size) continue;
        const uint8_t *p = mem + off;
        for (uint32_t i = 0; i < len; i++) {
            crc ^= p[i];
            for (int b = 0; b < 8; b++)
                crc = (crc >> 1) ^ (0xEDB88320u & -(crc & 1));
        }
    }
    return ~crc;
}

/* ── PUAE side ── */
void puae_snap_state(FrameState *s);          /* implemented via custom.c include */
void puae_get_cpu_state(PuaeCpuSnap *s);      /* PC/SR/D0-D7/A0-A7 */
uint32_t puae_get_cop1lc(void);               /* lightweight boot-detection accessor */
uint16_t puae_get_beam_line(void);
void puae_note_music_irq(uint32_t pc);
extern int g_puae_irq_trace_enabled;
unsigned puae_get_music_irq_count(void);
unsigned puae_get_music_range_count(void);
uint32_t puae_get_last_irq_pc(void);
unsigned puae_get_hook_calls(void);
unsigned puae_get_irq_pos_count(void);
uint16_t puae_get_irq_pos(unsigned index);
unsigned puae_get_range_entry_count(void);
uint32_t puae_get_range_entry_pc(unsigned index);
uint16_t puae_get_range_entry_pos(unsigned index);
void puae_reset_music_irq_count(void);
int  puae_dump_chipram(void *buf, int maxbytes); /* copy chip RAM out of PUAE */
int  puae_dump_mem(uint32_t addr, void *buf, int len); /* copy any Amiga addr range (chip+fast) */
void puae_poke_mem(uint32_t addr, const void *buf, int len); /* write any Amiga addr range */
void puae_dump_audio_regs(const char *path);  /* save audio sync state to file */

#endif /* PUAE_STATE_H */
