#!/usr/bin/env python3
"""Generate ZBOX SVG logos, raster PNG/ICO icons, and NSIS installer bitmaps
from zbox/brand.json using only Python's standard library (zero pip deps).

Usage:
  python zbox/generate-assets.py
"""

import json
import math
import os
import struct
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRAND = json.load(open(os.path.join(ROOT, "zbox", "brand.json"), encoding="utf-8"))
C = BRAND["colors"]
NAME = BRAND["name"]


def hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * max(0.0, min(1.0, t))


def lerp_rgb(c1, c2, t):
    return (
        int(round(lerp(c1[0], c2[0], t))),
        int(round(lerp(c1[1], c2[1], t))),
        int(round(lerp(c1[2], c2[2], t))),
    )


def write_png(path: str, w: int, h: int, rgba: bytes) -> None:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = bytearray()
    stride = w * 4
    for y in range(h):
        raw.append(0)
        raw.extend(rgba[y * stride : (y + 1) * stride])
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def write_bmp24(path: str, w: int, h: int, rgb: bytes) -> None:
    row_pad = (4 - (w * 3) % 4) % 4
    img_size = (w * 3 + row_pad) * h
    file_size = 54 + img_size
    hdr = struct.pack("<2sIHHI", b"BM", file_size, 0, 0, 54)
    dib = struct.pack("<IIIHHIIIIII", 40, w, h, 1, 24, 0, img_size, 2835, 2835, 0, 0)
    out = bytearray(hdr + dib)
    for y in range(h - 1, -1, -1):
        base = y * w * 3
        for x in range(w):
            i = base + x * 3
            out.extend((rgb[i + 2], rgb[i + 1], rgb[i]))
        out.extend(b"\x00" * row_pad)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(out)


def write_ico(path: str, png_entries: list[tuple[int, bytes]]) -> None:
    count = len(png_entries)
    header = struct.pack("<HHH", 0, 1, count)
    offset = 6 + 16 * count
    directory = bytearray()
    blobs = bytearray()
    for size, png_bytes in png_entries:
        dim = 0 if size >= 256 else size
        directory.extend(struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(png_bytes), offset))
        blobs.extend(png_bytes)
        offset += len(png_bytes)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(header + directory + blobs)


def in_rounded_rect(x: float, y: float, x0: float, y0: float, x1: float, y1: float, r: float) -> bool:
    if x < x0 or x > x1 or y < y0 or y > y1:
        return False
    cx = max(x0 + r, min(x, x1 - r))
    cy = max(y0 + r, min(y, y1 - r))
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def in_z_glyph(nx: float, ny: float) -> bool:
    """Geometric ZBOX 'Z' glyph in normalized [0, 1] x [0, 1] coordinates."""
    # Top bar
    if 0.20 <= nx <= 0.80 and 0.21 <= ny <= 0.34:
        return True
    # Bottom bar
    if 0.20 <= nx <= 0.80 and 0.66 <= ny <= 0.79:
        return True
    # Diagonal bar connecting top-right (0.78, 0.30) to bottom-left (0.22, 0.70)
    if 0.22 <= ny <= 0.78:
        t = (ny - 0.28) / (0.72 - 0.28)
        cx = 0.74 - t * (0.74 - 0.26)
        if abs(nx - cx) <= 0.095:
            return True
    return False


