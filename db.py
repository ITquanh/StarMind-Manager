"""
StarMind Manager - 数据库模块
SQLite3 本地持久化：starred_repos 表的初始化与 CRUD 操作
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


def init_db():
    """初始化数据库表结构"""
    conn = get_connection()
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
            processed_date TEXT
        )
    """)
    conn.commit()
    conn.close()


def get_existing_ids() -> set:
    """返回本地数据库中已记录的全部项目 ID 集合"""
    conn = get_connection()
    rows = conn.execute("SELECT id FROM starred_repos").fetchall()
    conn.close()
    return {row["id"] for row in rows}


def upsert_repo(repo: dict):
    """
    插入或更新一条项目记录。
    repo 字典应包含：id, name, stars, summary, category, tags(list), language, url, description
    """
    conn = get_connection()
    tags_json = json.dumps(repo.get("tags", []), ensure_ascii=False)
    conn.execute("""
        INSERT INTO starred_repos (id, name, stars, summary, category, tags, language, url, description, processed_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,
            stars=excluded.stars,
            summary=excluded.summary,
            category=excluded.category,
            tags=excluded.tags,
            language=excluded.language,
            url=excluded.url,
            description=excluded.description,
            processed_date=excluded.processed_date
    """, (
        repo["id"],
        repo["name"],
        repo.get("stars", 0),
        repo.get("summary"),
        repo.get("category"),
        tags_json,
        repo.get("language"),
        repo.get("url"),
        repo.get("description"),
        datetime.now().isoformat(),
    ))
    conn.commit()
    conn.close()


def get_all_repos() -> list:
    """获取所有已记录的项目，按星标数降序排列"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM starred_repos ORDER BY stars DESC"
    ).fetchall()
    conn.close()

    result = []
    for row in rows:
        item = dict(row)
        # 将 tags JSON 字符串解析为列表
        try:
            item["tags"] = json.loads(item["tags"]) if item["tags"] else []
        except (json.JSONDecodeError, TypeError):
            item["tags"] = []
        result.append(item)
    return result


def get_repo_count() -> int:
    """获取数据库中项目总数"""
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM starred_repos").fetchone()[0]
    conn.close()
    return count


# 模块加载时自动初始化数据库
init_db()
