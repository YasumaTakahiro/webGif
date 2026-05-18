"""フォルダ内の画像を uploads にコピーし DB に登録する（Web アップロードより高速）。"""

import argparse
import shutil
import sys
import uuid
from pathlib import Path

import db
import media_util

BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"


def _title_from_filename(path: Path) -> str | None:
    stem = path.stem.strip()
    return stem[:120] if stem else None


def _parse_tag_ids(raw: str | None) -> list[int]:
    if not raw:
        return []
    ids = []
    for part in raw.replace(" ", "").split(","):
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError:
            print(f"[警告] タグ ID を無視: {part}", file=sys.stderr)
    return ids


def _find_images(source: Path, recursive: bool) -> list[Path]:
    return media_util.find_images(source, recursive)


def _title_exists(conn, title: str | None) -> bool:
    if not title:
        return False
    row = conn.execute(
        "SELECT 1 FROM gifs WHERE title = ? LIMIT 1", (title,)
    ).fetchone()
    return row is not None


def import_folder(
    source: Path,
    *,
    recursive: bool = False,
    category_id: int | None = None,
    tag_ids: list[int] | None = None,
    series_id: int | None = None,
    series_order_start: int | None = None,
    skip_duplicates: bool = False,
    fix_loops: bool = True,
    dry_run: bool = False,
) -> tuple[int, int, int]:
    source = source.resolve()
    if not source.is_dir():
        raise FileNotFoundError(f"フォルダが見つかりません: {source}")

    tag_ids = tag_ids or []
    files = _find_images(source, recursive)
    if not files:
        return 0, 0, 0

    UPLOAD_DIR.mkdir(exist_ok=True)
    db.init_db()

    imported = 0
    skipped = 0
    failed = 0
    series_order = series_order_start

    with db.get_db() as conn:
        if series_id:
            row = conn.execute(
                "SELECT id FROM series WHERE id = ?", (series_id,)
            ).fetchone()
            if not row:
                raise ValueError(f"シリーズ ID {series_id} が存在しません。")

        if category_id:
            row = conn.execute(
                "SELECT id FROM categories WHERE id = ?", (category_id,)
            ).fetchone()
            if not row:
                raise ValueError(f"カテゴリ ID {category_id} が存在しません。")

        for path in files:
            title = _title_from_filename(path)
            if skip_duplicates and _title_exists(conn, title):
                print(f"[スキップ] 同名タイトルあり: {path.name}")
                skipped += 1
                continue

            if dry_run:
                print(f"[確認] {path.name} -> uploads/…  title={title!r}")
                imported += 1
                if series_id and series_order is not None:
                    series_order += 1
                continue

            ext = media_util.extension_from_filename(path.name)
            if ext not in media_util.ALLOWED_IMAGE_EXTENSIONS:
                print(f"[スキップ] 非対応形式: {path.name}", file=sys.stderr)
                skipped += 1
                continue

            stored = media_util.stored_filename(uuid.uuid4().hex, ext)
            dest = UPLOAD_DIR / stored
            try:
                shutil.copy2(path, dest)
                if fix_loops:
                    media_util.maybe_fix_gif_loop(dest)
            except OSError as e:
                print(f"[失敗] {path.name}: {e}", file=sys.stderr)
                failed += 1
                if dest.exists():
                    dest.unlink(missing_ok=True)
                continue

            order = None
            if series_id is not None:
                if series_order is None:
                    order = db.next_series_order(conn, series_id)
                else:
                    order = series_order
                    series_order += 1

            cur = conn.execute(
                "INSERT INTO gifs (filename, title, category_id, series_id, series_order) "
                "VALUES (?, ?, ?, ?, ?)",
                (stored, title, category_id, series_id, order),
            )
            db.set_gif_tags(conn, cur.lastrowid, tag_ids)
            imported += 1
            print(f"[登録] {path.name} -> {stored}" + (f"  #{order}" if order else ""))

        if not dry_run:
            conn.commit()

    return imported, skipped, failed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "フォルダ内の画像（"
            f"{media_util.EXTENSIONS_LABEL}）を webGif の uploads / DB に一括登録します。"
        ),
    )
    parser.add_argument(
        "source",
        type=Path,
        help="画像が入ったフォルダのパス",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="サブフォルダも含める",
    )
    parser.add_argument(
        "--category-id",
        type=int,
        default=None,
        help="登録時のカテゴリ ID",
    )
    parser.add_argument(
        "--tag-ids",
        type=str,
        default=None,
        help="タグ ID（カンマ区切り、例: 1,2,3）",
    )
    parser.add_argument(
        "--series-id",
        type=int,
        default=None,
        help="割り当てるシリーズ ID",
    )
    parser.add_argument(
        "--series-order-start",
        type=int,
        default=None,
        help="シリーズの開始番号（1,2,3… と順に付与）",
    )
    parser.add_argument(
        "--skip-duplicates",
        action="store_true",
        help="ファイル名と同じタイトルが既にあればスキップ",
    )
    parser.add_argument(
        "--no-loop-fix",
        action="store_true",
        help="ループ補正をスキップ（起動時の一括補正に任せる）",
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="コピー・DB 登録を行わず対象だけ表示",
    )
    args = parser.parse_args(argv)

    try:
        imported, skipped, failed = import_folder(
            args.source,
            recursive=args.recursive,
            category_id=args.category_id,
            tag_ids=_parse_tag_ids(args.tag_ids),
            series_id=args.series_id,
            series_order_start=args.series_order_start,
            skip_duplicates=args.skip_duplicates,
            fix_loops=not args.no_loop_fix,
            dry_run=args.dry_run,
        )
    except (FileNotFoundError, ValueError) as e:
        print(f"エラー: {e}", file=sys.stderr)
        return 1

    label = "対象" if args.dry_run else "登録"
    print(
        f"\n完了: {label} {imported} 件"
        + (f" / スキップ {skipped} 件" if skipped else "")
        + (f" / 失敗 {failed} 件" if failed else "")
    )
    return 1 if failed and not imported else 0


if __name__ == "__main__":
    raise SystemExit(main())
