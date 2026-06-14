"""Gera a arte do ícone do app (1024x1024 PNG) — tema WiFi sensing."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

S = 1024
BG1 = (26, 31, 39)     # topo
BG2 = (10, 12, 16)     # base
ACCENT = (233, 74, 18)  # laranja
ACCENT_LT = (255, 122, 54)


def _rounded_mask(size: int, radius: int) -> Image.Image:
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, size - 1, size - 1], radius, fill=255)
    return m


def main() -> None:
    img = Image.new("RGB", (S, S), BG2)
    d = ImageDraw.Draw(img)

    # Fundo com gradiente vertical sutil.
    for y in range(S):
        t = y / S
        c = tuple(int(BG1[i] + (BG2[i] - BG1[i]) * t) for i in range(3))
        d.line([(0, y), (S, y)], fill=c)

    # Brilho radial laranja atrás das ondas.
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    cx, cy = S // 2, int(S * 0.74)
    for r in range(420, 0, -8):
        a = int(70 * (1 - r / 420))
        gd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(233, 74, 18, a))
    img = Image.alpha_composite(img.convert("RGBA"), glow)
    d = ImageDraw.Draw(img)

    # Ondas de Wi-Fi (arcos concêntricos) emanando do ponto.
    radii = [150, 270, 390]
    widths = [40, 38, 36]
    for i, (r, w) in enumerate(zip(radii, widths)):
        col = ACCENT if i == 0 else ACCENT_LT if i == 2 else (244, 100, 40)
        d.arc([cx - r, cy - r, cx + r, cy + r], start=212, end=328, fill=col, width=w)

    # Ponto-fonte (a "antena").
    rr = 46
    d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=ACCENT)
    d.ellipse([cx - 18, cy - 18, cx + 18, cy + 18], fill=(255, 235, 225))

    # Marca de "movimento detectado": pequeno pulso verde no topo direito.
    d.ellipse([S - 250, 150, S - 130, 270], outline=(46, 204, 113), width=22)

    # Aplica máscara de cantos arredondados (estilo macOS).
    mask = _rounded_mask(S, 220)
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    out.paste(img.convert("RGBA"), (0, 0), mask)

    dst = Path(__file__).parent.parent / "icon.png"
    out.save(dst)
    print("OK ->", dst)


if __name__ == "__main__":
    main()
