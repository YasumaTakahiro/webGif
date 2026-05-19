import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

DB_PATH = Path(__file__).parent / "webgif.db"
JST = ZoneInfo("Asia/Tokyo")
_CREATED_AT_SQL = "datetime('now', 'localtime')"


def now_jst() -> str:
    """DB 保存用の JST タイムスタンプ（YYYY-MM-DD HH:MM:SS）。"""
    return datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _migrate(conn):
    conn.executescript(
        f"""
        CREATE TABLE IF NOT EXISTS series (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT ({_CREATED_AT_SQL})
        );
        """
    )
    _migrate_created_at_to_jst(conn)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(gifs)").fetchall()}
    if "series_id" not in cols:
        conn.execute(
            "ALTER TABLE gifs ADD COLUMN series_id INTEGER "
            "REFERENCES series(id) ON DELETE SET NULL"
        )
    if "series_order" not in cols:
        conn.execute("ALTER TABLE gifs ADD COLUMN series_order INTEGER")
    _migrate_gallery_order(conn)


def _migrate_gallery_order(conn):
    """シリーズ未所属 GIF 用の表示順（gallery_order）。"""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS _schema_migrations (name TEXT PRIMARY KEY)"
    )
    cols = {row[1] for row in conn.execute("PRAGMA table_info(gifs)").fetchall()}
    if "gallery_order" not in cols:
        conn.execute("ALTER TABLE gifs ADD COLUMN gallery_order INTEGER")

    if conn.execute(
        "SELECT 1 FROM _schema_migrations WHERE name = 'gallery_order_backfill'"
    ).fetchone():
        return

    rows = conn.execute(
        "SELECT id FROM gifs WHERE series_id IS NULL ORDER BY id"
    ).fetchall()
    for i, row in enumerate(rows):
        conn.execute(
            "UPDATE gifs SET gallery_order = ? WHERE id = ? AND gallery_order IS NULL",
            ((i + 1) * 10, row["id"]),
        )
    conn.execute(
        "INSERT INTO _schema_migrations (name) VALUES ('gallery_order_backfill')"
    )


def _migrate_created_at_to_jst(conn):
    """旧データの UTC created_at を JST に直す（1 回だけ）。"""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS _schema_migrations (name TEXT PRIMARY KEY)"
    )
    if conn.execute(
        "SELECT 1 FROM _schema_migrations WHERE name = 'created_at_jst'"
    ).fetchone():
        return
    for table in ("gifs", "categories", "tags", "series"):
        if not conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone():
            continue
        conn.execute(
            f"UPDATE {table} SET created_at = datetime(created_at, '+9 hours') "
            f"WHERE created_at IS NOT NULL"
        )
    conn.execute(
        "INSERT INTO _schema_migrations (name) VALUES ('created_at_jst')"
    )


def init_db():
    with get_db() as conn:
        conn.executescript(
            f"""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL DEFAULT ({_CREATED_AT_SQL})
            );

            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL DEFAULT ({_CREATED_AT_SQL})
            );

            CREATE TABLE IF NOT EXISTS gifs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                title TEXT,
                category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
                created_at TEXT NOT NULL DEFAULT ({_CREATED_AT_SQL})
            );

            CREATE TABLE IF NOT EXISTS gif_tags (
                gif_id INTEGER NOT NULL REFERENCES gifs(id) ON DELETE CASCADE,
                tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
                PRIMARY KEY (gif_id, tag_id)
            );
            """
        )
        _migrate(conn)


def fetch_categories(conn):
    return conn.execute(
        "SELECT c.*, COUNT(g.id) AS gif_count "
        "FROM categories c "
        "LEFT JOIN gifs g ON g.category_id = c.id "
        "GROUP BY c.id "
        "ORDER BY c.name"
    ).fetchall()


def fetch_tags(conn):
    return conn.execute(
        "SELECT t.*, COUNT(gt.gif_id) AS gif_count "
        "FROM tags t "
        "LEFT JOIN gif_tags gt ON gt.tag_id = t.id "
        "GROUP BY t.id "
        "ORDER BY t.name"
    ).fetchall()


def fetch_series(conn):
    return conn.execute(
        "SELECT s.*, COUNT(g.id) AS gif_count "
        "FROM series s "
        "LEFT JOIN gifs g ON g.series_id = s.id "
        "GROUP BY s.id "
        "ORDER BY s.sort_order, s.name"
    ).fetchall()


def fetch_series_gifs(conn, series_id):
    return conn.execute(
        "SELECT g.id, g.title, g.filename, g.series_order "
        "FROM gifs g "
        "WHERE g.series_id = ? "
        "ORDER BY "
        "CASE WHEN g.series_order IS NULL THEN 1 ELSE 0 END, "
        "g.series_order, g.id",
        (series_id,),
    ).fetchall()


def next_series_sort_order(conn):
    row = conn.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 AS n FROM series").fetchone()
    return row["n"] if row else 0


