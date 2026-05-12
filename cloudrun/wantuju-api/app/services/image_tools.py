"""Deterministic image tools."""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import logging
import re

from PIL import Image, ImageOps

from app.cloudbase.storage import CloudBaseStorage
from app.services.poster import download_image_bytes


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ImageToolResult:
    poster_file_id: str
    result_file_ids: list[str]
    result_mode: str


def process_image_tool(
    job_type: str,
    task_id: str,
    image_urls: list[str],
    param: dict | None = None,
    storage: CloudBaseStorage | None = None,
) -> ImageToolResult:
    storage = storage or CloudBaseStorage()
    if job_type == "split":
        return split_image(task_id, image_urls, param or {}, storage)
    if job_type == "long_image":
        return stitch_long_image(task_id, image_urls, storage)
    raise ValueError(f"不支持的图片工具类型: {job_type}")


def split_image(task_id: str, image_urls: list[str], param: dict, storage: CloudBaseStorage) -> ImageToolResult:
    if not image_urls:
        raise ValueError("缺少待切分图片")

    rows, cols = parse_grid(str(param.get("grid") or "3x3"))
    image = load_image(image_urls[0])
    width, height = image.size
    pieces: list[Image.Image] = []

    for row in range(rows):
        for col in range(cols):
            left = round(width * col / cols)
            upper = round(height * row / rows)
            right = round(width * (col + 1) / cols)
            lower = round(height * (row + 1) / rows)
            pieces.append(image.crop((left, upper, right, lower)))

    encoded_pieces = [encode_jpeg(piece) for piece in pieces]
    preview_bytes = encode_jpeg(build_split_preview(pieces, rows, cols))
    result_file_ids: list[str] = []
    try:
        for index, piece_bytes in enumerate(encoded_pieces, start=1):
            result_file_ids.append(
                storage.upload_bytes(
                    f"image-tools/{task_id}/split-{index:02d}.jpg",
                    piece_bytes,
                    "image/jpeg",
                )
            )

        poster_file_id = storage.upload_bytes(
            f"image-tools/{task_id}/preview.jpg",
            preview_bytes,
            "image/jpeg",
        )
    except Exception:
        cleanup_uploaded_files(storage, result_file_ids)
        raise
    return ImageToolResult(poster_file_id=poster_file_id, result_file_ids=result_file_ids, result_mode="multiple")


def stitch_long_image(task_id: str, image_urls: list[str], storage: CloudBaseStorage) -> ImageToolResult:
    if len(image_urls) < 2:
        raise ValueError("长图拼接至少需要2张图片")

    images = [load_image(url) for url in image_urls[:9]]
    target_width = min(max(min(image.width for image in images), 360), 1600)
    resized = [resize_to_width(image, target_width) for image in images]
    total_height = sum(image.height for image in resized)
    canvas = Image.new("RGB", (target_width, total_height), "#ffffff")

    y = 0
    for image in resized:
        canvas.paste(image, (0, y))
        y += image.height

    poster_file_id = storage.upload_bytes(
        f"image-tools/{task_id}/long-image.jpg",
        encode_jpeg(canvas, quality=90),
        "image/jpeg",
    )
    return ImageToolResult(poster_file_id=poster_file_id, result_file_ids=[], result_mode="single")


def parse_grid(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"\s*([1-4])\s*[xX×]\s*([1-4])\s*", value)
    if not match:
        raise ValueError("切分规格不正确")
    rows = int(match.group(1))
    cols = int(match.group(2))
    if rows * cols < 2 or rows * cols > 12:
        raise ValueError("切分规格不支持")
    return rows, cols


def load_image(url: str) -> Image.Image:
    image_bytes = download_image_bytes(url)
    image = Image.open(BytesIO(image_bytes))
    image = ImageOps.exif_transpose(image)
    return image.convert("RGB")


def resize_to_width(image: Image.Image, width: int) -> Image.Image:
    if image.width == width:
        return image
    height = max(1, round(image.height * width / image.width))
    return image.resize((width, height), Image.Resampling.LANCZOS)


def build_split_preview(pieces: list[Image.Image], rows: int, cols: int) -> Image.Image:
    thumb_width = 360
    gap = 10
    thumbs = [resize_to_width(piece, thumb_width) for piece in pieces]
    row_heights = [
        max(thumbs[row * cols + col].height for col in range(cols))
        for row in range(rows)
    ]
    canvas_width = cols * thumb_width + (cols - 1) * gap
    canvas_height = sum(row_heights) + (rows - 1) * gap
    canvas = Image.new("RGB", (canvas_width, canvas_height), "#f7f7f7")

    y = 0
    for row in range(rows):
        x = 0
        for col in range(cols):
            thumb = thumbs[row * cols + col]
            canvas.paste(thumb, (x, y))
            x += thumb_width + gap
        y += row_heights[row] + gap
    return canvas


def encode_jpeg(image: Image.Image, quality: int = 92) -> bytes:
    output = BytesIO()
    image.save(output, format="JPEG", quality=quality, optimize=True)
    return output.getvalue()


def cleanup_uploaded_files(storage: CloudBaseStorage, file_ids: list[str]) -> None:
    if not file_ids:
        return
    try:
        storage.delete_objects(file_ids)
    except Exception as exc:
        logger.warning("清理工具输出文件失败: %s", exc)