def render_icon(size: int, transparent_bg: bool = False) -> bytes:
    bg1 = hex_rgb(C["card"])
    bg2 = hex_rgb(C["bg"])
    ac1 = hex_rgb(C["accent"])
    ac2 = hex_rgb(C["accent2"])
    samples = 4 if size <= 128 else 2
    inv_s = 1.0 / samples
    inv_n = 1.0 / (samples * samples)
    buf = bytearray(size * size * 4)

    for py in range(size):
        for px in range(size):
            r_acc = g_acc = b_acc = a_acc = 0.0
            for sy in range(samples):
                ny = (py + (sy + 0.5) * inv_s) / size
                for sx in range(samples):
                    nx = (px + (sx + 0.5) * inv_s) / size
                    if transparent_bg:
                        # Tray icon: pure accent Z + outer frame
                        outer = in_rounded_rect(nx, ny, 0.08, 0.08, 0.92, 0.92, 0.20)
                        inner = in_rounded_rect(nx, ny, 0.16, 0.16, 0.84, 0.84, 0.14)
                        if (outer and not inner) or in_z_glyph(nx, ny):
                            c = lerp_rgb(ac1, ac2, ny)
                            r_acc += c[0]
                            g_acc += c[1]
                            b_acc += c[2]
                            a_acc += 255.0
                    else:
                        if in_rounded_rect(nx, ny, 0.04, 0.04, 0.96, 0.96, 0.22):
                            border = not in_rounded_rect(nx, ny, 0.09, 0.09, 0.91, 0.91, 0.17)
                            if in_z_glyph(nx, ny) or border:
                                c = lerp_rgb(ac1, ac2, (ny - 0.15) / 0.70)
                            else:
                                c = lerp_rgb(bg1, bg2, ny)
                            r_acc += c[0]
                            g_acc += c[1]
                            b_acc += c[2]
                            a_acc += 255.0
            i = (py * size + px) * 4
            if a_acc > 0:
                buf[i] = int(round(r_acc / (a_acc / 255.0)))
                buf[i + 1] = int(round(g_acc / (a_acc / 255.0)))
                buf[i + 2] = int(round(b_acc / (a_acc / 255.0)))
                buf[i + 3] = int(round(a_acc * inv_n))
    return bytes(buf)


def generate_svgs() -> None:
    ac1, ac2, bg, card = C["accent"], C["accent2"], C["bg"], C["card"]

    mark_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" role="img" aria-label="{NAME}">
<defs>
  <linearGradient id="zg" x1="0" y1="24" x2="256" y2="232" gradientUnits="userSpaceOnUse">
    <stop offset="0" stop-color="{ac1}"/>
    <stop offset="1" stop-color="{ac2}"/>
  </linearGradient>
</defs>
<rect x="14" y="14" width="228" height="228" rx="52" fill="{card}" stroke="url(#zg)" stroke-width="14"/>
<path fill="url(#zg)" d="M56 60H200V88L108 168H200V196H56V168L148 88H56Z"/>
</svg>
"""

    tray_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" role="img" aria-label="{NAME}">
<defs>
  <linearGradient id="zg" x1="0" y1="24" x2="256" y2="232" gradientUnits="userSpaceOnUse">
    <stop offset="0" stop-color="{ac1}"/>
    <stop offset="1" stop-color="{ac2}"/>
  </linearGradient>
</defs>
<rect x="20" y="20" width="216" height="216" rx="48" fill="none" stroke="url(#zg)" stroke-width="20"/>
<path fill="url(#zg)" d="M58 62H198V90L110 166H198V194H58V166L146 90H58Z"/>
</svg>
"""

    def wordmark(text_fill: str) -> str:
        return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 540 120" role="img" aria-label="{NAME}">
<defs>
  <linearGradient id="zg" x1="0" y1="10" x2="0" y2="110" gradientUnits="userSpaceOnUse">
    <stop offset="0" stop-color="{ac1}"/>
    <stop offset="1" stop-color="{ac2}"/>
  </linearGradient>
</defs>
<text x="4" y="96" font-family="Archivo, 'Segoe UI', system-ui, sans-serif" font-weight="900" font-size="104" letter-spacing="8">
  <tspan fill="url(#zg)">Z</tspan><tspan fill="{text_fill}">BOX</tspan>
