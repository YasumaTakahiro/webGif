import logging
import os
import re
import socket
import sqlite3
import sys
import threading
import uuid
from datetime import datetime
from pathlib import Path

from flask import (
    Flask,
    abort,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

import db
import gif_util
import media_util
import webgif_log

BASE_DIR = Path(__file__).parent
HOST = os.environ.get("WEBGIF_HOST", "127.0.0.1")
PORT = int(os.environ.get("WEBGIF_PORT", "5055"))
UPLOAD_DIR = BASE_DIR / "uploads"
ALLOWED_EXTENSIONS = media_util.ALLOWED_IMAGE_EXTENSIONS
GIFS_PER_PAGE = 10
def _max_upload_bytes():
    """MAX_UPLOAD_MB: 上限 MB。0 または未設定で制限なし（ローカル向け）。"""
    raw = os.environ.get("MAX_UPLOAD_MB", "0").strip()
    if raw in ("", "0", "none", "off"):
        return None
    return int(raw) * 1024 * 1024


MAX_CONTENT_LENGTH = _max_upload_bytes()


def _active_tag_ids():
    ids = []
    for raw in request.args.getlist("tag"):
        try:
            tag_id = int(raw)
        except (TypeError, ValueError):
            continue
        if tag_id not in ids:
            ids.append(tag_id)
    return sorted(ids)


def _series_only():
    return request.args.get("series_only", "").lower() in ("1", "true", "yes")


def _active_series_id():
    return request.args.get("series", type=int)


def _series_filter_active():
    return _series_only() or _active_series_id() is not None


_UNSET = object()


def _gallery_query(
    category=_UNSET, tag=_UNSET, series_only=_UNSET, series=_UNSET, page=None
):
    kw = {}
    if page is not None:
        kw["page"] = page
    series_id = _active_series_id() if series is _UNSET else series
    if series_id:
        kw["series"] = series_id
        return kw
    use_series_only = _series_only() if series_only is _UNSET else bool(series_only)
    if use_series_only:
        kw["series_only"] = 1
        return kw
    if category is not _UNSET:
        if category:
            kw["category"] = category
    else:
        cat = request.args.get("category", type=int)
        if cat:
            kw["category"] = cat
    if tag is not _UNSET:
        tag_ids = tag
    else:
        tag_ids = _active_tag_ids()
    if tag_ids:
        kw["tag"] = tag_ids
    return kw


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-change-me")
    app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    UPLOAD_DIR.mkdir(exist_ok=True)

    db.init_db()

    def _fix_gifs_background():
        count = gif_util.fix_all_upload_gifs(UPLOAD_DIR)
        if count:
            webgif_log.log(f"GIF loop fix: {count} file(s) updated")

    threading.Thread(target=_fix_gifs_background, daemon=True).start()

    @app.before_request
    def log_request():
        if request.path.startswith("/static"):
            return
        webgif_log.log(f"{request.method} {request.path}")
        if request.method == "POST" and request.path == "/gifs/upload":
            webgif_log.log("upload: ファイル受信完了・保存開始")

    @app.route("/health")
    def health():
        webgif_log.log("health check OK")
        return "webGif OK", 200, {"Content-Type": "text/plain; charset=utf-8"}

    @app.errorhandler(RequestEntityTooLarge)
    def upload_too_large(_e):
        limit = app.config.get("MAX_CONTENT_LENGTH")
        if limit:
            flash(
                f"合計サイズが上限（{limit // (1024 * 1024)} MB）を超えました。"
                "枚数を減らすか、run.bat 実行前に set MAX_UPLOAD_MB=0 で制限なしにできます。",
                "error",
            )
        else:
            flash(
                "リクエストが大きすぎます。一度に送る枚数を減らして再試行してください。",
                "error",
            )
        return redirect(request.referrer or url_for("index"))

    @app.template_filter("toggle_tag")
    def toggle_tag_filter(active_tags, tag_id):
        tags = list(active_tags or [])
        if tag_id in tags:
            return sorted(t for t in tags if t != tag_id)
        tags.append(tag_id)
        return sorted(tags)

    @app.context_processor
    def inject_globals():
        series_filter = _series_filter_active()
        with db.get_db() as conn:
            series_list = db.fetch_series(conn)
        return {
            "active_category": None
            if series_filter
            else request.args.get("category", type=int),
            "active_tags": [] if series_filter else _active_tag_ids(),
            "active_series_only": _series_only() and not _active_series_id(),
            "active_series_id": _active_series_id(),
            "series_filter_active": series_filter,
            "series_list": series_list,
            "gallery_query": _gallery_query,
            "page_loaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "app_port": PORT,
            "gifs_per_page": GIFS_PER_PAGE,
            "accept_images": media_util.ACCEPT_UPLOAD_ATTR,
        }

    def _gif_list_context(conn, page=1):
        series_id = _active_series_id()
        series_only = _series_only() and not series_id
        series_filter = series_id or series_only
        category_id = None if series_filter else request.args.get("category", type=int)
        tag_ids = [] if series_filter else _active_tag_ids()
        page = max(1, request.args.get("page", page, type=int))
        total = db.count_gifs(
            conn,
            category_id,
            tag_ids,
            series_only=series_only,
            series_id=series_id,
        )
        offset = (page - 1) * GIFS_PER_PAGE
        gifs = db.fetch_gifs(
            conn,
            category_id=category_id,
            tag_ids=tag_ids,
            limit=GIFS_PER_PAGE,
            offset=offset,
            series_only=series_only,
            series_id=series_id,
        )
        loaded = offset + len(gifs)
        return {
            "gifs": gifs,
            "page": page,
            "has_more": loaded < total,
            "next_page": page + 1,
            "total": total,
            "loaded": loaded,
        }

    @app.route("/")
    def index():
        with db.get_db() as conn:
            categories = db.fetch_categories(conn)
            tags = db.fetch_tags(conn)
            series_entries = _series_entries(conn)
            list_ctx = _gif_list_context(conn, page=1)
        return render_template(
            "index.html",
            categories=categories,
            tags=tags,
            series_entries=series_entries,
            **list_ctx,
        )

    @app.route("/partials/gif-list")
    def partial_gif_list():
        page = request.args.get("page", 1, type=int)
        with db.get_db() as conn:
            list_ctx = _gif_list_context(conn, page=page)
            if page <= 1:
                categories = db.fetch_categories(conn)
                tags = db.fetch_tags(conn)
        if page > 1:
            return render_template("partials/gif_list_items.html", **list_ctx)
        return render_template(
            "partials/gif_list_refresh.html",
            categories=categories,
            tags=tags,
            **list_ctx,
        )

    @app.route("/partials/filters")
    def partial_filters():
        with db.get_db() as conn:
            categories = db.fetch_categories(conn)
            tags = db.fetch_tags(conn)
        return render_template(
            "partials/filters_oob.html",
            categories=categories,
            tags=tags,
        )

    @app.route("/gifs/upload", methods=["GET"])
    def upload_gif_get():
        return redirect(url_for("index"))

    @app.route("/gifs/upload", methods=["POST"])
    def upload_gif():
        webgif_log.log("upload started")
        files = [f for f in request.files.getlist("files") if f and f.filename]
        if not files:
            legacy = request.files.get("file")
            if legacy and legacy.filename:
                files = [legacy]

        if not files:
            return _upload_error("ファイルを選択してください。")

        category_id = request.form.get("category_id", type=int) or None
        tag_ids = _parse_tag_ids(request.form)
        form_title = (request.form.get("title") or "").strip() or None
        single_file = len(files) == 1

        uploaded = 0
        skipped = []

        with db.get_db() as conn:
            for file in files:
                ext = (
                    file.filename.rsplit(".", 1)[-1].lower()
                    if "." in file.filename
                    else ""
                )
                if ext not in ALLOWED_EXTENSIONS:
                    skipped.append(
                        f"{file.filename}（{media_util.EXTENSIONS_LABEL} 以外）"
                    )
                    continue

                stored = media_util.stored_filename(uuid.uuid4().hex, ext)
                dest = UPLOAD_DIR / stored
                file.save(dest)
                media_util.maybe_fix_gif_loop(dest)

                if single_file and form_title:
                    title = form_title
                else:
                    title = _title_from_filename(file.filename)

                cur = conn.execute(
                    "INSERT INTO gifs (filename, title, category_id) VALUES (?, ?, ?)",
                    (stored, title, category_id),
                )
                db.set_gif_tags(conn, cur.lastrowid, tag_ids)
                uploaded += 1

            conn.commit()

        if uploaded == 0:
            detail = "、".join(skipped[:5])
            return _upload_error(
                f"アップロードできませんでした。{detail}"
                if detail
                else f"対応形式（{media_util.EXTENSIONS_LABEL}）のファイルがありません。"
            )

        msg = f"{uploaded} 件をアップロードしました。"
        if skipped:
            msg += f"（{len(skipped)} 件スキップ: " + "、".join(skipped[:5])
            if len(skipped) > 5:
                msg += " ほか"
            msg += "）"
        flash(msg, "success")
        webgif_log.log(f"upload done ({uploaded} files)")
        return redirect(url_for("index"))

    @app.route("/gifs/<int:gif_id>/edit", methods=["GET", "POST"])
    def edit_gif(gif_id):
        with db.get_db() as conn:
            gif = db.get_gif(conn, gif_id)
            if not gif:
                abort(404)
            categories = db.fetch_categories(conn)
            tags = db.fetch_tags(conn)
            series_list = db.fetch_series(conn)

            if request.method == "POST":
                title = (request.form.get("title") or "").strip() or None
                category_id = request.form.get("category_id", type=int) or None
                tag_ids = _parse_tag_ids(request.form)
                series_id, series_order = _parse_series_fields(
                    request.form, conn, gif_id
                )
                conn.execute(
                    "UPDATE gifs SET title = ?, category_id = ? WHERE id = ?",
                    (title, category_id, gif_id),
                )
                db.set_gif_tags(conn, gif_id, tag_ids)
                db.set_gif_series(conn, gif_id, series_id, series_order)
                conn.commit()
                gif = db.get_gif(conn, gif_id)
                if request.headers.get("HX-Request"):
                    return render_template(
                        "partials/gif_card.html",
                        gif=gif,
                    )
                return redirect(url_for("index"))

        selected_tag_ids = {t["id"] for t in gif["tags"]}
        return render_template(
            "partials/gif_edit.html",
            gif=gif,
            categories=categories,
            tags=tags,
            series_list=series_list,
            selected_tag_ids=selected_tag_ids,
        )

    @app.route("/gifs/<int:gif_id>/delete", methods=["POST"])
    def delete_gif(gif_id):
        with db.get_db() as conn:
            row = conn.execute(
                "SELECT filename FROM gifs WHERE id = ?", (gif_id,)
            ).fetchone()
            if not row:
                abort(404)
            conn.execute("DELETE FROM gifs WHERE id = ?", (gif_id,))
            conn.commit()
            path = UPLOAD_DIR / row["filename"]
            if path.exists():
                path.unlink()

        if request.headers.get("HX-Request"):
            with db.get_db() as conn:
                list_ctx = _gif_list_context(conn, page=1)
                categories = db.fetch_categories(conn)
                tags = db.fetch_tags(conn)
            return render_template(
                "partials/gif_list_refresh.html",
                categories=categories,
                tags=tags,
                **list_ctx,
            )
        return redirect(url_for("index"))

    @app.route("/gifs/<int:gif_id>/series-shift", methods=["POST"])
    def shift_gif_series_order(gif_id):
        direction = request.form.get("direction", "up")
        with db.get_db() as conn:
            if not db.swap_series_order(conn, gif_id, direction):
                flash("並び順を変更できませんでした。", "error")
            else:
                conn.commit()
        if request.headers.get("HX-Request"):
            with db.get_db() as conn:
                if request.form.get("refresh_list"):
                    list_ctx = _gif_list_context(conn, page=1)
                    categories = db.fetch_categories(conn)
                    tags = db.fetch_tags(conn)
                    return render_template(
                        "partials/gif_list_refresh.html",
                        categories=categories,
                        tags=tags,
                        **list_ctx,
                    )
                gif = db.get_gif(conn, gif_id)
            if gif:
                return render_template("partials/gif_card.html", gif=gif)
        return redirect(request.referrer or url_for("index"))

    @app.route("/series", methods=["POST"])
    def create_series():
        name = _normalize_name(request.form.get("name"))
        if not name:
            return _filters_response()
        with db.get_db() as conn:
            sort_order = db.next_series_sort_order(conn)
            conn.execute(
                "INSERT OR IGNORE INTO series (name, sort_order) VALUES (?, ?)",
                (name, sort_order),
            )
            conn.commit()
        return _filters_response()

    @app.route("/series/<int:series_id>/rename", methods=["POST"])
    def rename_series(series_id):
        name = _normalize_name(request.form.get("name"))
        if not name:
            flash("名称を入力してください。", "error")
            return _filters_response()
        with db.get_db() as conn:
            exists = conn.execute(
                "SELECT id FROM series WHERE id = ?", (series_id,)
            ).fetchone()
            if not exists:
                abort(404)
            try:
                conn.execute(
                    "UPDATE series SET name = ? WHERE id = ?",
                    (name, series_id),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                flash(f"「{name}」は既に使われています。", "error")
        return _filters_response()

    @app.route("/series/<int:series_id>/delete", methods=["POST"])
    def delete_series(series_id):
        with db.get_db() as conn:
            row = conn.execute(
                "SELECT name FROM series WHERE id = ?", (series_id,)
            ).fetchone()
            if not row:
                abort(404)
            conn.execute("DELETE FROM series WHERE id = ?", (series_id,))
            conn.commit()
        flash(f"シリーズ「{row['name']}」を削除しました。", "success")
        return _filters_response()

    @app.route("/series/<int:series_id>/save-orders", methods=["POST"])
    def save_series_orders(series_id):
        with db.get_db() as conn:
            exists = conn.execute(
                "SELECT id FROM series WHERE id = ?", (series_id,)
            ).fetchone()
            if not exists:
                abort(404)
            for key, val in request.form.items():
                if not key.startswith("order_"):
                    continue
                try:
                    gif_id = int(key[6:])
                except ValueError:
                    continue
                order = int(val) if str(val).strip() else None
                conn.execute(
                    "UPDATE gifs SET series_id = ?, series_order = ? WHERE id = ?",
                    (series_id, order, gif_id),
                )
            conn.commit()
        return _filters_response()

    @app.route("/categories", methods=["POST"])
    def create_category():
        name = _normalize_name(request.form.get("name"))
        if not name:
            return _filters_response()
        with db.get_db() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO categories (name) VALUES (?)", (name,)
            )
            conn.commit()
        return _filters_response()

    @app.route("/tags", methods=["POST"])
    def create_tag():
        name = _normalize_name(request.form.get("name"))
        if not name:
            return _filters_response()
        with db.get_db() as conn:
            conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (name,))
            conn.commit()
        return _filters_response()

    @app.route("/categories/<int:category_id>/rename", methods=["POST"])
    def rename_category(category_id):
        name = _normalize_name(request.form.get("name"))
        if not name:
            flash("名称を入力してください。", "error")
            return _filters_response()
        with db.get_db() as conn:
            exists = conn.execute(
                "SELECT id FROM categories WHERE id = ?", (category_id,)
            ).fetchone()
            if not exists:
                abort(404)
            try:
                conn.execute(
                    "UPDATE categories SET name = ? WHERE id = ?",
                    (name, category_id),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                flash(f"「{name}」は既に使われています。", "error")
        return _filters_response()

    @app.route("/tags/<int:tag_id>/rename", methods=["POST"])
    def rename_tag(tag_id):
        name = _normalize_name(request.form.get("name"))
        if not name:
            flash("名称を入力してください。", "error")
            return _filters_response()
        with db.get_db() as conn:
            exists = conn.execute(
                "SELECT id FROM tags WHERE id = ?", (tag_id,)
            ).fetchone()
            if not exists:
                abort(404)
            try:
                conn.execute(
                    "UPDATE tags SET name = ? WHERE id = ?",
                    (name, tag_id),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                flash(f"「{name}」は既に使われています。", "error")
        return _filters_response()

    @app.route("/categories/<int:category_id>/delete", methods=["POST"])
    def delete_category(category_id):
        with db.get_db() as conn:
            row = conn.execute(
                "SELECT name FROM categories WHERE id = ?", (category_id,)
            ).fetchone()
            if not row:
                abort(404)
            gif_count = conn.execute(
                "SELECT COUNT(*) FROM gifs WHERE category_id = ?", (category_id,)
            ).fetchone()[0]
            conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
            conn.commit()

        flash(
            f"カテゴリ「{row['name']}」を削除しました。"
            + (f"（{gif_count} 件は未分類になります）" if gif_count else ""),
            "success",
        )
        redirect_url = None
        if request.args.get("category", type=int) == category_id:
            tag_ids = _active_tag_ids()
            redirect_url = (
                url_for("index", tag=tag_ids) if tag_ids else url_for("index")
            )
        return _filters_response(redirect_url=redirect_url)

    @app.route("/tags/<int:tag_id>/delete", methods=["POST"])
    def delete_tag(tag_id):
        with db.get_db() as conn:
            row = conn.execute(
                "SELECT name FROM tags WHERE id = ?", (tag_id,)
            ).fetchone()
            if not row:
                abort(404)
            gif_count = conn.execute(
                "SELECT COUNT(*) FROM gif_tags WHERE tag_id = ?", (tag_id,)
            ).fetchone()[0]
            conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
            conn.commit()

        flash(
            f"タグ「{row['name']}」を削除しました。"
            + (f"（{gif_count} 件の GIF から外れます）" if gif_count else ""),
            "success",
        )
        redirect_url = None
        if tag_id in _active_tag_ids():
            cat = request.args.get("category", type=int)
            remaining = [t for t in _active_tag_ids() if t != tag_id]
            if cat and remaining:
                redirect_url = url_for("index", category=cat, tag=remaining)
            elif cat:
                redirect_url = url_for("index", category=cat)
            elif remaining:
                redirect_url = url_for("index", tag=remaining)
            else:
                redirect_url = url_for("index")
        return _filters_response(redirect_url=redirect_url)

    @app.route("/uploads/<path:filename>")
    def serve_upload(filename):
        safe = secure_filename(filename)
        if safe != filename:
            abort(404)
        path = UPLOAD_DIR / safe
        if not path.exists():
            abort(404)
        from flask import send_from_directory

        return send_from_directory(
            UPLOAD_DIR,
            safe,
            mimetype=media_util.mimetype_for_filename(safe),
        )

    return app


def _title_from_filename(filename):
    stem = Path(filename).stem.strip()
    return stem[:120] if stem else None


def _normalize_name(value):
    if not value:
        return ""
    name = re.sub(r"\s+", " ", value.strip())
    return name[:64]


def _parse_tag_ids(form):
    raw = form.getlist("tag_ids")
    ids = []
    for v in raw:
        try:
            ids.append(int(v))
        except (TypeError, ValueError):
            continue
    return ids


def _parse_series_fields(form, conn, gif_id=None):
    raw = (form.get("series_id") or "").strip()
    series_id = int(raw) if raw else None
    raw_order = (form.get("series_order") or "").strip()
    series_order = int(raw_order) if raw_order else None
    if series_id and series_order is None:
        series_order = db.next_series_order(conn, series_id, gif_id)
    return series_id, series_order


def _series_entries(conn):
    entries = []
    for s in db.fetch_series(conn):
        entries.append(
            {
                "series": s,
                "gifs": db.fetch_series_gifs(conn, s["id"]),
            }
        )
    return entries


def _filters_response(redirect_url=None):
    with db.get_db() as conn:
        categories = db.fetch_categories(conn)
        tags = db.fetch_tags(conn)
        series_entries = _series_entries(conn)
    resp = make_response(
        render_template(
            "partials/filters_oob.html",
            categories=categories,
            tags=tags,
            series_entries=series_entries,
        )
    )
    if redirect_url:
        resp.headers["HX-Redirect"] = redirect_url
    return resp


def _hx_redirect(location):
    resp = make_response("", 204)
    resp.headers["HX-Redirect"] = location
    return resp


def _upload_error(message):
    flash(message, "error")
    return redirect(request.referrer or url_for("index"))


app = create_app()

def _port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False


if __name__ == "__main__":
    url = f"http://{HOST}:{PORT}/"
    log_path = webgif_log.LOG_PATH

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
        force=True,
    )
    logging.getLogger("werkzeug").setLevel(logging.INFO)

    webgif_log.log("=== webGif 起動 ===")
    webgif_log.log(f"URL: {url}")
    webgif_log.log(f"ログファイル: {log_path}")

    if not _port_available(HOST, PORT):
        webgif_log.log(
            f"ERROR: ポート {PORT} は使用中です。"
            " 別の run.ps1 を止めるか WEBGIF_PORT=5056 を指定してください。"
        )
        sys.exit(1)

    print(f"webGif: {url}", flush=True)
    print(f"ログファイル: {log_path}", flush=True)
    print("接続テスト: ブラウザで上記 URL を開く → GET / がログに出ます", flush=True)
    print(f"ヘルスチェック: {url}health", flush=True)

    app.run(
        host=HOST,
        port=PORT,
        debug=False,
        use_reloader=False,
        threaded=True,
    )
