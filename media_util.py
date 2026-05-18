"""画像ファイルの拡張子・MIME・検索の共通定義。"""

from pathlib import Path

ALLOWED_IMAGE_EXTENSIONS = frozenset({"gif", "png", "jpg", "jpeg", "webp"})
ACCEPT_UPLOAD_ATTR = ".gif,.png,.jpg,.jpeg,.webp,image/*"
EXTENSIONS_LABEL = "GIF / PNG / JPEG / WebP"

MIME_BY_EXTENSION = {
    "gif": "image/gif",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}


def extension_from_filename(filename: str) -> str:
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].lower()


def is_allowed_image(filename: str) -> bool:
    return extension_from_filename(filename) in ALLOWED_IMAGE_EXTENSIONS


def stored_filename(file_id: str, ext: str) -> str:
    return f"{file_id}.{ext}"


def mimetype_for_filename(filename: str) -> str:
    return MIME_BY_EXTENSION.get(
        extension_from_filename(filename), "application/octet-stream"
    )


def find_images(source: Path, recursive: bool = False) -> list[Path]:
    found: dict[str, Path] = {}
    for ext in ALLOWED_IMAGE_EXTENSIONS:
        patterns = [f"**/*.{ext}", f"**/*.{ext.upper()}"] if recursive else [
            f"*.{ext}",
            f"*.{ext.upper()}",
        ]
        for pattern in patterns:
            for path in source.glob(pattern):
                if path.is_file():
                    found[str(path.resolve())] = path
    return sorted(found.values(), key=lambda p: str(p).lower())


def maybe_fix_gif_loop(path: Path) -> bool:
    if extension_from_filename(path.name) != "gif":
        return False
    from gif_util import ensure_gif_loops

    return ensure_gif_loops(path)
