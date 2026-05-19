"""Feature preview image composition helpers."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from uuid import uuid4
from typing import BinaryIO

from PIL import Image, ImageFilter, ImageOps


SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_IMAGE_PIXELS = 16_000_000


def _ensure_reasonable_dimensions(image: Image.Image, label: str) -> None:
    width, height = image.size
    if width <= 0 or height <= 0:
        raise ValueError(f"{label} 尺寸无效")
    if width * height > MAX_IMAGE_PIXELS:
        raise ValueError(f"{label} 像素过大，请上传不超过 1600 万像素的图片")


def compose_preview_image(
    *,
    original_file: BinaryIO,
    generated_file: BinaryIO,
    inset_ratio: float = 0.24,
    margin_ratio: float = 0.05,
    border_ratio: float = 0.006,
    shadow_ratio: float = 0.012,
) -> bytes:
    """Overlay the original image as a framed inset on generated image."""
    with Image.open(generated_file) as generated_raw:
        _ensure_reasonable_dimensions(generated_raw, "生成后的图片")
        generated = ImageOps.exif_transpose(generated_raw).convert("RGB")

    with Image.open(original_file) as original_raw:
        _ensure_reasonable_dimensions(original_raw, "原图")
        original = ImageOps.exif_transpose(original_raw).convert("RGB")

    base_width, base_height = generated.size
    inset_width = max(96, int(base_width * inset_ratio))
    inset_height = max(96, int(inset_width * original.height / original.width))

    max_inset_height = int(base_height * 0.32)
    if inset_height > max_inset_height:
        inset_height = max(96, max_inset_height)
        inset_width = max(96, int(inset_height * original.width / original.height))

    inset = original.resize((inset_width, inset_height), Image.Resampling.LANCZOS)

    border = max(2, int(base_width * border_ratio))
    framed = ImageOps.expand(inset, border=border, fill=(255, 255, 255))

    shadow_offset = max(3, int(base_width * shadow_ratio))
    shadow_blur = max(8, int(base_width * shadow_ratio * 1.6))
    shadow = Image.new("RGBA", framed.size, (0, 0, 0, 88))
    shadow = shadow.filter(ImageFilter.GaussianBlur(shadow_blur))

    composed = generated.convert("RGBA")
    margin = max(16, int(base_width * margin_ratio))
    x = max(0, base_width - framed.width - margin)
    y = margin

    composed.alpha_composite(shadow, (x + shadow_offset, y + shadow_offset))
    composed.alpha_composite(framed.convert("RGBA"), (x, y))

    output = BytesIO()
    composed.convert("RGB").save(output, format="JPEG", quality=92, optimize=True, progressive=True)
    return output.getvalue()


def safe_preview_object_id(filename: str) -> str:
    """Build a stable CloudBase storage object path for a composed preview."""
    stem = Path(filename).stem.strip().lower()
    safe = "".join(char if char.isascii() and (char.isalnum() or char in {"-", "_"}) else "-" for char in stem)
    safe = "-".join(part for part in safe.split("-") if part)[:48] or "preview"
    return f"preview-image/{safe}-{uuid4().hex[:8]}.jpg"
