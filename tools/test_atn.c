#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include "engine/disk_boot.h"

uint8_t *g_mem;

int main(int argc, char **argv) {
    if (argc != 6) {
        fprintf(stderr, "usage: %s <disk> <offset-hex> <length-hex> <dest-hex> <out>\n", argv[0]);
        return 2;
    }
    const char *disks[1] = { argv[1] };
    uint32_t off = (uint32_t)strtoul(argv[2], NULL, 0);
    uint32_t len = (uint32_t)strtoul(argv[3], NULL, 0);
    uint32_t dest = (uint32_t)strtoul(argv[4], NULL, 0);
    g_mem = calloc(1, 8u * 1024u * 1024u);
    if (!g_mem || disk_boot_open(disks, 1) < 0) return 1;
    int got = disk_boot_load(1, off, dest, len);
    fprintf(stderr, "loaded %d bytes at 0x%x\n", got, dest);
    uint32_t out = atn_decrunch(dest);
    fprintf(stderr, "decrunched length 0x%x\n", out);
    FILE *f = fopen(argv[5], "wb");
    if (!f) return 1;
    fwrite(g_mem, 1, 0x600000u, f);
    fclose(f);
    disk_boot_close();
    free(g_mem);
    return out ? 0 : 1;
}
