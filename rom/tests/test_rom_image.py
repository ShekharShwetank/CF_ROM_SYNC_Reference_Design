#!/usr/bin/env python3
"""Check the reference image layout, fingerprint, CRC, and generated files."""

import hashlib
import sys
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "rom"))

import gen_rom_image as gen  # noqa: E402


class RomImageTest(unittest.TestCase):
    def setUp(self):
        self.image = gen.build_image()

    def test_length_header_and_regions(self):
        img = self.image
        self.assertEqual(len(img), 1024)
        self.assertEqual(img[0:4], b"CFRM")
        self.assertEqual(img[4], 0x01)
        self.assertEqual(img[6:8], b"\x00\x04")
        self.assertEqual(list(img[0x10:0x18]), [0x80, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02, 0x01])
        self.assertEqual(img[0x18], 0x7F)
        self.assertEqual(img[0x1F], 0xFE)
        self.assertEqual(img[0x20], 0x55)
        self.assertEqual(img[0x21], 0xAA)
        self.assertEqual(img[0x30], 0xAA)
        self.assertEqual(img[0x31], 0x55)
        self.assertEqual(img[0x40], 0x5A)
        self.assertEqual(img[0x41], 0xAA)
        self.assertEqual(img[0x60], 0x00)
        self.assertEqual(img[0x7F], 0x00)
        self.assertEqual(img[0x80], 0xFF)
        self.assertEqual(img[0xFF], 0xFF)
        self.assertEqual(img[0x100], 0x00)
        self.assertEqual(img[0x1FF], 0xFF)
        self.assertEqual(img[0x200], 0xA5)
        self.assertEqual(img[0x201], 0xFE)
        self.assertEqual(img[0x380:0x380 + len(gen.BANNER)], gen.BANNER)
        self.assertEqual(img[0x3C0], 0xFF)
        self.assertEqual(img[0x3FB], 0xFF)

    def test_sine_points(self):
        def sample(index):
            lo = self.image[0x300 + 2 * index]
            hi = self.image[0x300 + 2 * index + 1]
            value = lo | (hi << 8)
            if value & 0x8000:
                value -= 0x10000
            return value

        self.assertEqual(sample(0), 0)
        self.assertEqual(sample(16), 32767)
        self.assertEqual(sample(48), -32767)

    def test_fingerprint_and_crc(self):
        seen = [self.image[addr] for addr in gen.FINGERPRINT_ADDRS]
        self.assertEqual(len(set(seen)), len(seen))
        expect = zlib.crc32(self.image[:0x3FC]) & 0xFFFFFFFF
        self.assertEqual(gen.image_crc(self.image), expect)

    def test_generated_files_match_when_present(self):
        rom = ROOT / "submit" / "CF_ROM_SYNC.rom"
        sim = ROOT / "build" / "CF_ROM_SYNC_sim.v"
        digest_file = ROOT / "submit" / "CF_ROM_SYNC.rom.sha256"
        if not rom.is_file():
            return
        lines = [line.strip() for line in rom.read_text().splitlines() if line.strip()]
        self.assertEqual(len(lines), 1024)
        self.assertEqual(bytes(int(line, 16) for line in lines), self.image)
        digest = hashlib.sha256(self.image).hexdigest()
        if digest_file.is_file():
            self.assertEqual(digest_file.read_text().strip(), digest)
        if sim.is_file():
            self.assertIn(digest, sim.read_text())
            self.assertIn("mem[0] = 8'h43;", sim.read_text())
            self.assertIn("mem[1023] = 8'h%02x;" % self.image[1023], sim.read_text())


if __name__ == "__main__":
    unittest.main()