def _gif_filter_sql(category_id=None, tag_ids=None):
    sql = " WHERE 1=1"
    params = []
    if category_id:
        sql += " AND g.category_id = ?"
        params.append(category_id)
    for tag_id in tag_ids or []:
        sql += " AND g.id IN (SELECT gif_id FROM gif_tags WHERE tag_id = ?)"
        params.append(tag_id)
    return sql, params


def _gif_select_sql():
    return (
        "SELECT g.*, c.name AS category_name, "
        "s.name AS series_name, s.sort_order AS series_sort_order "
        "FROM gifs g "
        "LEFT JOIN categories c ON c.id = g.category_id "
        "LEFT JOIN series s ON s.id = g.series_id "
    )


def _sort_series_group(group):
    group.sort(
        key=lambda r: (
            r["series_order"] if r["series_order"] is not None else 1_000_000,
            r["id"],
        )
    )
    return group


def _sort_gallery_rows(rows):
    """全体は ID 昇順。シリーズは先頭話の ID の位置にまとめて並べる。"""
    by_series = {}
    slots = []
    for row in rows:
        series_id = row["series_id"]
        if series_id:
            by_series.setdefault(series_id, []).append(row)
        else:
            anchor = (
                row["gallery_order"]
                if row["gallery_order"] is not None
                else row["id"]
            )
            slots.append((anchor, [row]))

    for group in by_series.values():
        group = _sort_series_group(group)
        anchor_id = min(r["id"] for r in group)
        slots.append((anchor_id, group))

    slots.sort(key=lambda slot: slot[0])
    result = []
    for _, items in slots:
        result.extend(items)
    return result


def _attach_tags(conn, gifs):
    if not gifs:
        return []
    gif_ids = [g["id"] for g in gifs]
    placeholders = ",".join("?" * len(gif_ids))
    tag_rows = conn.execute(
        f"SELECT gt.gif_id, t.id, t.name "
        f"FROM gif_tags gt "
        f"JOIN tags t ON t.id = gt.tag_id "
        f"WHERE gt.gif_id IN ({placeholders}) "
        f"ORDER BY t.name",
        gif_ids,
    ).fetchall()
    tags_by_gif = {}
    for tr in tag_rows:
        tags_by_gif.setdefault(tr["gif_id"], []).append(
            {"id": tr["id"], "name": tr["name"]}
        )
    return [
        {**gif, "tags": tags_by_gif.get(gif["id"], [])}
        for gif in gifs
    ]


def _rows_to_gifs(rows):
    return [dict(row) for row in rows]


def fetch_gifs_for_gallery(
    conn, category_id=None, tag_ids=None, series_only=False, series_id=None
):
    if series_id:
        rows = conn.execute(
            f"{_gif_select_sql()} WHERE g.series_id = ?",
            (series_id,),
        ).fetchall()
        rows.sort(
            key=lambda r: (
                r["series_order"] if r["series_order"] is not None else 1_000_000,
                r["id"],
            )
        )
        return _attach_tags(conn, _rows_to_gifs(rows))

    if series_only:
        rows = conn.execute(
            f"{_gif_select_sql()} WHERE g.series_id IS NOT NULL"
        ).fetchall()
        sorted_rows = _sort_gallery_rows(rows)
        return _attach_tags(conn, _rows_to_gifs(sorted_rows))

    where, params = _gif_filter_sql(category_id, tag_ids)
    matched = conn.execute(
        f"SELECT g.id, g.series_id FROM gifs g{where}",
        params,
    ).fetchall()

    final_ids = {r["id"] for r in matched}
    series_ids = {r["series_id"] for r in matched if r["series_id"]}

    if series_ids:
        placeholders = ",".join("?" * len(series_ids))
        expand_sql = f"SELECT id FROM gifs WHERE series_id IN ({placeholders})"
        expand_params = list(series_ids)
        if category_id:
            expand_sql += " AND category_id = ?"
            expand_params.append(category_id)
        for row in conn.execute(expand_sql, expand_params):
            final_ids.add(row["id"])

    if not final_ids:
        return []

    placeholders = ",".join("?" * len(final_ids))
    rows = conn.execute(
        f"{_gif_select_sql()} WHERE g.id IN ({placeholders})",
        list(final_ids),
    ).fetchall()
    sorted_rows = _sort_gallery_rows(rows)
    return _attach_tags(conn, _rows_to_gifs(sorted_rows))


def count_gifs(
    conn, category_id=None, tag_ids=None, series_only=False, series_id=None
):
    return len(
        fetch_gifs_for_gallery(
            conn,
            category_id,
            tag_ids,
            series_only=series_only,
            series_id=series_id,
        )
    )


def fetch_gifs(
    conn,
    category_id=None,
    tag_ids=None,
    limit=None,
    offset=0,
    series_only=False,
    series_id=None,
):
    all_gifs = fetch_gifs_for_gallery(
        conn,
        category_id,
        tag_ids,
        series_only=series_only,
        series_id=series_id,
    )
    if limit is None:
        return all_gifs
    start = offset or 0
    return all_gifs[start : start + limit]


