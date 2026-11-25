#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include "engine/disk_boot.h"

uint8_t *g_mem;

int main(int argc, char **argv)
{
    if (argc != 4) return 2;
    g_mem = calloc(1, 8u * 1024u * 1024u);
    if (!g_mem || disk_boot_open((const char *const *)argv + 1, 3) < 0) return 1;

    /* Load the corrupt physical Disk.2 copy directly, bypassing the CLS alias
     * table, so this exercises the cross-disk recovery path itself. */
    FILE *f = fopen(argv[2], "rb");
    if (!f || fseek(f, 0xD26EBL, SEEK_SET) != 0 ||
        fread(g_mem + 0x500000, 1, 0x9388, f) != 0x9388) return 1;
    fclose(f);

    uint32_t direct = atn_decrunch(0x500000u);
    uint32_t recovered = disk_boot_recover_atn(0x500000u, 0x19000u, 0x9388u);
    printf("direct=%u recovered=%u\n", direct, recovered);
    disk_boot_close();
    free(g_mem);
    return direct == 0 && recovered == 0x19000u ? 0 : 1;
}
