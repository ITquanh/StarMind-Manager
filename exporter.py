"""
StarMind Manager - 导出模块
支持：HTML 知识库、Markdown、JSON、CSV 多格式导出
统计计算、相似度预计算、集合映射注入
"""

import os
import json
import csv
from datetime import datetime
from collections import Counter

from jinja2 import Environment, FileSystemLoader

import db
from analysis import build_similar_map, analyze_trends

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")


# ═══════════════════════════════════════
#            统计计算
# ═══════════════════════════════════════

def compute_stats(repos: list) -> dict:
    """计算综合统计数据，用于 Dashboard 图表"""
    if not repos:
        return {
            "total_count": 0, "avg_stars": 0,
            "category_counts": {}, "language_counts": {},
            "star_ranges": {}, "monthly_timeline": {},
            "top_repos": [], "top_categories": [], "top_languages": [],
        }

    total = len(repos)
    total_stars = sum(r.get("stars", 0) for r in repos)
    avg_stars = round(total_stars / total) if total else 0

    # 分类分布
    cat_counter = Counter(r.get("category", "其他") or "其他" for r in repos)
    category_counts = dict(cat_counter.most_common())

    # 语言分布
    lang_counter = Counter(r.get("language", "") for r in repos if r.get("language"))
    language_counts = dict(lang_counter.most_common(15))

    # Star 区间分布
    star_ranges = {"0-100": 0, "100-1k": 0, "1k-10k": 0, "10k-100k": 0, "100k+": 0}
    for r in repos:
        s = r.get("stars", 0)
        if s < 100:
            star_ranges["0-100"] += 1
        elif s < 1000:
            star_ranges["100-1k"] += 1
        elif s < 10000:
            star_ranges["1k-10k"] += 1
        elif s < 100000:
            star_ranges["10k-100k"] += 1
        else:
            star_ranges["100k+"] += 1

    # 收藏时间线（按月）
    monthly = Counter()
    for r in repos:
        starred = r.get("starred_at", "")
        if starred:
            try:
                dt = datetime.fromisoformat(starred.replace("Z", "+00:00").split("+")[0])
                key = dt.strftime("%Y-%m")
                monthly[key] += 1
            except (ValueError, TypeError):
                pass
    monthly_timeline = dict(sorted(monthly.items()))

    # Top 项目
    top_repos = sorted(repos, key=lambda x: x.get("stars", 0), reverse=True)[:10]
    top_repos_data = [{"name": r["name"], "stars": r.get("stars", 0),
                       "category": r.get("category", "")} for r in top_repos]

    return {
        "total_count": total,
        "avg_stars": avg_stars,
        "category_counts": category_counts,
        "language_counts": language_counts,
        "star_ranges": star_ranges,
        "monthly_timeline": monthly_timeline,
        "top_repos": top_repos_data,
        "top_categories": list(cat_counter.most_common(5)),
        "top_languages": list(lang_counter.most_common(5)),
    }


# ═══════════════════════════════════════
#          HTML 知识库导出
# ═══════════════════════════════════════