def get_gif(conn, gif_id):
    row = conn.execute(
        f"{_gif_select_sql()} WHERE g.id = ?",
        (gif_id,),
    ).fetchone()
    if not row:
        return None
    tags = conn.execute(
        "SELECT t.id, t.name FROM gif_tags gt "
        "JOIN tags t ON t.id = gt.tag_id "
        "WHERE gt.gif_id = ? ORDER BY t.name",
        (gif_id,),
    ).fetchall()
    return {**dict(row), "tags": [dict(t) for t in tags]}


def set_gif_tags(conn, gif_id, tag_ids):
    conn.execute("DELETE FROM gif_tags WHERE gif_id = ?", (gif_id,))
    for tag_id in tag_ids:
        conn.execute(
            "INSERT OR IGNORE INTO gif_tags (gif_id, tag_id) VALUES (?, ?)",
            (gif_id, tag_id),
        )


def set_gif_series(conn, gif_id, series_id, series_order):
    if series_id:
        conn.execute(
            "UPDATE gifs SET series_id = ?, series_order = ?, gallery_order = NULL "
            "WHERE id = ?",
            (series_id, series_order, gif_id),
        )
    else:
        order = next_gallery_order(conn, exclude_gif_id=gif_id)
        conn.execute(
            "UPDATE gifs SET series_id = NULL, series_order = NULL, "
            "gallery_order = COALESCE(gallery_order, ?) WHERE id = ?",
            (order, gif_id),
        )


def next_gallery_order(conn, exclude_gif_id=None):
    sql = (
        "SELECT COALESCE(MAX(gallery_order), 0) + 10 AS n FROM gifs "
        "WHERE series_id IS NULL"
    )
    params = []
    if exclude_gif_id:
        sql += " AND id != ?"
        params.append(exclude_gif_id)
    row = conn.execute(sql, params).fetchone()
    return row["n"] if row else 10


def swap_gallery_order(
    conn,
    gif_id,
    direction,
    *,
    category_id=None,
    tag_ids=None,
    series_only=False,
    series_id=None,
):
    if series_only or series_id:
        return False
    gifs = fetch_gifs_for_gallery(
        conn,
        category_id,
        tag_ids,
        series_only=series_only,
        series_id=series_id,
    )
    standalone_ids = [g["id"] for g in gifs if not g["series_id"]]
    if gif_id not in standalone_ids:
        return False
    idx = standalone_ids.index(gif_id)
    if direction == "up" and idx > 0:
        other_id = standalone_ids[idx - 1]
    elif direction == "down" and idx < len(standalone_ids) - 1:
        other_id = standalone_ids[idx + 1]
    else:
        return False

    cur = conn.execute(
        "SELECT gallery_order FROM gifs WHERE id = ?", (gif_id,)
    ).fetchone()
    other = conn.execute(
        "SELECT gallery_order FROM gifs WHERE id = ?", (other_id,)
    ).fetchone()
    if not cur or not other:
        return False
    a_order = cur["gallery_order"]
    b_order = other["gallery_order"]
    if a_order is None or b_order is None:
        return False
    conn.execute(
        "UPDATE gifs SET gallery_order = ? WHERE id = ?", (b_order, gif_id)
    )
    conn.execute(
        "UPDATE gifs SET gallery_order = ? WHERE id = ?", (a_order, other_id)
    )
    return True


def next_series_order(conn, series_id, exclude_gif_id=None):
    sql = (
        "SELECT COALESCE(MAX(series_order), 0) + 1 AS n FROM gifs "
        "WHERE series_id = ?"
    )
    params = [series_id]
    if exclude_gif_id:
        sql += " AND id != ?"
        params.append(exclude_gif_id)
    row = conn.execute(sql, params).fetchone()
    return row["n"] if row else 1


def swap_series_order(conn, gif_id, direction):
    gif = conn.execute(
        "SELECT id, series_id, series_order FROM gifs WHERE id = ?",
        (gif_id,),
    ).fetchone()
    if not gif or not gif["series_id"] or gif["series_order"] is None:
        return False

    siblings = conn.execute(
        "SELECT id, series_order FROM gifs "
        "WHERE series_id = ? AND series_order IS NOT NULL "
        "ORDER BY series_order, id",
        (gif["series_id"],),
    ).fetchall()
    ids = [s["id"] for s in siblings]
    if gif_id not in ids:
        return False
    idx = ids.index(gif_id)
    if direction == "up" and idx > 0:
        other_id = ids[idx - 1]
    elif direction == "down" and idx < len(ids) - 1:
        other_id = ids[idx + 1]
    else:
        return False

    other = next(s for s in siblings if s["id"] == other_id)
    conn.execute(
        "UPDATE gifs SET series_order = ? WHERE id = ?",
        (other["series_order"], gif_id),
    )
    conn.execute(
        "UPDATE gifs SET series_order = ? WHERE id = ?",
        (gif["series_order"], other_id),
    )
    return True
