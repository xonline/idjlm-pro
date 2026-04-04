#!/usr/bin/env python3
"""
Generate IDLM Pro app icon — vinyl record + purple/teal gradient on dark bg.
Outputs: icon_1024.png, and icon.icns (macOS) via iconutil or sips.
"""

import math
import os
import struct
import subprocess
import sys
import zlib
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFilter
except ImportError:
    sys.exit("pip install Pillow")

SIZE = 1024
OUT_DIR = Path(__file__).parent


def lerp_colour(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def make_icon(size=1024) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx = cy = size // 2

    # ── Background rounded square ──────────────────────────────────────────
    # Radial gradient: #1a1033 → #0d1f2d
    bg = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    bg_draw = ImageDraw.Draw(bg)
    for r in range(size // 2, 0, -1):
        t = r / (size // 2)
        col = lerp_colour((26, 16, 51), (10, 18, 35), t)
        bg_draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col + (255,))

    # Round-rect mask
    radius = int(size * 0.22)
    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    img.paste(bg, (0, 0), mask=mask)

    # ── Outer vinyl grooves (subtle rings) ────────────────────────────────
    groove_count = 14
    for i in range(groove_count):
        r = int(size * (0.46 - i * 0.012))
        alpha = int(25 + i * 4)
        draw.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            outline=(180, 140, 255, alpha),
            width=max(1, size // 400),
        )

    # ── Label gradient disc (centre of vinyl) ─────────────────────────────
    label_r = int(size * 0.20)
    label_img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    label_draw = ImageDraw.Draw(label_img)
    for r in range(label_r, 0, -1):
        t = 1 - r / label_r
        col = lerp_colour((139, 92, 246), (6, 182, 212), t)  # purple → teal
        label_draw.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            fill=col + (255,),
        )
    img = Image.alpha_composite(img, label_img)
    draw = ImageDraw.Draw(img)

    # ── Glow behind label ─────────────────────────────────────────────────
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_r = int(size * 0.27)
    for r in range(glow_r, glow_r - 60, -1):
        alpha = int((glow_r - r) * 2.5)
        glow_draw.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            outline=(139, 92, 246, alpha),
            width=3,
        )
    glow = glow.filter(ImageFilter.GaussianBlur(radius=size // 40))
    img = Image.alpha_composite(img, glow)
    draw = ImageDraw.Draw(img)

    # ── Spindle hole ──────────────────────────────────────────────────────
    hole_r = int(size * 0.032)
    draw.ellipse(
        [cx - hole_r, cy - hole_r, cx + hole_r, cy + hole_r],
        fill=(12, 10, 24, 255),
    )

    # ── "AI" spark: 3 small teal dots arranged like a triangle ────────────
    # (subtle hint of intelligence inside the label)
    dot_r = int(size * 0.018)
    dot_dist = int(size * 0.09)
    for angle_deg in [90, 210, 330]:
        a = math.radians(angle_deg)
        dx = int(math.cos(a) * dot_dist)
        dy = int(math.sin(a) * dot_dist)
        draw.ellipse(
            [cx + dx - dot_r, cy + dy - dot_r, cx + dx + dot_r, cy + dy + dot_r],
            fill=(200, 255, 250, 230),
        )

    # ── White highlight (top-left gloss) ─────────────────────────────────
    gloss = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gloss_draw = ImageDraw.Draw(gloss)
    gloss_w = int(size * 0.55)
    gloss_h = int(size * 0.35)
    gloss_draw.ellipse(
        [cx - gloss_w, cy - size // 2 - gloss_h // 2,
         cx + gloss_w // 4, cy - size // 2 + gloss_h],
        fill=(255, 255, 255, 22),
    )
    gloss = gloss.filter(ImageFilter.GaussianBlur(radius=size // 20))
    # Crop to rounded rect
    gloss_arr = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gloss_arr.paste(gloss, (0, 0), mask=mask)
    img = Image.alpha_composite(img, gloss_arr)

    return img


def write_png(img: Image.Image, path: Path):
    img.save(str(path), "PNG")
    print(f"  Saved {path} ({path.stat().st_size // 1024} KB)")


def make_icns(png_1024: Path, out: Path):
    """Build .icns using iconutil (macOS) or a manual fallback."""
    iconset = out.parent / "icon.iconset"
    iconset.mkdir(exist_ok=True)

    sizes = [16, 32, 64, 128, 256, 512, 1024]
    base = Image.open(str(png_1024)).convert("RGBA")

    for s in sizes:
        resized = base.resize((s, s), Image.LANCZOS)
        fname = f"icon_{s}x{s}.png" if s < 1024 else "icon_512x512@2x.png"
        resized.save(str(iconset / fname))
        if s <= 512:
            resized2 = base.resize((s * 2, s * 2), Image.LANCZOS)
            resized2.save(str(iconset / f"icon_{s}x{s}@2x.png"))

    try:
        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset), "-o", str(out)],
            check=True, capture_output=True,
        )
        print(f"  Saved {out} (macOS iconutil)")
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fallback: simple .icns with just the 1024 PNG (good enough for PyInstaller)
        print("  iconutil not available — writing minimal .icns fallback")
        _write_minimal_icns(base, out)

    # Clean up iconset dir
    import shutil
    shutil.rmtree(str(iconset), ignore_errors=True)


def _write_minimal_icns(img: Image.Image, out: Path):
    """Write a minimal .icns containing ic10 (1024×1024) only."""
    import io
    buf = io.BytesIO()
    img.resize((1024, 1024), Image.LANCZOS).save(buf, "PNG")
    png_data = buf.getvalue()

    # icns format: magic + file_size + (type + size + data)...
    icon_type = b"ic10"
    chunk_size = 8 + len(png_data)
    file_size = 8 + chunk_size

    with open(str(out), "wb") as f:
        f.write(b"icns")
        f.write(struct.pack(">I", file_size))
        f.write(icon_type)
        f.write(struct.pack(">I", chunk_size))
        f.write(png_data)


def make_ico(png_1024: Path, out: Path):
    """Write a proper multi-resolution .ico for Windows (PNG-in-ICO format)."""
    import io
    base = Image.open(str(png_1024)).convert("RGBA")
    sizes = [256, 128, 64, 48, 32, 16]

    pngs = []
    for s in sizes:
        buf = io.BytesIO()
        base.resize((s, s), Image.LANCZOS).save(buf, "PNG")
        pngs.append(buf.getvalue())

    n = len(sizes)
    header_size = 6 + n * 16
    offset = header_size

    with open(str(out), "wb") as f:
        # ICONDIR header
        f.write(struct.pack("<HHH", 0, 1, n))
        # ICONDIRENTRY per size (256 stored as 0 per spec)
        for s, png in zip(sizes, pngs):
            w = 0 if s == 256 else s
            f.write(struct.pack("<BBBBHHII", w, w, 0, 0, 1, 32, len(png), offset))
            offset += len(png)
        for png in pngs:
            f.write(png)

    print(f"  Saved {out} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    print("Generating IDLM Pro icon…")
    icon = make_icon(SIZE)
    png_path = OUT_DIR / "icon_1024.png"
    write_png(icon, png_path)

    icns_path = OUT_DIR / "icon.icns"
    make_icns(png_path, icns_path)

    ico_path = OUT_DIR / "icon.ico"
    make_ico(png_path, ico_path)

    # Also write a 256 px version for README/marketing
    small = icon.resize((256, 256), Image.LANCZOS)
    write_png(small, OUT_DIR / "icon_256.png")

    print("Done.")
