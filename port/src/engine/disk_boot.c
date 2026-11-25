/* disk_boot.c — native boot from the original Benefactor disk images.
 *
 * Replaces the chip-RAM snapshot: reads the game's crunched data straight from
 * the WHDLoad disk images, decompresses it with a faithful reimplementation of
 * the game's own "ATN!" decruncher, and serves the game's runtime Load calls
 * from the images.  No PUAE, no snapshot.
 *
 * Boot sequence (reverse-engineered from the Disk.1 loader at $76412):
 *   Load(disk=1, off=$1880, len=$2442E, dst=$3000)   ; crunched main game
 *   Decrunch($3000)                                  ; ATN! → $3000..$7013C
 *   jmp $3000                                        ; second-stage loader
 * The second-stage loader then Load()s further data from the disks; those
 * calls are decoded the same way (D0[7:0]=disk-1, D0[31:8]=byte offset,
 * D1=length, D2=dest) and serviced by disk_boot_load().
 */
#include "engine/rt.h"   /* g_mem, RT_MEM_SIZE — NOT hw_private.h, which drags in SDL and is
                   * unnecessary here (the dumpbanks regen tool must build without SDL). */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_DISKS 4
static FILE    *s_disk[MAX_DISKS];
static uint32_t s_disk_sz[MAX_DISKS];

int disk_boot_open(const char *const *paths, int n)
{
    int opened = 0;
    for (int i = 0; i < MAX_DISKS; i++) { s_disk[i] = NULL; s_disk_sz[i] = 0; }
    for (int i = 0; i < n && i < MAX_DISKS; i++) {
        if (!paths[i]) continue;
        s_disk[i] = fopen(paths[i], "rb");
        if (!s_disk[i]) { fprintf(stderr, "[diskboot] cannot open %s\n", paths[i]); continue; }
        fseek(s_disk[i], 0, SEEK_END);
        s_disk_sz[i] = (uint32_t)ftell(s_disk[i]);
        rewind(s_disk[i]);
        if (getenv("DISKBOOT_LOG"))
            fprintf(stderr, "[diskboot] opened[%d] '%s' size=%u\n", i, paths[i], s_disk_sz[i]);
        opened++;
    }
    return opened > 0 ? 0 : -1;
}

void disk_boot_close(void)
{
    for (int i = 0; i < MAX_DISKS; i++)
        if (s_disk[i]) { fclose(s_disk[i]); s_disk[i] = NULL; s_disk_sz[i] = 0; }
}

static int disk_boot_read_idx(int idx, uint32_t src_off, uint32_t dst_addr, uint32_t length)
{
    if (idx < 0 || idx >= MAX_DISKS || !s_disk[idx]) return -1;
    if (src_off >= s_disk_sz[idx]) return 0;
    if (src_off + length > s_disk_sz[idx]) length = s_disk_sz[idx] - src_off;
    if (dst_addr + length > RT_MEM_SIZE) return -1;
    fseek(s_disk[idx], (long)src_off, SEEK_SET);
    size_t got = fread(g_mem + dst_addr, 1, length, s_disk[idx]);
    return (int)got;
}

/* Copy `length` raw bytes from disk image `disk_no` (1-based) at byte offset
 * `src_off` into chip RAM at `dst_addr`. Returns bytes copied, or -1 on error. */
int disk_boot_load(int disk_no, uint32_t src_off, uint32_t dst_addr, uint32_t length)
{
    int idx = disk_no - 1;
    /* The CLS redistribution moved the shared world-5 assets to Disk.3 but
     * left the gameplay table pointing at their old Disk.2 offsets. The
     * credits stream was moved likewise. Match the full request (disk,
     * logical offset, length) so no unrelated read can be redirected. */
    static const struct {
        int disk; uint32_t off, len; int alias_disk; uint32_t alias_off;
    } aliases[] = {
        { 2, 0x0DE203u, 0x0050A6u, 3, 0x0558CCu },
        { 2, 0x0E3387u, 0x0064B8u, 3, 0x05AA50u },
        { 2, 0x0D22EBu, 0x009388u, 3, 0x0499B4u },
        { 2, 0x0E983Fu, 0x0051DCu, 3, 0x060F08u },
        { 3, 0x0C7100u, 0x001888Cu, 3, 0x031128u },
    };
    for (unsigned i = 0; i < sizeof aliases / sizeof aliases[0]; i++) {
        if (disk_no == aliases[i].disk && src_off == aliases[i].off && length == aliases[i].len) {
            if (getenv("DISKBOOT_LOG"))
                fprintf(stderr, "[diskboot] CLS alias disk=%d off=$%X -> disk=%d off=$%X\n",
                        disk_no, src_off, aliases[i].alias_disk, aliases[i].alias_off);
            return disk_boot_read_idx(aliases[i].alias_disk - 1, aliases[i].alias_off,
                                      dst_addr, length);
        }
    }
    /* The CLS ADFs insert a 0x400-byte crack stub before the game data area.
     * Runtime/game offsets are the original logical offsets; the payloads in
     * these ADFs begin 0x400 bytes later. Keep this translation here so every
     * overlay and streamed level read uses one mapping. */
    uint32_t physical_off = src_off + (((idx > 0) || (src_off >= 0x1880u)) ? 0x400u : 0u);
    if (getenv("DISKBOOT_LOAD_LOG"))
        fprintf(stderr, "[diskboot] load disk=%d logical=$%06X physical=$%06X len=$%X dst=$%06X\n",
                disk_no, src_off, physical_off, length, dst_addr);
    return disk_boot_read_idx(idx, physical_off, dst_addr, length);
}

