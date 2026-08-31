"""Tests for reading an image's dimensions out of its header bytes.

image_size answers from the header alone, so the tests build the smallest
headers each format allows rather than carrying binary fixtures. A None result
means "not known from these bytes", which covers both a non-image and a header
that has not arrived yet — the case a streaming caller retries on.
"""

import struct
import unittest
import zlib

from services.artwork import image_size, smallest_side


def jpeg(width, height, marker=0xC0, before=b""):
    """A JPEG header: SOI, optional leading segments, then the SOF marker."""
    sof = bytes([0xFF, marker]) + struct.pack(">HBHHB", 17, 8, height, width, 3)
    return b"\xff\xd8" + before + sof + b"\x01\x11\x00\x02\x11\x01\x03\x11\x01"


def app_segment(marker, payload):
    return bytes([0xFF, marker]) + struct.pack(">H", len(payload) + 2) + payload


def png(width, height):
    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)


class JpegTest(unittest.TestCase):
    def test_baseline(self):
        self.assertEqual(image_size(jpeg(1400, 1200)), ("jpeg", 1400, 1200))

    def test_progressive(self):
        self.assertEqual(image_size(jpeg(500, 500, marker=0xC2)), ("jpeg", 500, 500))

    def test_skips_leading_segments(self):
        # An embedded colour profile can push the SOF marker far into the file.
        before = app_segment(0xE1, b"Exif\x00\x00" + b"\x00" * 200) + app_segment(0xE2, b"ICC" + b"\x00" * 60000)
        self.assertEqual(image_size(jpeg(900, 900, before=before)), ("jpeg", 900, 900))

    def test_header_not_reached_yet(self):
        truncated = jpeg(900, 900, before=app_segment(0xE2, b"\x00" * 5000))[:2000]
        self.assertIsNone(image_size(truncated))

    def test_scan_start_without_size(self):
        self.assertIsNone(image_size(b"\xff\xd8" + app_segment(0xDA, b"\x00" * 10)))


class OtherFormatsTest(unittest.TestCase):
    def test_png(self):
        self.assertEqual(image_size(png(320, 240)), ("png", 320, 240))

    def test_png_truncated(self):
        self.assertIsNone(image_size(png(320, 240)[:16]))

    def test_gif(self):
        data = b"GIF89a" + struct.pack("<HH", 800, 600)
        self.assertEqual(image_size(data), ("gif", 800, 600))

    def test_bmp_bottom_up_height_is_negative(self):
        data = b"BM" + b"\x00" * 16 + struct.pack("<ii", 640, -480)
        self.assertEqual(image_size(data), ("bmp", 640, 480))

    def test_webp_lossy(self):
        data = b"RIFF" + b"\x00" * 4 + b"WEBP" + b"VP8 " + b"\x00" * 10 + struct.pack("<HH", 1024, 768)
        self.assertEqual(image_size(data), ("webp", 1024, 768))

    def test_webp_lossless(self):
        bits = (1024 - 1) | ((768 - 1) << 14)
        data = b"RIFF" + b"\x00" * 4 + b"WEBP" + b"VP8L" + b"\x00" * 5 + struct.pack("<I", bits) + b"\x00" * 6
        self.assertEqual(image_size(data), ("webp", 1024, 768))

    def test_webp_extended(self):
        canvas = (1600 - 1).to_bytes(3, "little") + (1600 - 1).to_bytes(3, "little")
        data = b"RIFF" + b"\x00" * 4 + b"WEBP" + b"VP8X" + b"\x00" * 8 + canvas
        self.assertEqual(image_size(data), ("webp", 1600, 1600))


class NotAnImageTest(unittest.TestCase):
    def test_empty(self):
        self.assertIsNone(image_size(b""))

    def test_text(self):
        self.assertIsNone(image_size(b"not an image at all"))


class SmallestSideTest(unittest.TestCase):
    def test_returns_the_shorter_side(self):
        self.assertEqual(smallest_side(jpeg(1000, 750)), 750)
        self.assertEqual(smallest_side(jpeg(600, 900)), 600)

    def test_zero_when_unknown(self):
        self.assertEqual(smallest_side(b"garbage"), 0)


if __name__ == "__main__":
    unittest.main()
