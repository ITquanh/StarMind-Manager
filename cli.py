"""
StarMind Manager - CLI 命令行入口
支持：同步、导出、重分析、统计、搜索
"""

import argparse
import json
import os
import sys

# 确保能导入同目录模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db
import exporter
from sync_engine import SyncEngine


def load_config() -> dict:
    config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    if os.path.exists(config_file):
        with open(config_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _print_event(event_type, data):
    """同步事件回调：打印到终端"""
    if event_type == 'log':
        print(data)
    elif event_type == 'progress':
        processed, total = data
        pct = int(processed / total * 100) if total else 0
        print(f"  进度: {processed}/{total} ({pct}%)", end="\r")
    elif event_type == 'done':
        success, fail = data
        print(f"\n完成: 成功 {success}, 失败 {fail}")


def cmd_sync(args):
    """执行同步"""
    config = load_config()
    engine = SyncEngine(config)
    engine.sync(
        max_workers=args.workers,
        callback=_print_event,
    )


def cmd_export(args):
    """导出数据"""
    repos = db.get_all_repos()
    if not repos:
        print("数据库为空，请先执行同步。")
        return

    fmt = args.format.lower()
    if fmt == "html":
        template = args.template or "index.html"
        path = exporter.export_html(repos=repos, template_name=template)
    elif fmt == "json":
        path = exporter.export_json(repos)
    elif fmt == "csv":
        path = exporter.export_csv(repos)
    elif fmt == "markdown" or fmt == "md":
        path = exporter.export_markdown(repos)
    else:
        print(f"不支持的格式: {fmt}")
        return

    print(f"✅ 已导出到: {path}")


def cmd_reanalyze(args):
    """重新分析项目"""
    config = load_config()
    engine = SyncEngine(config)
    repo_ids = None
    if args.ids:
        repo_ids = [int(x.strip()) for x in args.ids.split(",")]
    engine.reanalyze(
        repo_ids=repo_ids,
        max_workers=args.workers,
        callback=_print_event,
    )


def cmd_stats(args):
    """显示统计信息"""
    repos = db.get_all_repos()
    total = len(repos)
    hidden = db.get_repo_count(include_hidden=True) - total

    if total == 0:
        print("数据库为空。")
        return

    print(f"📊 StarMind Manager 数据统计")
    print(f"  总项目数: {total} (隐藏: {hidden})")
    print(f"  数据库大小: {os.path.getsize(db.DB_PATH) / 1024:.1f} KB")

    # 分类分布
    cats = {}
    langs = {}
    for r in repos:
        cat = r.get("category", "其他") or "其他"
        cats[cat] = cats.get(cat, 0) + 1
        lang = r.get("language", "")
        if lang:
            langs[lang] = langs.get(lang, 0) + 1

    print(f"\n📂 分类分布:")
    for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
        bar = "█" * min(count, 30)
        print(f"  {cat:<20s} {count:>4d}  {bar}")

    print(f"\n💻 语言 Top 10:")
    for lang, count in sorted(langs.items(), key=lambda x: -x[1])[:10]:
        bar = "█" * min(count, 30)
        print(f"  {lang:<20s} {count:>4d}  {bar}")

    # 用户统计
    usernames = db.get_usernames()
    if usernames:
        print(f"\n👤 已同步用户: {', '.join(usernames)}")

    # 集合统计
    collections = db.get_collections()
    if collections:
        print(f"\n📁 集合:")
        for c in collections:
            print(f"  {c['name']}: {c['repo_count']} 个项目")


def cmd_search(args):
    """搜索项目"""
    repos = db.search_repos(
        query=args.query,
        category=args.category or "",
        language=args.language or "",
    )
    if not repos:
        print("未找到匹配项目。")
        return

    print(f"找到 {len(repos)} 个项目:\n")
    for r in repos[:20]:
        stars = r.get("stars", 0)
        star_str = f"{stars/1000:.1f}k" if stars >= 1000 else str(stars)
        cat = r.get("category", "")
        lang = r.get("language", "")
        print(f"  ⭐ {star_str:>6s}  {r['name']}")
        if cat or lang:
            print(f"         {cat} | {lang}")
        summary = r.get("summary", "") or r.get("description", "")
        if summary:
            print(f"         {summary[:80]}...")
        print()

    if len(repos) > 20:
        print(f"  ... 还有 {len(repos) - 20} 个结果未显示")


def cmd_compare(args):
    """对比两个用户"""
    repos = db.get_all_repos(include_hidden=True)
    if not repos:
        print("数据库为空。")
        return

    from analysis import compare_users
    result = compare_users(repos, args.user_a, args.user_b)

    print(f"\n🔍 用户 Star 对比: {args.user_a} vs {args.user_b}")
    print(f"  {args.user_a} 独有: {len(result['only_a'])} 个")
    print(f"  {args.user_b} 独有: {len(result['only_b'])} 个")
    print(f"  共同: {len(result['common'])} 个")

    if result['common']:
        print(f"\n  共同项目 Top 5:")
        for r in sorted(result['common'], key=lambda x: x.get('stars', 0), reverse=True)[:5]:
            print(f"    ⭐ {r['name']}")


def main():
    parser = argparse.ArgumentParser(
        description="StarMind Manager CLI - GitHub Star 智能管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", help="可用命令")

    # sync
    p_sync = sub.add_parser("sync", help="同步 GitHub Star")
    p_sync.add_argument("-w", "--workers", type=int, default=5, help="并发线程数 (默认 5)")
    p_sync.set_defaults(func=cmd_sync)

    # export
    p_export = sub.add_parser("export", help="导出数据")
    p_export.add_argument("-f", "--format", default="html",
                          choices=["html", "json", "csv", "markdown", "md"],
                          help="导出格式 (默认 html)")
    p_export.add_argument("-t", "--template", default=None,
                          help="HTML 模板名 (默认 index.html，可选 compact.html)")
    p_export.set_defaults(func=cmd_export)

    # reanalyze
    p_rean = sub.add_parser("reanalyze", help="重新分析项目")
    p_rean.add_argument("--ids", default=None, help="项目 ID (逗号分隔，留空分析全部)")
    p_rean.add_argument("-w", "--workers", type=int, default=3, help="并发线程数 (默认 3)")
    p_rean.set_defaults(func=cmd_reanalyze)

    # stats
    p_stats = sub.add_parser("stats", help="显示统计信息")
    p_stats.set_defaults(func=cmd_stats)

    # search
    p_search = sub.add_parser("search", help="搜索项目")
    p_search.add_argument("query", help="搜索关键词")
    p_search.add_argument("-c", "--category", default="", help="分类筛选")
    p_search.add_argument("-l", "--language", default="", help="语言筛选")
    p_search.set_defaults(func=cmd_search)

    # compare
    p_compare = sub.add_parser("compare", help="对比两个用户的 Star")
    p_compare.add_argument("user_a", help="第一个用户名")
    p_compare.add_argument("user_b", help="第二个用户名")
    p_compare.set_defaults(func=cmd_compare)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
