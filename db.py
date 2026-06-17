"""
StarMind Manager - 数据库模块
SQLite3 本地持久化：starred_repos / collections / collection_items 表的初始化与 CRUD 操作
支持：多用户同步、软删除、收藏夹、自定义集合、手动编辑、批量操作
"""

import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "starmind.db")


def get_connection():
    """获取数据库连接（自动创建文件）"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ═══════════════════════════════════════
#           Schema 初始化与迁移
# ═══════════════════════════════════════

def init_db():
    """初始化数据库表结构并执行迁移"""
    conn = get_connection()

    # ── 主表 ──
    conn.execute("""
        CREATE TABLE IF NOT EXISTS starred_repos (
            id          INTEGER PRIMARY KEY,
            name        TEXT    NOT NULL,
            stars       INTEGER DEFAULT 0,
            summary     TEXT,
            category    TEXT,
            tags        TEXT,
            language    TEXT,
            url         TEXT,
            description TEXT,
            processed_date TEXT,
            owner_username TEXT,
            starred_at TEXT
        )
    """)

    # ── 自动迁移：新增列 ──
    _migrations = [
        ("starred_repos", "owner_username", "TEXT"),
        ("starred_repos", "starred_at",     "TEXT"),
        ("starred_repos", "hidden",         "INTEGER DEFAULT 0"),
        ("starred_repos", "notes",          "TEXT"),
        ("starred_repos", "favorite",       "INTEGER DEFAULT 0"),
    ]
    for table, col, coltype in _migrations:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}")
        except sqlite3.OperationalError:
            pass  # 列已存在

    # ── 集合表 ──
    conn.execute("""
        CREATE TABLE IF NOT EXISTS collections (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL UNIQUE,
            created_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS collection_items (
            collection_id INTEGER,
            repo_id       INTEGER,
            PRIMARY KEY (collection_id, repo_id),
            FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE,
            FOREIGN KEY (repo_id)       REFERENCES starred_repos(id) ON DELETE CASCADE
        )
    """)

    conn.commit()
    conn.close()


# ═══════════════════════════════════════
#        starred_repos 基础 CRUD
# ═══════════════════════════════════════

def get_existing_ids(owner_username: str = "") -> set:
    """返回本地数据库中该用户已记录的项目 ID 集合"""
    conn = get_connection()
    if owner_username:
        rows = conn.execute(
            "SELECT id FROM starred_repos WHERE owner_username = ?", (owner_username,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id FROM starred_repos WHERE owner_username = '' OR owner_username IS NULL"
        ).fetchall()
    conn.close()
    return {row["id"] for row in rows}


def upsert_repo(repo: dict, owner_username: str = ""):
    """插入或更新一条项目记录"""
    conn = get_connection()
    tags = repo.get("tags", [])
    # 兼容：tags 可能是 list 或已经是 JSON 字符串
    if isinstance(tags, str):
        tags_json = tags
    else:
        tags_json = json.dumps(tags, ensure_ascii=False)
    conn.execute("""
        INSERT INTO starred_repos
            (id, name, stars, summary, category, tags, language, url, description,
             processed_date, owner_username, starred_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,
            stars=excluded.stars,
            summary=excluded.summary,
            category=excluded.category,
            tags=excluded.tags,
            language=excluded.language,
            url=excluded.url,
            description=excluded.description,
            processed_date=excluded.processed_date,
            owner_username=excluded.owner_username,
            starred_at=excluded.starred_at
    """, (
        repo["id"], repo["name"], repo.get("stars", 0),
        repo.get("summary"), repo.get("category"), tags_json,
        repo.get("language"), repo.get("url"), repo.get("description"),
        datetime.now().isoformat(), owner_username, repo.get("starred_at", ""),
    ))
    conn.commit()
    conn.close()


def get_all_repos(include_hidden: bool = False) -> list:
    """获取所有已记录的项目，按星标数降序排列。默认排除隐藏项目。"""
    conn = get_connection()
    if include_hidden:
        rows = conn.execute("SELECT * FROM starred_repos ORDER BY stars DESC").fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM starred_repos WHERE hidden = 0 OR hidden IS NULL ORDER BY stars DESC"
        ).fetchall()
    conn.close()
    return _rows_to_repos(rows)


def get_repos_paged(page: int = 1, page_size: int = 50, category: str = "",
                    search: str = "", include_hidden: bool = False) -> tuple:
    """分页获取项目，返回 (repos_list, total_count)"""
    conn = get_connection()
    conditions = []
    params = []

    if not include_hidden:
        conditions.append("(hidden = 0 OR hidden IS NULL)")
    if category:
        conditions.append("category = ?")
        params.append(category)
    if search:
        conditions.append("(name LIKE ? OR summary LIKE ? OR description LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like, like])

    where = " WHERE " + " AND ".join(conditions) if conditions else ""

    total = conn.execute(f"SELECT COUNT(*) FROM starred_repos{where}", params).fetchone()[0]
    offset = (page - 1) * page_size
    rows = conn.execute(
        f"SELECT * FROM starred_repos{where} ORDER BY stars DESC LIMIT ? OFFSET ?",
        params + [page_size, offset]
    ).fetchall()
    conn.close()
    return _rows_to_repos(rows), total


def get_repo_by_id(repo_id: int) -> dict | None:
    """根据 ID 获取单个项目"""
    conn = get_connection()
    row = conn.execute("SELECT * FROM starred_repos WHERE id = ?", (repo_id,)).fetchone()
    conn.close()
    if row:
        repos = _rows_to_repos([row])
        return repos[0] if repos else None
    return None


def get_repo_count(include_hidden: bool = False) -> int:
    """获取数据库中项目总数"""
    conn = get_connection()
    if include_hidden:
        count = conn.execute("SELECT COUNT(*) FROM starred_repos").fetchone()[0]
    else:
        count = conn.execute(
            "SELECT COUNT(*) FROM starred_repos WHERE hidden = 0 OR hidden IS NULL"
        ).fetchone()[0]
    conn.close()
    return count


def _rows_to_repos(rows) -> list:
    """将 Row 对象列表转为 dict 列表，反序列化 tags"""
    result = []
    for row in rows:
        item = dict(row)
        try:
            item["tags"] = json.loads(item["tags"]) if item["tags"] else []
        except (json.JSONDecodeError, TypeError):
            item["tags"] = []
        result.append(item)
    return result


# ═══════════════════════════════════════
#       软删除 / 硬删除 / 收藏
# ═══════════════════════════════════════

def toggle_hidden(repo_id: int, hidden: bool = True) -> None:
    """软删除/恢复项目"""
    conn = get_connection()
    conn.execute("UPDATE starred_repos SET hidden = ? WHERE id = ?", (1 if hidden else 0, repo_id))
    conn.commit()
    conn.close()


def hard_delete_repo(repo_id: int) -> None:
    """硬删除项目（同时移除所有集合关联）"""
    conn = get_connection()
    conn.execute("DELETE FROM collection_items WHERE repo_id = ?", (repo_id,))
    conn.execute("DELETE FROM starred_repos WHERE id = ?", (repo_id,))
    conn.commit()
    conn.close()


def toggle_favorite(repo_id: int) -> bool:
    """切换收藏状态，返回新状态"""
    conn = get_connection()
    row = conn.execute("SELECT favorite FROM starred_repos WHERE id = ?", (repo_id,)).fetchone()
    if not row:
        conn.close()
        return False
    new_val = 0 if row["favorite"] else 1
    conn.execute("UPDATE starred_repos SET favorite = ? WHERE id = ?", (new_val, repo_id))
    conn.commit()
    conn.close()
    return bool(new_val)


# ═══════════════════════════════════════
#         手动编辑 Metadata
# ═══════════════════════════════════════

def update_repo_metadata(repo_id: int, summary: str = None, category: str = None,
                         tags: list = None, notes: str = None) -> None:
    """手动更新项目的摘要、分类、标签、备注"""
    updates = []
    params = []
    if summary is not None:
        updates.append("summary = ?")
        params.append(summary)
    if category is not None:
        updates.append("category = ?")
        params.append(category)
    if tags is not None:
        updates.append("tags = ?")
        params.append(json.dumps(tags, ensure_ascii=False))
    if notes is not None:
        updates.append("notes = ?")
        params.append(notes)

    if not updates:
        return

    params.append(repo_id)
    conn = get_connection()
    conn.execute(f"UPDATE starred_repos SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    conn.close()


# ═══════════════════════════════════════
#           批量操作
# ═══════════════════════════════════════

def batch_toggle_hidden(repo_ids: list, hidden: bool = True) -> None:
    """批量软删除/恢复"""
    if not repo_ids:
        return
    conn = get_connection()
    placeholders = ",".join("?" * len(repo_ids))
    conn.execute(
        f"UPDATE starred_repos SET hidden = ? WHERE id IN ({placeholders})",
        [1 if hidden else 0] + repo_ids
    )
    conn.commit()
    conn.close()


def batch_delete(repo_ids: list) -> None:
    """批量硬删除"""
    if not repo_ids:
        return
    conn = get_connection()
    placeholders = ",".join("?" * len(repo_ids))
    conn.execute(f"DELETE FROM collection_items WHERE repo_id IN ({placeholders})", repo_ids)
    conn.execute(f"DELETE FROM starred_repos WHERE id IN ({placeholders})", repo_ids)
    conn.commit()
    conn.close()


def batch_update_category(repo_ids: list, new_category: str) -> None:
    """批量修改分类"""
    if not repo_ids:
        return
    conn = get_connection()
    placeholders = ",".join("?" * len(repo_ids))
    conn.execute(
        f"UPDATE starred_repos SET category = ? WHERE id IN ({placeholders})",
        [new_category] + repo_ids
    )
    conn.commit()
    conn.close()


# ═══════════════════════════════════════
#            集合管理
# ═══════════════════════════════════════

def create_collection(name: str) -> int:
    """创建集合，返回集合 ID"""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO collections (name, created_at) VALUES (?, ?)",
            (name, datetime.now().isoformat())
        )
        conn.commit()
        cid = conn.execute("SELECT id FROM collections WHERE name = ?", (name,)).fetchone()["id"]
        return cid
    except sqlite3.IntegrityError:
        return conn.execute("SELECT id FROM collections WHERE name = ?", (name,)).fetchone()["id"]
    finally:
        conn.close()


def delete_collection(name: str) -> None:
    """删除集合及其所有关联"""
    conn = get_connection()
    row = conn.execute("SELECT id FROM collections WHERE name = ?", (name,)).fetchone()
    if row:
        conn.execute("DELETE FROM collection_items WHERE collection_id = ?", (row["id"],))
        conn.execute("DELETE FROM collections WHERE id = ?", (row["id"],))
        conn.commit()
    conn.close()


def get_collections() -> list:
    """获取所有集合（附带项目数量）"""
    conn = get_connection()
    rows = conn.execute("""
        SELECT c.id, c.name, c.created_at,
               COUNT(ci.repo_id) as repo_count
        FROM collections c
        LEFT JOIN collection_items ci ON c.id = ci.collection_id
        GROUP BY c.id
        ORDER BY c.name
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_to_collection(collection_name: str, repo_id: int) -> None:
    """将项目添加到集合"""
    conn = get_connection()
    row = conn.execute("SELECT id FROM collections WHERE name = ?", (collection_name,)).fetchone()
    if not row:
        conn.close()
        return
    try:
        conn.execute(
            "INSERT INTO collection_items (collection_id, repo_id) VALUES (?, ?)",
            (row["id"], repo_id)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # 已存在
    finally:
        conn.close()


def remove_from_collection(collection_name: str, repo_id: int) -> None:
    """从集合中移除项目"""
    conn = get_connection()
    row = conn.execute("SELECT id FROM collections WHERE name = ?", (collection_name,)).fetchone()
    if row:
        conn.execute(
            "DELETE FROM collection_items WHERE collection_id = ? AND repo_id = ?",
            (row["id"], repo_id)
        )
        conn.commit()
    conn.close()


def batch_add_to_collection(collection_name: str, repo_ids: list) -> None:
    """批量添加到集合"""
    if not repo_ids:
        return
    conn = get_connection()
    row = conn.execute("SELECT id FROM collections WHERE name = ?", (collection_name,)).fetchone()
    if not row:
        conn.close()
        return
    cid = row["id"]
    for rid in repo_ids:
        try:
            conn.execute(
                "INSERT INTO collection_items (collection_id, repo_id) VALUES (?, ?)", (cid, rid)
            )
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    conn.close()


def get_collection_repos(collection_name: str) -> list:
    """获取集合内所有项目"""
    conn = get_connection()
    rows = conn.execute("""
        SELECT r.* FROM starred_repos r
        INNER JOIN collection_items ci ON r.id = ci.repo_id
        INNER JOIN collections c ON ci.collection_id = c.id
        WHERE c.name = ?
        ORDER BY r.stars DESC
    """, (collection_name,)).fetchall()
    conn.close()
    return _rows_to_repos(rows)


def get_repo_collections(repo_id: int) -> list:
    """获取项目所属的所有集合名称"""
    conn = get_connection()
    rows = conn.execute("""
        SELECT c.name FROM collections c
        INNER JOIN collection_items ci ON c.id = ci.collection_id
        WHERE ci.repo_id = ?
        ORDER BY c.name
    """, (repo_id,)).fetchall()
    conn.close()
    return [r["name"] for r in rows]


# ═══════════════════════════════════════
#          数据统计（Phase 2 用）
# ═══════════════════════════════════════

def get_all_categories() -> list:
    """获取所有不重复的分类"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT DISTINCT category FROM starred_repos "
        "WHERE category IS NOT NULL AND category != '' AND (hidden = 0 OR hidden IS NULL) "
        "ORDER BY category"
    ).fetchall()
    conn.close()
    return [r["category"] for r in rows]


def get_usernames() -> list:
    """获取所有已同步的用户名"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT DISTINCT owner_username FROM starred_repos "
        "WHERE owner_username IS NOT NULL AND owner_username != ''"
    ).fetchall()
    conn.close()
    return [r["owner_username"] for r in rows]


def get_repos_by_username(owner_username: str) -> list:
    """获取指定用户的所有项目"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM starred_repos WHERE owner_username = ? ORDER BY stars DESC",
        (owner_username,)
    ).fetchall()
    conn.close()
    return _rows_to_repos(rows)


def search_repos(query: str, category: str = "", language: str = "",
                 min_stars: int = 0, max_stars: int = 0,
                 include_hidden: bool = False) -> list:
    """高级搜索"""
    conn = get_connection()
    conditions = []
    params = []

    if not include_hidden:
        conditions.append("(hidden = 0 OR hidden IS NULL)")
    if query:
        conditions.append("(name LIKE ? OR summary LIKE ? OR description LIKE ? OR tags LIKE ?)")
        like = f"%{query}%"
        params.extend([like, like, like, like])
    if category:
        conditions.append("category = ?")
        params.append(category)
    if language:
        conditions.append("language = ?")
        params.append(language)
    if min_stars > 0:
        conditions.append("stars >= ?")
        params.append(min_stars)
    if max_stars > 0:
        conditions.append("stars <= ?")
        params.append(max_stars)

    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    rows = conn.execute(
        f"SELECT * FROM starred_repos{where} ORDER BY stars DESC", params
    ).fetchall()
    conn.close()
    return _rows_to_repos(rows)


def get_english_summary_repo_ids() -> list:
    """获取 summary 字段不含中文字符的项目 ID 列表（即英文简介项目）"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id FROM starred_repos "
        "WHERE summary IS NOT NULL AND summary != '' "
        "AND summary NOT GLOB '*[一-龥]*' "
        "ORDER BY id"
    ).fetchall()
    conn.close()
    return [row["id"] for row in rows]


# 模块加载时自动初始化数据库
init_db()
