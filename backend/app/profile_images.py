"""Bounded raster-container validation; bytes stay intact to retain GIF animation.

No external URLs, filesystem uploads, image decoder or executable formats. The
browser decodes the image; these checks constrain format, dimensions and frames.
"""
import struct
import zlib

MAX_AVATAR_BYTES = 5 * 1024 * 1024
MAX_SIDE = 1024
MAX_FRAMES = 120
MAX_PIXELS = 16 * 1024 * 1024


def dimensions(width, height):
    if not 1 <= width <= MAX_SIDE or not 1 <= height <= MAX_SIDE:
        raise ValueError("Profilbilder dürfen höchstens 1024 × 1024 Pixel groß sein.")


def validate_avatar(data: bytes) -> str:
    if not data or len(data) > MAX_AVATAR_BYTES:
        raise ValueError("Ein Profilbild darf höchstens 5 MB groß sein.")
    try:
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            offset, count, seen_data = 8, 0, False
            while offset + 12 <= len(data):
                size = int.from_bytes(data[offset:offset+4], "big")
                kind = data[offset+4:offset+8]
                end = offset + 12 + size
                if end > len(data) or zlib.crc32(data[offset+4:end-4]) != int.from_bytes(data[end-4:end], "big"):
                    raise ValueError()
                if count == 0:
                    if kind != b"IHDR" or size != 13: raise ValueError()
                    dimensions(*struct.unpack(">II", data[offset+8:offset+16]))
                if kind == b"acTL": raise ValueError("Animierte PNGs werden nicht unterstützt; bitte GIF verwenden.")
                if kind == b"IDAT" and size: seen_data = True
                if kind == b"IEND":
                    if size or end != len(data) or not seen_data: raise ValueError()
                    return "image/png"
                offset, count = end, count + 1
        elif data[:6] in (b"GIF87a", b"GIF89a"):
            width, height = struct.unpack("<HH", data[6:10]); dimensions(width, height)
            packed = data[10]
            offset = 13 + (3 * (2 ** ((packed & 7) + 1)) if packed & 128 else 0)
            frames, pixels = 0, 0
            def blocks(position):
                while position < len(data):
                    size = data[position]; position += 1
                    if size == 0: return position
                    position += size
                    if position > len(data): raise ValueError()
                raise ValueError()
            while offset < len(data):
                marker = data[offset]; offset += 1
                if marker == 0x3B:
                    if offset == len(data) and frames: return "image/gif"
                    raise ValueError()
                if marker == 0x21:
                    offset = blocks(offset + 1)
                elif marker == 0x2C:
                    left, top, fw, fh, packed = struct.unpack("<HHHHB", data[offset:offset+9])
                    dimensions(fw, fh)
                    if left + fw > width or top + fh > height: raise ValueError()
                    frames += 1; pixels += width * height
                    if frames > MAX_FRAMES or pixels > MAX_PIXELS:
                        raise ValueError("Animation zu groß: maximal 120 Bilder und 16 Megapixel insgesamt.")
                    offset += 9 + (3 * (2 ** ((packed & 7) + 1)) if packed & 128 else 0)
                    if data[offset] not in range(2, 9): raise ValueError()
                    offset = blocks(offset + 1)
                else: raise ValueError()
        elif data.startswith(b"\xff\xd8") and data.endswith(b"\xff\xd9"):
            offset, found = 2, False
            while offset + 4 < len(data):
                if data[offset] != 255: raise ValueError()
                while data[offset] == 255: offset += 1
                marker = data[offset]; offset += 1
                size = int.from_bytes(data[offset:offset+2], "big")
                if size < 2 or offset + size > len(data): raise ValueError()
                if marker in (0xC0, 0xC1, 0xC2):
                    if size < 8: raise ValueError()
                    height, width = struct.unpack(">HH", data[offset+3:offset+7]); dimensions(width, height); found = True
                if marker == 0xDA:
                    if found and offset + size < len(data)-2: return "image/jpeg"
                    raise ValueError()
                offset += size
        elif data.startswith(b"RIFF") and data[8:12] == b"WEBP" and int.from_bytes(data[4:8], "little") + 8 == len(data):
            offset, found, frames, pixels, animated, canvas = 12, False, 0, 0, False, None
            while offset + 8 <= len(data):
                kind = data[offset:offset+4]; size = int.from_bytes(data[offset+4:offset+8], "little")
                chunk = data[offset+8:offset+8+size]
                if len(chunk) != size: raise ValueError()
                if kind == b"VP8X" and size == 10:
                    canvas=(1+int.from_bytes(chunk[4:7],"little"),1+int.from_bytes(chunk[7:10],"little"))
                    dimensions(*canvas)
                    animated = bool(chunk[0] & 2)
                elif kind == b"VP8 " and chunk[3:6] == b"\x9d\x01\x2a":
                    w,h=struct.unpack("<HH",chunk[6:10]);dimensions(w & 0x3fff,h & 0x3fff);found=True
                elif kind == b"VP8L" and size >= 5 and chunk[0] == 0x2f:
                    bits=int.from_bytes(chunk[1:5],"little");dimensions(1+(bits & 0x3fff),1+((bits >> 14) & 0x3fff));found=True
                elif kind == b"ANMF" and size >= 24:
                    w=1+int.from_bytes(chunk[6:9],"little");h=1+int.from_bytes(chunk[9:12],"little");dimensions(w,h)
                    x=2*int.from_bytes(chunk[0:3],"little");y=2*int.from_bytes(chunk[3:6],"little")
                    if not canvas or not animated or x+w>canvas[0] or y+h>canvas[1]:raise ValueError()
                    frames+=1;pixels+=canvas[0]*canvas[1]
                    if frames>MAX_FRAMES or pixels>MAX_PIXELS:raise ValueError("Animation zu groß.")
                offset += 8 + size + size % 2
            if offset == len(data) and (found or (animated and frames)): return "image/webp"
    except (IndexError, struct.error):
        pass
    raise ValueError("Ungültiges Profilbild. PNG, JPEG, WebP oder GIF verwenden.")
