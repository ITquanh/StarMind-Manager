"""
StarMind Manager - 数据分析模块
项目相似度推荐、用户 Star 对比、收藏趋势分析
"""

from collections import Counter, defaultdict
from datetime import datetime, timedelta

import db


# ═══════════════════════════════════════
#          相似项目推荐
# ═══════════════════════════════════════

def _tag_set(tags) -> set:
    """将 tags 列表转为 set（小写去重）"""
    if isinstance(tags, str):
        import json
        try:
            tags = json.loads(tags)
        except Exception:
            tags = []
    if not isinstance(tags, list):
        return set()
    return {t.lower().strip() for t in tags if t}


def _jaccard(set_a: set, set_b: set) -> float:
    """Jaccard 相似度"""
    if not set_a and not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def find_similar_repos(repos: list, target_id: int, top_n: int = 5) -> list:
    """
    基于 tags + category + language 的综合相似度计算。
    返回最相似的 top_n 个项目列表 [{repo, score}]。
    """
    target = None
    for r in repos:
        if r["id"] == target_id:
            target = r
            break
    if not target:
        return []

    target_tags = _tag_set(target.get("tags", []))
    target_cat = (target.get("category") or "").strip()
    target_lang = (target.get("language") or "").strip().lower()

    scored = []
    for r in repos:
        if r["id"] == target_id:
            continue

        # Tag 相似度（权重 0.5）
        r_tags = _tag_set(r.get("tags", []))
        tag_sim = _jaccard(target_tags, r_tags)

        # Category 匹配（权重 0.3）
        cat_sim = 1.0 if target_cat and target_cat == (r.get("category") or "").strip() else 0.0

        # Language 匹配（权重 0.2）
        lang_sim = 1.0 if target_lang and target_lang == (r.get("language") or "").strip().lower() else 0.0

        score = tag_sim * 0.5 + cat_sim * 0.3 + lang_sim * 0.2
        if score > 0:
            scored.append({"repo": r, "score": round(score, 3)})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_n]


def build_similar_map(repos: list, top_n: int = 3) -> dict:
    """
    为所有项目预计算相似项目映射（用于注入 HTML 模板）。
    返回 {repo_id: [{id, name, score}, ...]}
    """
    result = {}
    for r in repos:
        similar = find_similar_repos(repos, r["id"], top_n=top_n)
        result[r["id"]] = [
            {"id": s["repo"]["id"], "name": s["repo"]["name"], "score": s["score"]}
            for s in similar
        ]
    return result


# ═══════════════════════════════════════
#          用户 Star 对比
# ═══════════════════════════════════════

def compare_users(repos: list, user_a: str, user_b: str) -> dict:
    """
    对比两个用户的 Star 差异。
    返回 {
        only_a: [...], only_b: [...], common: [...],
        stats_a: {count, top_categories, top_languages},
        stats_b: {count, top_categories, top_languages}
    }
    """
    repos_a = {r["id"]: r for r in repos if r.get("owner_username") == user_a}
    repos_b = {r["id"]: r for r in repos if r.get("owner_username") == user_b}

    ids_a = set(repos_a.keys())
    ids_b = set(repos_b.keys())

    common_ids = ids_a & ids_b
    only_a_ids = ids_a - ids_b
    only_b_ids = ids_b - ids_a

    def _stats(repo_dict, id_set):
        subset = [repo_dict[i] for i in id_set]
        cats = Counter(r.get("category", "其他") for r in subset)
        langs = Counter(r.get("language", "未知") for r in subset if r.get("language"))
        return {
            "count": len(subset),
            "top_categories": cats.most_common(5),
            "top_languages": langs.most_common(5),
        }

    return {
        "only_a": [repos_a[i] for i in only_a_ids],
        "only_b": [repos_b[i] for i in only_b_ids],
        "common": [repos_a[i] for i in common_ids],
        "stats_a": _stats(repos_a, ids_a),
        "stats_b": _stats(repos_b, ids_b),
        "user_a": user_a,
        "user_b": user_b,
    }


# ═══════════════════════════════════════
#           收藏趋势分析
# ═══════════════════════════════════════

def analyze_trends(repos: list, recent_days: int = 30) -> dict:
    """
    分析收藏趋势：
    - 近期 vs 早期的分类分布变化
    - 新兴标签
    - 热门方向
    返回 {recent_categories, early_categories, rising_categories, new_tags, summary}
    """
    now = datetime.now()
    cutoff = now - timedelta(days=recent_days)

    recent = []
    early = []
    for r in repos:
        starred_at = r.get("starred_at", "")
        if not starred_at:
            early.append(r)
            continue
        try:
            dt = datetime.fromisoformat(starred_at.replace("Z", "+00:00").split("+")[0])
            if dt >= cutoff:
                recent.append(r)
            else:
                early.append(r)
        except (ValueError, TypeError):
            early.append(r)

    # 分类分布
    recent_cats = Counter(r.get("category", "其他") for r in recent)
    early_cats = Counter(r.get("category", "其他") for r in early)

    # 计算分类增长（近期占比 vs 早期占比）
    recent_total = max(len(recent), 1)
    early_total = max(len(early), 1)
    rising = {}
    all_cats = set(list(recent_cats.keys()) + list(early_cats.keys()))
    for cat in all_cats:
        recent_pct = recent_cats.get(cat, 0) / recent_total
        early_pct = early_cats.get(cat, 0) / early_total
        delta = recent_pct - early_pct
        if delta > 0.02:  # 增长超过 2%
            rising[cat] = round(delta * 100, 1)

    # 新兴标签（近期出现但早期没有）
    recent_tags = Counter()
    early_tags = set()
    for r in recent:
        for t in _tag_set(r.get("tags", [])):
            recent_tags[t] += 1
    for r in early:
        for t in _tag_set(r.get("tags", [])):
            early_tags.add(t)

    new_tags = {tag: count for tag, count in recent_tags.most_common(20)
                if tag not in early_tags}

    # 生成摘要
    summary_parts = []
    if recent:
        summary_parts.append(f"最近 {recent_days} 天收藏了 {len(recent)} 个项目")
    if rising:
        top_rising = sorted(rising.items(), key=lambda x: x[1], reverse=True)[:3]
        directions = "、".join(f"{cat}(+{pct}%)" for cat, pct in top_rising)
        summary_parts.append(f"趋势方向：{directions}")
    if new_tags:
        tags_preview = "、".join(list(new_tags.keys())[:5])
        summary_parts.append(f"新兴标签：{tags_preview}")

    return {
        "recent_count": len(recent),
        "early_count": len(early),
        "recent_categories": dict(recent_cats.most_common()),
        "early_categories": dict(early_cats.most_common()),
        "rising_categories": rising,
        "new_tags": new_tags,
        "summary": "。".join(summary_parts) if summary_parts else "暂无足够数据进行趋势分析",
    }
