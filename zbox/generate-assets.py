#!/usr/bin/env python3
"""Generate ZBOX SVG logos (ZMAX design system), raster PNG/ICO icons, and NSIS installer bitmaps
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


def grad3(c0, c1, c2, t: float):
    t = max(0.0, min(1.0, t))
    if t <= 0.45:
        u = t / 0.45
        return (int(round(lerp(c0[0], c1[0], u))), int(round(lerp(c0[1], c1[1], u))), int(round(lerp(c0[2], c1[2], u))))
    u = (t - 0.45) / 0.55
    return (int(round(lerp(c1[0], c2[0], u))), int(round(lerp(c1[1], c2[1], u))), int(round(lerp(c1[2], c2[2], u))))


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


def in_zmax_z(nx: float, ny: float) -> bool:
    """ZMAX signature skewed-Z with dynamic curved speed-slash cut in [0, 1] x [0, 1]."""
    # Map normalized [0,1] into ZMAX's 100x100 mark space, then into Z local space
    # Mark transform: translate(13 24) scale(0.5) translate(20 2) -> origin (23, 25), scale 0.5
    mx = nx * 100.0
    my = ny * 100.0
    lx = (mx - 23.0) / 0.5
    ly = (my - 25.0) / 0.5

    # Speed-slash arc curve: y_cut(x) approx from (-20, 104) through (40, 62) to (132, 42)
    t_arc = max(0.0, min(1.0, (lx + 20.0) / 152.0))
    y_cut = 104.0 * (1 - t_arc) ** 2 + 2 * 56.0 * (1 - t_arc) * t_arc + 42.0 * t_arc ** 2

    # Thin glowing swoosh ribbon inside the cut
    if -14.0 <= lx <= 122.0 and abs(ly - (y_cut + 2.5)) <= 2.2:
        return True

    # Cutout gap across the Z
    if abs(ly - y_cut) <= 5.5:
        return False

    # Inverse of translate(32 0) skewX(-18): x_orig = lx - 32 + tan(18 deg) * ly
    zx = lx - 32.0 + math.tan(math.radians(18.0)) * ly
    zy = ly

    if zx < 0.0 or zx > 100.0 or zy < 0.0 or zy > 100.0:
        return False
    # Top bar
    if zy <= 24.0:
        return True
    # Bottom bar
    if zy >= 76.0:
        return True
    # Diagonal bar: from (58,24)-(100,24) down to (0,76)-(42,76)
    u = (zy - 24.0) / 52.0
    left = 58.0 * (1.0 - u)
    right = 100.0 - 58.0 * u
    return left <= zx <= right


def render_icon(size: int, transparent_bg: bool = False) -> bytes:
    bg = hex_rgb(C["bg"])
    ac0 = hex_rgb(C["accent"])
    ac1 = hex_rgb(C["accentMid"])
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
                    # Diagonal gradient t from bottom-left (0,1) to top-right (1,0)
                    gt = (nx * 0.72 + (1.0 - ny) * 0.68) / 1.15
                    if transparent_bg:
                        if in_zmax_z(nx, ny):
                            c = grad3(ac0, ac1, ac2, gt)
                            r_acc += c[0]
                            g_acc += c[1]
                            b_acc += c[2]
                            a_acc += 255.0
                    else:
                        if in_rounded_rect(nx, ny, 0.02, 0.02, 0.98, 0.98, 0.24):
                            if in_zmax_z(nx, ny):
                                c = grad3(ac0, ac1, ac2, gt)
                            else:
                                # Subtle ZMAX top-right radial glow on #05080F
                                d = math.hypot((nx - 0.85) / 0.9, (ny - 0.10) / 0.9)
                                glow = max(0.0, 1.0 - d) ** 1.6 * 0.30
                                c = (
                                    int(round(lerp(bg[0], ac1[0], glow))),
                                    int(round(lerp(bg[1], ac1[1], glow))),
                                    int(round(lerp(bg[2], ac1[2], glow))),
                                )
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
    ac0, ac1, ac2, bg = C["accent"], C["accentMid"], C["accent2"], C["bg"]

    defs = f"""<defs>
  <linearGradient id="gMark" gradientUnits="userSpaceOnUse" x1="-10" y1="104" x2="128" y2="0">
    <stop offset="0" stop-color="{ac0}"/>
    <stop offset="0.45" stop-color="{ac1}"/>
    <stop offset="1" stop-color="{ac2}"/>
  </linearGradient>
  <linearGradient id="gX" x1="0" y1="1" x2="1" y2="0">
    <stop offset="0" stop-color="{ac1}"/>
    <stop offset="1" stop-color="{ac2}"/>
  </linearGradient>
  <mask id="mCut" maskUnits="userSpaceOnUse" x="-20" y="-2" width="150" height="108">
    <rect x="-20" y="-2" width="150" height="108" fill="#fff"/>
    <path d="M-20 104C14 74 58 54 132 42" fill="none" stroke="#000" stroke-width="11"/>
  </mask>
  <radialGradient id="glow" cx="0.85" cy="0.1" r="0.9">
    <stop offset="0" stop-color="{ac1}" stop-opacity="0.5"/>
    <stop offset="1" stop-color="{ac1}" stop-opacity="0"/>
  </radialGradient>