</text>
</svg>
"""

    logo_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 840 256" role="img" aria-label="{NAME}">
<defs>
  <linearGradient id="zg" x1="0" y1="24" x2="256" y2="232" gradientUnits="userSpaceOnUse">
    <stop offset="0" stop-color="{ac1}"/>
    <stop offset="1" stop-color="{ac2}"/>
  </linearGradient>
</defs>
<rect x="14" y="14" width="228" height="228" rx="52" fill="{card}" stroke="url(#zg)" stroke-width="14"/>
<path fill="url(#zg)" d="M56 60H200V88L108 168H200V196H56V168L148 88H56Z"/>
<text x="292" y="178" font-family="Archivo, 'Segoe UI', system-ui, sans-serif" font-weight="900" font-size="146" letter-spacing="10">
  <tspan fill="url(#zg)">Z</tspan><tspan fill="#FFFFFF">BOX</tspan>
</text>
</svg>
"""

    for rel, content in [
        ("ui/img/mark.svg", mark_svg),
        ("ui/img/wordmark.svg", wordmark("#FFFFFF")),
        ("ui/img/wordmark-dark.svg", wordmark("#0E1626")),
        ("ui/img/logo.svg", logo_svg),
        ("src-tauri/icons/icon.svg", mark_svg),
        ("src-tauri/icons/tray.svg", tray_svg),
    ]:
        with open(os.path.join(ROOT, rel), "w", encoding="utf-8", newline="\n") as f:
            f.write(content)


def generate_rasters() -> None:
    icons_dir = os.path.join(ROOT, "src-tauri", "icons")
    sizes = {
        "32x32.png": 32,
        "64x64.png": 64,
        "128x128.png": 128,
        "128x128@2x.png": 256,
        "icon.png": 512,
        "Square30x30Logo.png": 30,
        "Square44x44Logo.png": 44,
        "Square71x71Logo.png": 71,
        "Square89x89Logo.png": 89,
        "Square107x107Logo.png": 107,
        "Square142x142Logo.png": 142,
        "Square150x150Logo.png": 150,
        "Square284x284Logo.png": 284,
        "Square310x310Logo.png": 310,
        "StoreLogo.png": 50,
    }
    cache: dict[int, bytes] = {}
    for fname, sz in sizes.items():
        if sz not in cache:
            cache[sz] = render_icon(sz, transparent_bg=False)
        write_png(os.path.join(icons_dir, fname), sz, sz, cache[sz])

    # Tray PNG
    write_png(os.path.join(icons_dir, "tray.png"), 64, 64, render_icon(64, transparent_bg=True))

    # Multi-resolution Windows ICO (16, 24, 32, 48, 64, 128, 256)
    ico_entries: list[tuple[int, bytes]] = []
    for sz in (16, 24, 32, 48, 64, 128, 256):
        rgba = cache.get(sz) or render_icon(sz, transparent_bg=False)
        tmp = os.path.join(icons_dir, f".tmp_{sz}.png")
        write_png(tmp, sz, sz, rgba)
        with open(tmp, "rb") as f:
            ico_entries.append((sz, f.read()))
        os.remove(tmp)
    write_ico(os.path.join(icons_dir, "icon.ico"), ico_entries)

    # NSIS header (150x57) and sidebar (164x314) bitmaps
    bg = hex_rgb(C["bg"])
    card = hex_rgb(C["card2"])
    ac1 = hex_rgb(C["accent"])
    ac2 = hex_rgb(C["accent2"])

    for fname, w, h in [("header.bmp", 150, 57), ("sidebar.bmp", 164, 314)]:
        rgb = bytearray(w * h * 3)
        for y in range(h):
            t = y / max(1, h - 1)
            base = lerp_rgb(card, bg, t)
            for x in range(w):
                # Subtle accent bar on the bottom (header) or left (sidebar)
                if (fname == "header.bmp" and y >= h - 3) or (fname == "sidebar.bmp" and x < 4):
                    c = lerp_rgb(ac1, ac2, x / max(1, w - 1) if fname == "header.bmp" else t)
                else:
                    c = base
                i = (y * w + x) * 3
                rgb[i], rgb[i + 1], rgb[i + 2] = c
        write_bmp24(os.path.join(ROOT, "src-tauri", "installer", fname), w, h, bytes(rgb))


if __name__ == "__main__":
    generate_svgs()
    generate_rasters()
    print(f"Generated ZBOX assets for '{NAME}' ({C['accent']} / {C['bg']}).")
