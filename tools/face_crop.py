"""Recorta retratos centralizados no rosto usando MediaPipe (Tasks API).

Detecta o maior rosto com o modelo BlazeFace e gera um avatar quadrado frontal,
centralizado no rosto, para a página de apresentação.

Uso: python tools/face_crop.py <entrada> <saida> [tamanho]
"""

from __future__ import annotations

import sys
from pathlib import Path

import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from PIL import Image

_MODEL = Path(__file__).parent / "models" / "blaze_face_short_range.tflite"


def _detector() -> vision.FaceDetector:
    opts = vision.FaceDetectorOptions(
        base_options=python.BaseOptions(model_asset_path=str(_MODEL)),
        min_detection_confidence=0.4,
    )
    return vision.FaceDetector.create_from_options(opts)


def crop_to_face(src: str, dst: str, size: int = 440, margin: float = 0.9) -> None:
    """Detecta o maior rosto e salva um recorte quadrado centralizado nele."""
    img = Image.open(src).convert("RGB")
    w, h = img.size
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.array(img))

    with _detector() as det:
        result = det.detect(mp_image)
    if not result.detections:
        raise SystemExit(f"Nenhum rosto detectado em {src}")

    bb = max((d.bounding_box for d in result.detections),
             key=lambda b: b.width * b.height)
    cx = bb.origin_x + bb.width / 2
    cy = bb.origin_y + bb.height / 2 - bb.height * 0.05   # leve subida (testa)

    side = min(max(bb.width, bb.height) * (1 + margin), float(min(w, h)))
    left = min(max(cx - side / 2, 0), w - side)
    top = min(max(cy - side / 2, 0), h - side)

    out = img.crop((int(left), int(top), int(left + side), int(top + side)))
    out = out.resize((size, size), Image.LANCZOS)
    out.save(dst, quality=88)
    print(f"OK {Path(src).name} -> {dst} (face {bb.width}x{bb.height}px)")


if __name__ == "__main__":
    crop_to_face(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 440)
