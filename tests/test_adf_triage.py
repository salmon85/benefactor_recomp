import struct
import tempfile
import unittest
from pathlib import Path

from tools.adf_triage import STANDARD_DD_SIZE, repeated_runs, sized_candidate, triage_image


class AdfTriageTests(unittest.TestCase):
    def test_geometry_candidates_and_boot_checksum(self):
        data = bytearray(STANDARD_DD_SIZE)
        data[:4] = b"DOS\0"
        struct.pack_into(">H", data, 0x3FE, 0x4200)
        struct.pack_into(">4sII", data, 0x100, b"ATN!", 32, 0x20)
        struct.pack_into(">I", data, 0x120 + 12, 4)
        struct.pack_into(">H", data, 0x120 + 16, 0)
        data[0x120 + 18 : 0x120 + 46] = bytes(range(1, 29))
        struct.pack_into(">4sII", data, 0x200, b"=SB=", 16, 4)
        struct.pack_into(">4sII", data, 0x300, b"IMP!", 0xFFFFFFFF, 0xFFFFFFFE)
        data[0x500:0x510] = b"TSL!" * 4
        struct.pack_into(">I", data, 4, 0)
        total = 0
        for offset in range(0, 1024, 4):
            if offset == 4:
                continue
            previous = total
            total = (total + struct.unpack_from(">I", data, offset)[0]) & 0xFFFFFFFF
            if total < previous:
                total = (total + 1) & 0xFFFFFFFF
        struct.pack_into(">I", data, 4, (~total) & 0xFFFFFFFF)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.adf"
            path.write_bytes(data)
            report = triage_image(path)

        self.assertTrue(report["geometry"]["matches_standard_dd"])
        self.assertEqual(report["geometry"]["total_sectors"], 1760)
        self.assertTrue(report["bootblock"]["checksum_valid"])
        plausible = [item["offset"] for item in report["container_candidates"] if item["plausible"]]
        self.assertEqual(plausible, [0x100, 0x200])
        rejected = [item for item in report["container_candidates"] if item["offset"] == 0x300][0]
        self.assertFalse(rejected["plausible"])
        self.assertEqual(report["signatures"]["TSL!"]["repetitive_runs"][0]["copies"], 4)

    def test_custom_disk_tag(self):
        data = bytearray(0x400)
        struct.pack_into(">H", data, 0x3FE, 0x4202)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "header.adf"
            path.write_bytes(data)
            report = triage_image(path)
        self.assertEqual(report["sector_zero"]["custom_tag_be16_at_0x3fe"], "0x4202")
        self.assertIsNone(report["bootblock"])

    def test_iff_form_size_and_repetitive_run(self):
        data = b"FORM" + struct.pack(">I", 16) + b"ILBM" + b"x" * 12
        candidate = sized_candidate(data, 0, b"FORM", [])
        self.assertTrue(candidate["plausible"])
        self.assertEqual(candidate["end_exclusive"], len(data))
        self.assertEqual(repeated_runs(b"TSL!TSL!TSL!", b"TSL!")[0]["copies"], 3)


if __name__ == "__main__":
    unittest.main()
