import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "webgif.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS gifs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                title TEXT,
                category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS gif_tags (
                gif_id INTEGER NOT NULL REFERENCES gifs(id) ON DELETE CASCADE,
                tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
                PRIMARY KEY (gif_id, tag_id)
            );
            """
        )


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


def count_gifs(conn, category_id=None, tag_ids=None):
    where, params = _gif_filter_sql(category_id, tag_ids)
    row = conn.execute(
        f"SELECT COUNT(*) AS n FROM gifs g{where}",
        params,
    ).fetchone()
    return row["n"] if row else 0


def fetch_gifs(conn, category_id=None, tag_ids=None, limit=None, offset=0):
    where, params = _gif_filter_sql(category_id, tag_ids)
    sql = (
        "SELECT g.*, c.name AS category_name "
        "FROM gifs g "
        "LEFT JOIN categories c ON c.id = g.category_id "
        f"{where}"
    )
    sql += " ORDER BY g.created_at DESC, g.id DESC"
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params = [*params, limit, offset]
    rows = conn.execute(sql, params).fetchall()

    gif_ids = [r["id"] for r in rows]
    tags_by_gif = {}
    if gif_ids:
        placeholders = ",".join("?" * len(gif_ids))
        tag_rows = conn.execute(
            f"SELECT gt.gif_id, t.id, t.name "
            f"FROM gif_tags gt "
            f"JOIN tags t ON t.id = gt.tag_id "
            f"WHERE gt.gif_id IN ({placeholders}) "
            f"ORDER BY t.name",
            gif_ids,
        ).fetchall()
        for tr in tag_rows:
            tags_by_gif.setdefault(tr["gif_id"], []).append(
                {"id": tr["id"], "name": tr["name"]}
            )

    return [
        {
            **dict(row),
            "tags": tags_by_gif.get(row["id"], []),
        }
        for row in rows
    ]


def get_gif(conn, gif_id):
    row = conn.execute(
        "SELECT g.*, c.name AS category_name "
        "FROM gifs g "
        "LEFT JOIN categories c ON c.id = g.category_id "
        "WHERE g.id = ?",
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
