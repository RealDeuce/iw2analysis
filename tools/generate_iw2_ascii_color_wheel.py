#!/usr/bin/env python3
"""Generate an ImageWriter II text-glyph CMYK overstrike color wheel sample."""

from __future__ import annotations

import argparse
import math
from pathlib import Path


ESC = b"\x1b"

# ImageWriter II ESC K command digits.
YELLOW = 1
MAGENTA = 2
CYAN = 3
ORANGE = 4
GREEN = 5
PURPLE = 6
BLACK = 0


def esc(cmd: bytes) -> bytes:
    return ESC + cmd


def color(n: int) -> bytes:
    return ESC + b"K" + str(n).encode("ascii")


def hsv_to_rgb(hue: float, sat: float, val: float) -> tuple[float, float, float]:
    h = (hue % 1.0) * 6.0
    i = int(h)
    f = h - i
    p = val * (1.0 - sat)
    q = val * (1.0 - sat * f)
    t = val * (1.0 - sat * (1.0 - f))
    return [
        (val, t, p),
        (q, val, p),
        (p, val, t),
        (p, q, val),
        (t, p, val),
        (val, p, q),
    ][i % 6]


def rgb_to_cmyk(red: float, green: float, blue: float) -> tuple[float, float, float, float]:
    key = 1.0 - max(red, green, blue)
    if key >= 0.999:
        return 0.0, 0.0, 0.0, 1.0
    denom = 1.0 - key
    cyan = (1.0 - red - key) / denom
    magenta = (1.0 - green - key) / denom
    yellow = (1.0 - blue - key) / denom
    return cyan, magenta, yellow, key


def target_cmyk(dx: float, dy: float, radius_frac: float) -> tuple[float, float, float, float]:
    """Return process-ink coverages for a color-wheel cell.

    The wheel uses hue by angle with high saturation across the disk. A slight
    value falloff toward the rim lets black participate without dominating.
    """
    hue = (math.atan2(-dy, dx) / (math.pi * 2.0)) % 1.0
    sat = min(1.0, 0.90 + radius_frac * 0.10)
    val = 1.0 - 0.08 * (radius_frac ** 1.7)
    c, m, y, k = rgb_to_cmyk(*hsv_to_rgb(hue, sat, val))

    # The text glyphs have holes and do not cover a full cell, so push the ink
    # requests upward. The ramp and dithering below still keep light colors airy.
    scale = 1.18
    return (
        min(1.0, c * scale),
        min(1.0, m * scale),
        min(1.0, y * scale),
        min(1.0, k * 0.35),
    )


def dither(row: int, col: int, channel: int) -> float:
    # Deterministic 0..1 jitter, independent per ink channel.
    n = (row * 1103515245 + col * 12345 + channel * 2654435761) & 0xFFFFFFFF
    n ^= n >> 16
    return (n & 0xFFFF) / 65535.0


def glyph_for_amount(amount: float, row: int, col: int, channel: int) -> str | None:
    # Ordered roughly by visual coverage in the ImageWriter fixed-width font.
    ramp = ".,:;riIXS25A3hHMB#&0@"
    if amount < 0.025:
        return None
    noisy = amount + (dither(row, col, channel) - 0.5) / len(ramp)
    idx = max(0, min(len(ramp) - 1, round(noisy * (len(ramp) - 1))))
    return ramp[idx]


def generate() -> bytes:
    rows = 72
    cols = 78
    cx = (cols - 1) / 2.0
    cy = (rows - 1) / 2.0
    radius = min(cx, cy) - 1.0

    out = bytearray()
    out += esc(b"c")      # reset defaults
    out += esc(b"Q")      # 17 cpi ultracondensed
    out += esc(b"T08")    # 8/144 inch line spacing
    out += color(BLACK)
    out += b"\r\n"

    for row in range(rows):
        current = BLACK
        for col in range(cols):
            dx = col - cx
            dy = row - cy
            dist = math.hypot(dx, dy)
            if dist > radius:
                out += b" "
                continue

            c, m, y, k = target_cmyk(dx, dy, dist / radius)
            strikes: list[tuple[int, str]] = []
            for channel, (selection, amount) in enumerate(
                ((YELLOW, y), (CYAN, c), (MAGENTA, m), (BLACK, k))
            ):
                glyph = glyph_for_amount(amount, row, col, channel)
                if glyph is not None:
                    strikes.append((selection, glyph))

            if not strikes:
                out += b" "
                continue

            for idx, (selected, glyph) in enumerate(strikes):
                if selected != current:
                    out += color(selected)
                    current = selected
                if idx > 0:
                    out += b"\x08"
                out += glyph.encode("ascii")

        out += color(BLACK)
        out += b"\r\n"

    out += esc(b"A")      # restore default 6 lpi
    out += esc(b"N")      # restore pica
    out += color(BLACK)
    out += b"\r\n"
    return bytes(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "output",
        nargs="?",
        default="samples/iw2_ascii_color_wheel.bin",
        help="raw ImageWriter II input stream to write",
    )
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(generate())
    print(output)


if __name__ == "__main__":
    main()
