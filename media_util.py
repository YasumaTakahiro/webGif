"""画像ファイルの拡張子・MIME・検索の共通定義。"""

import hashlib
import os
import re
import shutil
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from werkzeug.utils import secure_filename

_JST = ZoneInfo("Asia/Tokyo")

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


_HASH_CHUNK = 65536


def sha256_hex_path(path: Path) -> str | None:
    """ファイルの SHA-256（16進小文字）。存在しない場合は None。"""
    path = Path(path)
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(_HASH_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_hex_file_storage(storage) -> str:
    """FileStorage の内容の SHA-256（読み取り後にストリーム位置を戻す）。"""
    stream = storage.stream
    pos = stream.tell() if hasattr(stream, "tell") else None
    digest = hashlib.sha256()
    try:
        if hasattr(stream, "seek"):
            stream.seek(0)
        while True:
            chunk = stream.read(_HASH_CHUNK)
            if not chunk:
                break
            digest.update(chunk)
    finally:
        if hasattr(stream, "seek"):
            stream.seek(pos if pos is not None else 0)
    return digest.hexdigest()


def compare_upload_to_existing(storage, existing_path: Path) -> dict:
    """アップロード予定と既存ファイルの SHA-256 比較。

    Returns:
        sha256_new, sha256_existing (str | None), same_content (bool | None)
    """
    new_hash = sha256_hex_file_storage(storage)
    existing_hash = sha256_hex_path(existing_path)
    if existing_hash is None:
        return {
            "sha256_new": new_hash,
            "sha256_existing": None,
            "same_content": None,
        }
    return {
        "sha256_new": new_hash,
        "sha256_existing": existing_hash,
        "same_content": new_hash == existing_hash,
    }


def find_filename_conflict(
    original: str, upload_dir: Path, conn
) -> tuple[str | None, dict | None]:
    """正規化ファイル名が uploads / DB に既にあるか。 (normalized, conflict_row)"""
    normalized = normalize_upload_filename(original)
    if not normalized:
        return None, None
    row = conn.execute(
        "SELECT id, filename, title FROM gifs WHERE filename = ?",
        (normalized,),
    ).fetchone()
    if row:
        return normalized, dict(row)
    if (upload_dir / normalized).exists():
        return normalized, {
            "id": None,
            "filename": normalized,
            "title": None,
        }
    return normalized, None


def _timestamp_suffix() -> str:
    """ファイル名用の JST タイムスタンプ（例: 20260519_143022）。"""
    return datetime.now(_JST).strftime("%Y%m%d_%H%M%S")


def _stem_with_timestamp(stem: str, extra: str = "") -> str:
    """語尾に _YYYYMMDD_HHMMSS（+ 任意の extra）を付けた stem。"""
    suffix = f"_{_timestamp_suffix()}{extra}"
    max_stem = _MAX_BASENAME_LEN - len(suffix)
    stem_part = stem if len(stem) <= max_stem else stem[:max_stem]
    return f"{stem_part}{suffix}"


def allocate_alternate_filename(
    base_normalized: str,
    upload_dir: Path,
    conn,
    *,
    reserved: set[str] | None = None,
) -> str:
    """同名時に語尾へタイムスタンプを付けたファイル名（例: photo_20260519_143022.gif）。"""
    reserved = reserved if reserved is not None else set()
    stem = Path(base_normalized).stem
    ext = extension_from_filename(base_normalized)
    for attempt in range(100):
        extra = f"_{attempt}" if attempt else ""
        candidate = f"{_stem_with_timestamp(stem, extra)}.{ext}"
        if not _filename_taken(candidate, upload_dir, conn, reserved):
            reserved.add(candidate)
            return candidate
    fallback = stored_filename(uuid.uuid4().hex, ext)
    reserved.add(fallback)
    return fallback


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


def preview_alternate_filename(base_normalized: str) -> str:
    """UI 表示用の候補名（保存時点の JST タイムスタンプを付与）。"""
    stem = Path(base_normalized).stem
    ext = extension_from_filename(base_normalized)
    return f"{_stem_with_timestamp(stem)}.{ext}"


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