</defs>"""

    # Exact ZMAX mark geometry
    mark_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 100 100" role="img" aria-label="{NAME}">
{defs}
  <rect width="100" height="100" rx="24" fill="{bg}"/>
  <rect width="100" height="100" rx="24" fill="url(#glow)" opacity="0.6"/>
  <g transform="translate(13 24) scale(0.5) translate(20 2)">
    <g mask="url(#mCut)"><path d="M0 0H100V24L42 76H100V100H0V76L58 24H0Z" transform="translate(32 0) skewX(-18)" fill="url(#gMark)"/></g>
    <path d="M-14 100C20 72 60 54 126 43C66 58 26 76 -14 100Z" fill="url(#gMark)"/>
  </g>
</svg>
"""

    tray_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 100 100" role="img" aria-label="{NAME}">
{defs}
  <g transform="translate(6 14) scale(0.64) translate(20 2)">
    <g mask="url(#mCut)"><path d="M0 0H100V24L42 76H100V100H0V76L58 24H0Z" transform="translate(32 0) skewX(-18)" fill="url(#gMark)"/></g>
    <path d="M-14 100C20 72 60 54 126 43C66 58 26 76 -14 100Z" fill="url(#gMark)"/>
  </g>
</svg>
"""

    # Exact ZMAX geometric vector wordmark style: Z - B O X with skewX(-14) and signature electric-blue X slash
    def zbox_letters(fill: str) -> str:
        return f"""<g transform="scale(0.92) skewX(-14)">
    <!-- Z -->
    <path d="M0 0H72V18L25 82H72V100H0V82L47 18H0Z" transform="translate(0 0)" fill="{fill}" fill-rule="evenodd"/>
    <!-- - -->
    <path d="M0 42H28V58H0Z" transform="translate(82 0)" fill="{fill}"/>
    <!-- B -->
    <path d="M0 0H58C72 0 80 8 80 22C80 34 73 43 62 47C75 51 84 60 84 74C84 90 73 100 56 100H0ZM22 18V41H52C57 41 60 37 60 30C60 22 57 18 52 18ZM22 58V82H54C60 82 63 78 63 70C63 62 60 58 54 58Z" transform="translate(120 0)" fill="{fill}" fill-rule="evenodd"/>
    <!-- O -->
    <path d="M44 0C72 0 88 18 88 50C88 82 72 100 44 100C16 100 0 82 0 50C0 18 16 0 44 0ZM44 19C29 19 22 30 22 50C22 70 29 81 44 81C59 81 66 70 66 50C66 30 59 19 44 19Z" transform="translate(216 0)" fill="{fill}" fill-rule="evenodd"/>
    <!-- X (ZMAX signature ascending electric slash) -->
    <path d="M0 0H24L90 100H66Z" transform="translate(316 0)" fill="{fill}"/>
    <path d="M0 100H24L112 -10H88Z" transform="translate(316 0)" fill="url(#gX)"/>
  </g>"""

    def wordmark(text_fill: str) -> str:
        return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="-26 -16 440 120" role="img" aria-label="{NAME}">
{defs}
  <g transform="translate(4 6)">
    {zbox_letters(text_fill)}
  </g>
</svg>
"""

    logo_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="240" viewBox="0 -14 640 120" role="img" aria-label="{NAME}">
{defs}
  <g transform="translate(0 0) scale(1) translate(20 2)">
    <g mask="url(#mCut)"><path d="M0 0H100V24L42 76H100V100H0V76L58 24H0Z" transform="translate(32 0) skewX(-18)" fill="url(#gMark)"/></g>
    <path d="M-14 100C20 72 60 54 126 43C66 58 26 76 -14 100Z" fill="url(#gMark)"/>
  </g>
  <g transform="translate(195 9)">
    {zbox_letters("#ffffff")}
  </g>
</svg>
"""

    for rel, content in [
        ("ui/img/mark.svg", mark_svg),
        ("ui/img/wordmark.svg", wordmark("#ffffff")),
        ("ui/img/wordmark-dark.svg", wordmark("#05080F")),
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

    write_png(os.path.join(icons_dir, "tray.png"), 64, 64, render_icon(64, transparent_bg=True))

    ico_entries: list[tuple[int, bytes]] = []
    for sz in (16, 24, 32, 48, 64, 128, 256):
        rgba = cache.get(sz) or render_icon(sz, transparent_bg=False)
        tmp = os.path.join(icons_dir, f".tmp_{sz}.png")
        write_png(tmp, sz, sz, rgba)
        with open(tmp, "rb") as f:
            ico_entries.append((sz, f.read()))
        os.remove(tmp)
    write_ico(os.path.join(icons_dir, "icon.ico"), ico_entries)

    # NSIS header (150x57) and sidebar (164x314) in ZMAX obsidian + electric cyan->royal gradient bar
    bg = hex_rgb(C["bg"])
    card = hex_rgb(C["card2"])
    ac0 = hex_rgb(C["accent"])
    ac1 = hex_rgb(C["accentMid"])
    ac2 = hex_rgb(C["accent2"])

    for fname, w, h in [("header.bmp", 150, 57), ("sidebar.bmp", 164, 314)]:
        rgb = bytearray(w * h * 3)
        for y in range(h):
            t = y / max(1, h - 1)
            base = (int(round(lerp(card[0], bg[0], t))), int(round(lerp(card[1], bg[1], t))), int(round(lerp(card[2], bg[2], t))))
            for x in range(w):
                if (fname == "header.bmp" and y >= h - 3) or (fname == "sidebar.bmp" and x < 4):
                    c = grad3(ac0, ac1, ac2, x / max(1, w - 1) if fname == "header.bmp" else t)
                else:
                    c = base
                i = (y * w + x) * 3
                rgb[i], rgb[i + 1], rgb[i + 2] = c
        write_bmp24(os.path.join(ROOT, "src-tauri", "installer", fname), w, h, bytes(rgb))


if __name__ == "__main__":
    generate_svgs()
    generate_rasters()
    print(f"Generated ZBOX (ZMAX standard) assets for '{NAME}' ({C['accent']} -> {C['accentMid']} -> {C['accent2']} on {C['bg']}).")