/* ── ATN! decruncher ──────────────────────────────────────────────────────
 * Backwards LZ.  Decompresses in place: the crunched blob lives at `start`,
 * the output expands upward to start+output_len.  Faithful reimplementation
 * of the game's routine at $0765E4 (validated byte-exact against a PUAE
 * decrunch in the code region).  Operates directly on g_mem.
 */
static const uint8_t ATN_T738[4]  = { 0x06, 0x0A, 0x0A, 0x12 };
static const uint8_t ATN_T73C[12] = { 1,1,1,1, 2,3,3,4, 4,5,7,14 };

static uint32_t r32(uint32_t a)
{
    return ((uint32_t)g_mem[a] << 24) | ((uint32_t)g_mem[a+1] << 16)
         | ((uint32_t)g_mem[a+2] << 8) | g_mem[a+3];
}

/* Bit reader state for the backwards stream. */
typedef struct { uint32_t a3; uint16_t d3; uint8_t X; uint8_t invalid; } AtnBits;

static int atn_getbit(AtnBits *b, uint32_t start)
{
    if (b->invalid) return 0;
    uint8_t lo = b->d3 & 0xFF;
    int c = (lo >> 7) & 1;
    uint8_t res = (uint8_t)(lo << 1);
    b->X = (uint8_t)c;
    if (res != 0) { b->d3 = (uint16_t)((b->d3 & 0xFF00) | res); return c; }
    /* buffer empty → reload a byte (read backwards) and shift in X */
    if (b->a3 <= start) { b->invalid = 1; return 0; }
    uint8_t by = g_mem[--b->a3];
    uint8_t xin = b->X;
    int c2 = (by >> 7) & 1;
    uint8_t res2 = (uint8_t)((by << 1) | xin);
    b->X = (uint8_t)c2;
    b->d3 = (uint16_t)((b->d3 & 0xFF00) | res2);
    return c2;
}

/* Returns decompressed length, or 0 if the magic doesn't match.
 * Accepts both "ATN!" (the game's own files) and "IMP!" (the fan-made
 * Disk.4 extra levels): both are Amiga Imploder-family containers with the
 * identical [magic][decrunched_len][crunched_len] header and bitstream —
 * the per-file token tables are read FROM the stream (the 28-byte block
 * below), so the algorithm is magic-agnostic. */
