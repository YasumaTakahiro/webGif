"""画像ファイルの拡張子・MIME・検索の共通定義。"""

import os
import re
import shutil
import tempfile
import uuid
from pathlib import Path

from werkzeug.utils import secure_filename

_UPLOAD_TMP = os.environ.get("WEBGIF_UPLOAD_TMP", "").strip()

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


_INVALID_FILENAME_CHARS = re.compile(r'[/\\:\0<>"|?*\x00-\x1f]')
_RESERVED_WIN_NAMES = re.compile(
    r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\.|$)", re.IGNORECASE
)
_MAX_BASENAME_LEN = 200


def _sanitize_stem(stem: str) -> str:
    """パス区切りなど危険文字だけ除去し、日本語は残す。"""
    return _INVALID_FILENAME_CHARS.sub("", stem).strip().strip(".")


def normalize_upload_filename(original: str) -> str | None:
    """アップロード元のファイル名を保存用に正規化。危険な名前は None。"""
    if not original or not str(original).strip():
        return None
    name = Path(original).name.strip()
    if not name or name in (".", "..") or ".." in name:
        return None

    ext = extension_from_filename(name)
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return None

    stem = _sanitize_stem(Path(name).stem)
    if not stem:
        ascii_safe = secure_filename(name)
        if (
            ascii_safe
            and ascii_safe not in (".", "..")
            and Path(ascii_safe).stem
            and extension_from_filename(ascii_safe) in ALLOWED_IMAGE_EXTENSIONS
        ):
            stem = Path(ascii_safe).stem
        else:
            return None

    if _RESERVED_WIN_NAMES.match(stem):
        return None
    if len(stem) > _MAX_BASENAME_LEN:
        stem = stem[:_MAX_BASENAME_LEN]

    result = f"{stem}.{ext}"
    if _RESERVED_WIN_NAMES.match(Path(result).stem):
        return None
    return result


def is_safe_stored_filename(filename: str) -> bool:
    """保存済みファイル名として配信してよいか（パストラバーサル等を拒否）。"""
    if not filename or filename in (".", ".."):
        return False
    if Path(filename).name != filename:
        return False
    return normalize_upload_filename(filename) == filename


def _filename_taken(
    filename: str, upload_dir: Path, conn, reserved: set[str]
) -> bool:
    if filename in reserved:
        return True
    if (upload_dir / filename).exists():
        return True
    return (
        conn.execute("SELECT 1 FROM gifs WHERE filename = ?", (filename,)).fetchone()
        is not None
    )


def allocate_stored_filename(
    original: str,
    upload_dir: Path,
    conn,
    *,
    reserved: set[str] | None = None,
) -> str:
    """uploads と DB で重複がなければ元のファイル名、なければ UUID 名を返す。"""
    reserved = reserved if reserved is not None else set()
    normalized = normalize_upload_filename(original)
    if normalized and not _filename_taken(normalized, upload_dir, conn, reserved):
        reserved.add(normalized)
        return normalized

    ext = extension_from_filename(original) or "gif"
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        ext = "gif"
    fallback = stored_filename(uuid.uuid4().hex, ext)
    reserved.add(fallback)
    return fallback


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


def save_upload_file(storage, dest: Path) -> None:
    """アップロードファイルを保存する。

    WEBGIF_UPLOAD_TMP が設定されているときは先にコンテナ内の tmp へ書き、
    完了後に uploads へ移動する（Dev Container の bind mount 書き込みを短くする）。
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if _UPLOAD_TMP:
        Path(_UPLOAD_TMP).mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=_UPLOAD_TMP, prefix="webgif-")
        os.close(fd)
        try:
            storage.save(tmp_path)
            shutil.move(tmp_path, dest)
        except Exception:
            Path(tmp_path).unlink(missing_ok=True)
            raise
    else:
        storage.save(dest)
