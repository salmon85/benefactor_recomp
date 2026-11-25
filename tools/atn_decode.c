#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include "engine/disk_boot.h"

uint8_t *g_mem;

int main(int argc, char **argv)
{
    if (argc != 5) {
        fprintf(stderr, "usage: %s <disk> <offset> <length> <out>\n", argv[0]);
        return 2;
    }
    FILE *f = fopen(argv[1], "rb");
    if (!f) return 1;
    unsigned long off = strtoul(argv[2], NULL, 0);
    unsigned long len = strtoul(argv[3], NULL, 0);
    g_mem = calloc(1, 8u * 1024u * 1024u);
    if (!g_mem || fseek(f, (long)off, SEEK_SET) != 0 ||
        fread(g_mem + 0x500000, 1, len, f) != len) return 1;
    fclose(f);
    uint32_t out = atn_decrunch(0x500000u);
    if (!out) return 1;
    f = fopen(argv[4], "wb");
    if (!f || fwrite(g_mem + 0x500000, 1, out, f) != out) return 1;
    fclose(f);
    free(g_mem);
    return 0;
}
