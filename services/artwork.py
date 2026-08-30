"""Read an image's dimensions from its header bytes.

Framework-free and dependency-free, so it can be reused from a CLI or the web
app. Only the first bytes of a file are ever needed, which keeps a whole-library
sweep cheap: a cover's size is known long before its pixels are.
"""

_JPEG_SOF = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}


def _jpeg_size(buf):
    pos, end = 2, len(buf)
    while pos + 9 <= end:
        if buf[pos] != 0xFF:
            pos += 1
            continue
        marker = buf[pos + 1]
        if marker == 0xFF:
            pos += 1
            continue
        if marker == 0x01 or 0xD0 <= marker <= 0xD8:
            pos += 2
            continue
        if marker in (0xDA, 0xD9):
            return None
        if marker in _JPEG_SOF:
            return "jpeg", int.from_bytes(buf[pos + 7:pos + 9], "big"), int.from_bytes(buf[pos + 5:pos + 7], "big")
        pos += 2 + int.from_bytes(buf[pos + 2:pos + 4], "big")
    return None


def _webp_size(buf):
    if len(buf) < 30:
        return None
    chunk = buf[12:16]
    if chunk == b"VP8X":
        return "webp", int.from_bytes(buf[24:27], "little") + 1, int.from_bytes(buf[27:30], "little") + 1
    if chunk == b"VP8 ":
        return "webp", int.from_bytes(buf[26:28], "little") & 0x3FFF, int.from_bytes(buf[28:30], "little") & 0x3FFF
    if chunk == b"VP8L":
        bits = int.from_bytes(buf[21:25], "little")
        return "webp", (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    return None


def _png_size(data):
    if data[:8] != b"\x89PNG\r\n\x1a\n" or len(data) < 24:
        return None
    return "png", int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


def _gif_size(data):
    if data[:3] != b"GIF" or len(data) < 10:
        return None
    return "gif", int.from_bytes(data[6:8], "little"), int.from_bytes(data[8:10], "little")


def _bmp_size(data):
    if data[:2] != b"BM" or len(data) < 26:
        return None
    # A bottom-up bitmap states its height as a negative number.
    width = int.from_bytes(data[18:22], "little", signed=True)
    height = int.from_bytes(data[22:26], "little", signed=True)
    return "bmp", abs(width), abs(height)


def _riff_size(data):
    if data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return None
    return _webp_size(data)


def _soi_size(data):
    if data[:2] != b"\xff\xd8":
        return None
    return _jpeg_size(data)


_READERS = (_png_size, _gif_size, _bmp_size, _riff_size, _soi_size)


def image_size(data):
    """Return (format, width, height) for JPEG/PNG/GIF/BMP/WebP bytes, else None.

    `format` is a lowercase name ("jpeg", "png", ...). None means the bytes seen
    so far don't pin the size down — either they aren't a known image, or the
    header hasn't arrived yet, so a caller streaming a file can keep reading and
    ask again. A JPEG carrying a large colour profile can push its SOF marker
    hundreds of kilobytes into the file.
    """
    for reader in _READERS:
        size = reader(data)
        if size:
            return size
    return None


def smallest_side(data):
    """Return the shorter side of an image in pixels, or 0 when unknown.

    The shorter side is what decides how sharp a square cover looks once
    displayed, so it is the figure covers are compared on.
    """
    dims = image_size(data)
    return min(dims[1], dims[2]) if dims else 0
