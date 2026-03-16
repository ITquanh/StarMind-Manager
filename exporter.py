"""
StarMind Manager - HTML 导出模块
使用 Jinja2 将数据库数据注入到 HTML 模板中，生成离线静态站点
"""

import os
import json
from jinja2 import Environment, FileSystemLoader
from db import get_all_repos

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")


def export_html(output_path: str = None) -> str:
    """
    从数据库读取全部项目数据，渲染 HTML 模板并输出到文件。
    返回输出文件的绝对路径。
    """
    if output_path is None:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        output_path = os.path.join(OUTPUT_DIR, "index.html")

    repos = get_all_repos()

    # 收集所有分类和标签（用于侧边栏过滤）
    categories = sorted(set(r["category"] for r in repos if r.get("category")))
    all_tags = set()
    for r in repos:
        if isinstance(r.get("tags"), list):
            all_tags.update(r["tags"])
    all_tags = sorted(all_tags)

    # Jinja2 渲染
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=True)
    template = env.get_template("index.html")

    html_content = template.render(
        repos_json=json.dumps(repos, ensure_ascii=False, indent=2),
        categories_json=json.dumps(categories, ensure_ascii=False),
        tags_json=json.dumps(all_tags, ensure_ascii=False),
        total_count=len(repos),
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return output_path
