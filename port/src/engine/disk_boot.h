/* disk_boot.h — native boot from the original Benefactor disk images. */
#ifndef BENEFACTOR_DISK_BOOT_H
#define BENEFACTOR_DISK_BOOT_H
#include <stdint.h>

/* Open up to 4 disk images (Disk.1/2/3). Returns 0 if at least one opened. */
int  disk_boot_open(const char *const *paths, int n);
void disk_boot_close(void);

/* Raw byte copy from disk image (1-based) at src_off into g_mem[dst_addr]. */
int  disk_boot_load(int disk_no, uint32_t src_off, uint32_t dst_addr, uint32_t length);

/* In-place "ATN!" decrunch of the blob at `start` in g_mem. Returns the
 * decompressed length, or 0 if the magic/stream is invalid. */
uint32_t atn_decrunch(uint32_t start);

/* Load and decrunch one stream. If the supplied copy is corrupt, search the
 * other open disk images for an ATN!/IMP! stream with the same output and
 * packed sizes and use a copy that decodes cleanly. */
uint32_t disk_boot_load_atn(int disk_no, uint32_t src_off, uint32_t dst_addr,
                            uint32_t length);

/* Recover an already-loaded corrupt ATN!/IMP! stream from another disk. */
uint32_t disk_boot_recover_atn(uint32_t start, uint32_t expected_out,
                               uint32_t max_packed);

#endif
