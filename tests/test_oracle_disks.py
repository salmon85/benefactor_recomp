#!/usr/bin/env python3
"""Regression tests for the development-only WHDLoad oracle disk rebuild."""

from __future__ import annotations

import unittest

from tools.build_oracle_disks import WHDLOAD_DISK_SIZE, reconstruct_oracle_disks


class OracleDiskTests(unittest.TestCase):
    def test_disk1_preserves_boot_and_main_but_shifts_title_and_later(self):
        d1 = bytearray(901120)
        d1[0:4] = b"BOOT"
        d1[0x1C80:0x1C84] = b"MAIN"
        d1[0x26270:0x26274] = b"OLD!"
        d1[0x26670:0x26674] = b"TITL"

        disks = reconstruct_oracle_disks(bytes(d1), bytes(901120), bytes(901120))

        self.assertEqual(len(disks[0]), WHDLOAD_DISK_SIZE)
        self.assertEqual(disks[0][0:4], b"BOOT")
        self.assertEqual(disks[0][0x1C80:0x1C84], b"MAIN")
        self.assertEqual(disks[0][0x26270:0x26274], b"TITL")

    def test_disks2_and3_shift_payloads_by_0400(self):
        d2 = bytearray(901120)
        d3 = bytearray(901120)
        d2[0x400:0x404] = b"D2P0"
        d2[0x800:0x804] = b"D2P1"
        d3[0x400:0x404] = b"D3P0"
        d3[0x800:0x804] = b"D3P1"

        disks = reconstruct_oracle_disks(bytes(901120), bytes(d2), bytes(d3))

        self.assertEqual(disks[1][0:4], b"D2P0")
        self.assertEqual(disks[1][0x400:0x404], b"D2P1")
        self.assertEqual(disks[2][0:4], b"D3P0")
        self.assertEqual(disks[2][0x400:0x404], b"D3P1")

    def test_relocated_streams_are_copied_from_physical_disk3_offsets(self):
        d3 = bytearray(901120)
        d3[0x499B4:0x499B8] = b"W5A!"
        d3[0x31128:0x3112C] = b"CRED"

        disks = reconstruct_oracle_disks(bytes(901120), bytes(901120), bytes(d3))

        self.assertEqual(disks[1][0xD22EB:0xD22EF], b"W5A!")
        self.assertEqual(disks[2][0xC7100:0xC7104], b"CRED")

    def test_inputs_larger_than_whdload_image_are_rejected(self):
        with self.assertRaises(ValueError):
            reconstruct_oracle_disks(
                bytes(WHDLOAD_DISK_SIZE + 1),
                bytes(WHDLOAD_DISK_SIZE),
                bytes(WHDLOAD_DISK_SIZE),
            )


if __name__ == "__main__":
    unittest.main()