def export_html(output_path: str = None, repos: list = None,
                template_name: str = "index.html") -> str:
    """
    导出 HTML 知识库。
    repos: 可选，传入筛选后的子集；为 None 则导出全部。
    template_name: 模板文件名，支持 'index.html' 和 'compact.html'。
    """
    if output_path is None:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        # 根据模板命名输出文件
        base_name = template_name.replace(".html", "")
        output_path = os.path.join(OUTPUT_DIR, f"{base_name}.html")

    if repos is None:
        repos = db.get_all_repos()

    # 基础数据
    categories = sorted(set(r["category"] for r in repos if r.get("category")))
    all_tags = set()
    for r in repos:
        if isinstance(r.get("tags"), list):
            all_tags.update(r["tags"])
    all_tags = sorted(all_tags)

    # 统计数据
    stats = compute_stats(repos)

    # 相似度映射（限制项目数避免过慢）
    if len(repos) <= 2000:
        similar_map = build_similar_map(repos, top_n=3)
    else:
        similar_map = {}

    # 集合映射
    collections_map = {}
    for r in repos:
        cols = db.get_repo_collections(r["id"])
        if cols:
            collections_map[r["id"]] = cols

    # 趋势分析
    trends = analyze_trends(repos)

    # Jinja2 渲染
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=True)
    template = env.get_template(template_name)

    html_content = template.render(
        repos_json=json.dumps(repos, ensure_ascii=False, indent=2),
        categories_json=json.dumps(categories, ensure_ascii=False),
        tags_json=json.dumps(all_tags, ensure_ascii=False),
        total_count=len(repos),
        stats_json=json.dumps(stats, ensure_ascii=False, indent=2),
        similar_map_json=json.dumps(similar_map, ensure_ascii=False),
        collections_map_json=json.dumps(collections_map, ensure_ascii=False),
        trends_json=json.dumps(trends, ensure_ascii=False, indent=2),
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return output_path


# ═══════════════════════════════════════
#       多格式导出：Markdown / JSON / CSV
# ═══════════════════════════════════════

def export_markdown(repos: list = None, output_path: str = None) -> str:
    """导出为 Markdown 格式"""
    if repos is None:
        repos = db.get_all_repos()
    if output_path is None:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        output_path = os.path.join(OUTPUT_DIR, "starmind_export.md")

    stats = compute_stats(repos)
    lines = [
        f"# StarMind Manager 知识库导出",
        f"",
        f"> 导出时间：{datetime.now().strftime('%Y-%m-%d %H:%M')} | 项目总数：{len(repos)}",
        f"",
        f"## 📊 统计概览",
        f"",
        f"| 指标 | 数值 |",
        f"|------|------|",
        f"| 项目总数 | {stats['total_count']} |",
        f"| 平均 Star | {stats['avg_stars']} |",
        f"",
    ]

    # 分类分布
    lines.append("## 📂 分类分布\n")
    lines.append("| 分类 | 数量 |")
    lines.append("|------|------|")
    for cat, count in stats["category_counts"].items():
        lines.append(f"| {cat} | {count} |")
    lines.append("")

    # 项目列表
    lines.append("## 📋 项目列表\n")
    for r in repos:
        stars = r.get("stars", 0)
        star_str = f"{stars/1000:.1f}k" if stars >= 1000 else str(stars)
        lines.append(f"### ⭐ {star_str} - [{r['name']}]({r.get('url', '')})")
        lines.append("")
        if r.get("category"):
            lines.append(f"**分类**: {r['category']}")
        if r.get("language"):
            lines.append(f"**语言**: {r['language']}")
        if r.get("tags") and isinstance(r["tags"], list):
            tags_str = ", ".join(f"`{t}`" for t in r["tags"])
            lines.append(f"**标签**: {tags_str}")
        if r.get("summary"):
            lines.append(f"\n{r['summary']}")
        elif r.get("description"):
            lines.append(f"\n{r['description']}")
        lines.append("\n---\n")

    content = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    return output_path


def export_json(repos: list = None, output_path: str = None) -> str:
    """导出为 JSON 格式（可用于备份恢复）"""
    if repos is None:
        repos = db.get_all_repos()
    if output_path is None:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        output_path = os.path.join(OUTPUT_DIR, "starmind_export.json")

    export_data = {
        "exported_at": datetime.now().isoformat(),
        "total_count": len(repos),
        "repos": repos,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)

    return output_path


def export_csv(repos: list = None, output_path: str = None) -> str:
    """导出为 CSV 格式（tags 用分号分隔）"""
    if repos is None:
        repos = db.get_all_repos()
    if output_path is None:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        output_path = os.path.join(OUTPUT_DIR, "starmind_export.csv")

    fieldnames = ["id", "name", "stars", "category", "language", "tags",
                  "summary", "description", "url", "starred_at", "owner_username"]

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in repos:
            row = dict(r)
            # tags list → 分号分隔字符串
            if isinstance(row.get("tags"), list):
                row["tags"] = ";".join(row["tags"])
            writer.writerow(row)

    return output_path