uint32_t atn_decrunch(uint32_t start)
{
    if (start > RT_MEM_SIZE - 12u) return 0;
    uint32_t magic = r32(start);
    if (magic != 0x41544E21u && magic != 0x494D5021u) return 0;  /* ATN! / IMP! */
    uint32_t out_len = r32(start + 4);
    uint32_t packed_len = r32(start + 8);
    if (out_len == 0 || packed_len < 58u || packed_len > out_len) return 0;
    if (out_len > RT_MEM_SIZE - start || packed_len > RT_MEM_SIZE - start) return 0;
    uint32_t a4 = start + out_len;                    /* output end (write -(a4)) */
    uint32_t a3 = start + packed_len;                 /* input end (read -(a3))  */
    uint32_t a5 = start;                              /* output start (stop)      */
    uint32_t a0 = start + 12, a2 = a3;
    /* restore the 3 longs the header overwrote at the start */
    for (int i = 0; i < 3; i++) {
        uint32_t v = r32(a2); a2 += 4; a0 -= 4;
        g_mem[a0] = v>>24; g_mem[a0+1] = v>>16; g_mem[a0+2] = v>>8; g_mem[a0+3] = v;
    }
    uint32_t d2 = r32(a2); a2 += 4;                   /* initial literal run     */
    uint16_t d3 = (uint16_t)((g_mem[a2]<<8)|g_mem[a2+1]); a2 += 2;
    if (!(d3 & 0x8000)) a3 -= 1;
    uint8_t tbl[28];
    memcpy(tbl, g_mem + a2, 28); a2 += 28;

    AtnBits b = { a3, d3, 0, 0 };
    for (;;) {
        if (d2 > a4 - a5) return 0;
        while (d2 > 0) {
            if (b.a3 <= a5) return 0;
            g_mem[--a4] = g_mem[--b.a3]; d2--;
        }
        if (!(a5 < a4)) break;
        int d4, d0;
        if (atn_getbit(&b, start) == 0)      { d4 = 2; d0 = 0; }
        else if (atn_getbit(&b, start) == 0) { d4 = 3; d0 = 1; }
        else if (atn_getbit(&b, start) == 0) { d4 = 4; d0 = 2; }
        else if (atn_getbit(&b, start) == 0) { d4 = 5; d0 = 3; }
        else if (atn_getbit(&b, start) == 1) { if (b.a3 <= a5) return 0;
                                               d4 = g_mem[--b.a3]; d0 = 3; }
        else {
            int v = 0;
            for (int i = 0; i < 3; i++) v = ((v << 1) | atn_getbit(&b, start)) & 0xFF;
            d4 = (v + 6) & 0xFF; d0 = 3;
        }
        if (b.invalid || d4 == 0 || d4 > (int)(a4 - a5)) return 0;
        int d1 = d0, d5 = 0;
        if (atn_getbit(&b, start) == 1) {
            if (atn_getbit(&b, start) == 1) { d5 = ATN_T738[d0]; d0 += 8; }
            else                     { d5 = 2;            d0 += 4; }
        }
        int nb = ATN_T73C[d0];
        d2 = 0;
        for (int i = 0; i < nb; i++) d2 = ((d2 << 1) | atn_getbit(&b, start)) & 0xFFFF;
        d2 += d5;
        /* match offset */
        uint32_t a2base = 0; d0 = d1;
        if (atn_getbit(&b, start) == 1) {
            int d1b = (d1 << 1) & 0xFFFF;
            if (atn_getbit(&b, start) == 1) { a2base = (tbl[8+d1b]<<8)|tbl[8+d1b+1]; d0 += 8; }
            else                     { a2base = (tbl[d1b]<<8)|tbl[d1b+1];     d0 += 4; }
        }
        nb = tbl[0x10 + d0];
        uint32_t off = 0;
        for (int i = 0; i < nb; i++) off = ((off << 1) | atn_getbit(&b, start));
        if (b.invalid) return 0;
        uint32_t src = a4 + a2base + off + 1;
        if (src > RT_MEM_SIZE || src <= a5) return 0;
        for (int i = 0; i < d4; i++) {
            if (a4 <= a5 || src <= a5) return 0;
            g_mem[--a4] = g_mem[--src];
        }
    }
    return out_len;
}

static uint32_t be32_at(uint32_t a)
{
    return r32(a);
}

uint32_t disk_boot_recover_atn(uint32_t start, uint32_t expected_out,
                               uint32_t max_packed)
{
    if (expected_out == 0 || expected_out > RT_MEM_SIZE - start) return 0;
    for (int i = 0; i < MAX_DISKS; i++) {
        if (!s_disk[i] || s_disk_sz[i] < 12u) continue;
        uint8_t *buf = (uint8_t *)malloc(s_disk_sz[i]);
        if (!buf) continue;
        rewind(s_disk[i]);
        size_t got = fread(buf, 1, s_disk_sz[i], s_disk[i]);
        if (got == s_disk_sz[i]) {
            for (uint32_t off = 0; off + 12u <= got; off += 2u) {
                uint32_t magic = ((uint32_t)buf[off]<<24)|((uint32_t)buf[off+1]<<16)
                               |((uint32_t)buf[off+2]<<8)|buf[off+3];
                if (magic != 0x41544E21u && magic != 0x494D5021u) continue;
                uint32_t out = ((uint32_t)buf[off+4]<<24)|((uint32_t)buf[off+5]<<16)
                             |((uint32_t)buf[off+6]<<8)|buf[off+7];
                uint32_t packed = ((uint32_t)buf[off+8]<<24)|((uint32_t)buf[off+9]<<16)
                                |((uint32_t)buf[off+10]<<8)|buf[off+11];
                if (out != expected_out || packed < 58u || packed > max_packed
                    || off + packed > got) continue;
                uint32_t read_len = max_packed > packed ? max_packed : packed;
                if (off + read_len > got) read_len = packed;
                if (getenv("DISKBOOT_LOG"))
                    fprintf(stderr, "[diskboot] ATN candidate disk=%d off=$%X out=$%X packed=$%X read=$%X\n",
                            i + 1, off, out, packed, read_len);
                memset(g_mem + start, 0, expected_out);
                if (disk_boot_read_idx(i, off, start, read_len) != (int)read_len) continue;
                if (atn_decrunch(start) == expected_out) {
                    fprintf(stderr, "[diskboot] recovered corrupt ATN stream from disk %d @$%X\n",
                            i + 1, off);
                    free(buf);
                    return expected_out;
                }
            }
        }
        free(buf);
    }
    return 0;
}

uint32_t disk_boot_load_atn(int disk_no, uint32_t src_off, uint32_t dst_addr,
                            uint32_t length)
{
    if (disk_boot_load(disk_no, src_off, dst_addr, length) < 12) return 0;
    uint32_t expected = be32_at(dst_addr + 4u);
    uint32_t out = atn_decrunch(dst_addr);
    if (out != expected)
        out = disk_boot_recover_atn(dst_addr, expected, length);
    return out;
}
