"""
StarMind Manager - GitHub API 模块
支持获取任意用户的 Star 列表、获取 Readme、获取项目文件树、检查 Rate Limit
"""

import requests
import base64
import time

API_BASE = "https://api.github.com"

# GitHub Token 申请地址
TOKEN_URL = "https://github.com/settings/tokens/new?scopes=repo,read:user&description=StarMind+Manager"
TOKEN_HELP = (
    "获取 GitHub Personal Access Token (PAT) 步骤：\n"
    "1. 打开上方链接（或访问 github.com → Settings → Developer settings → Personal access tokens）\n"
    "2. 点击 'Generate new token (classic)'\n"
    "3. 勾选 'repo'（读取仓库）和 'read:user'（读取用户信息）权限\n"
    "4. 点击 'Generate token'，复制生成的 Token 粘贴到此处\n"
    "⚠️ Token 仅在生成时显示一次，请妥善保存！"
)


def _headers(token: str) -> dict:
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }


def check_rate_limit(token: str) -> dict:
    """
    查询 GitHub API 剩余额度。
    返回：{"limit": int, "remaining": int, "reset": int(unix时间戳)}
    """
    resp = requests.get(f"{API_BASE}/rate_limit", headers=_headers(token), timeout=15)
    resp.raise_for_status()
    core = resp.json()["resources"]["core"]
    return {
        "limit": core["limit"],
        "remaining": core["remaining"],
        "reset": core["reset"],
    }


def fetch_starred_repos(token: str, username: str = "", callback=None) -> list:
    """
    分页获取指定用户（或当前认证用户）的所有 Starred 仓库。
    username: 为空则获取当前 Token 对应用户的 Star；填写则获取该用户的公开 Star。
    callback(page, repos_in_page): 可选回调，每页获取后触发。
    返回全量 repo 列表（精简字段）。
    """
    all_repos = []
    page = 1
    per_page = 100  # GitHub 单页上限

    # 区分：获取自己的 vs 他人的 Star 列表
    if username.strip():
        url = f"{API_BASE}/users/{username.strip()}/starred"
    else:
        url = f"{API_BASE}/user/starred"

    while True:
        resp = requests.get(
            url,
            headers=_headers(token),
            params={"page": page, "per_page": per_page},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        if not data:
            break

        repos = []
        for item in data:
            repos.append({
                "id": item["id"],
                "name": item["full_name"],
                "stars": item["stargazers_count"],
                "language": item.get("language"),
                "url": item["html_url"],
                "description": item.get("description") or "",
                "topics": item.get("topics", []),
            })

        all_repos.extend(repos)

        if callback:
            callback(page, repos)

        # 若返回不足一页，说明已是最后一页
        if len(data) < per_page:
            break

        page += 1
        time.sleep(0.3)  # 温和限速，避免触发 GitHub 二级限频

    return all_repos


def fetch_readme(token: str, repo_full_name: str) -> str:
    """
    获取仓库的 README 内容（纯文本）。
    失败时返回空字符串。
    """
    try:
        resp = requests.get(
            f"{API_BASE}/repos/{repo_full_name}/readme",
            headers=_headers(token),
            timeout=20,
        )
        if resp.status_code == 404:
            return ""
        resp.raise_for_status()

        content = resp.json().get("content", "")
        encoding = resp.json().get("encoding", "base64")

        if encoding == "base64" and content:
            return base64.b64decode(content).decode("utf-8", errors="replace")
        return content
    except Exception:
        return ""


def fetch_repo_tree(token: str, repo_full_name: str) -> str:
    """
    获取仓库的顶层文件/目录列表，用于在无 Readme 时分析项目结构。
    返回格式化的目录树文本。失败时返回空字符串。
    """
    try:
        resp = requests.get(
            f"{API_BASE}/repos/{repo_full_name}/contents/",
            headers=_headers(token),
            timeout=15,
        )
        if resp.status_code != 200:
            return ""
        items = resp.json()
        if not isinstance(items, list):
            return ""

        lines = []
        for item in sorted(items, key=lambda x: (x.get("type", "") != "dir", x.get("name", ""))):
            icon = "📁" if item.get("type") == "dir" else "📄"
            lines.append(f"  {icon} {item['name']}")

        return f"项目 {repo_full_name} 的文件结构：\n" + "\n".join(lines)
    except Exception:
        return ""


def fetch_repo_info(token: str, repo_full_name: str) -> dict:
    """
    获取仓库的详细元信息（description, topics, language 等）。
    用作内容获取的补充手段。
    """
    try:
        resp = requests.get(
            f"{API_BASE}/repos/{repo_full_name}",
            headers=_headers(token),
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "description": data.get("description") or "",
            "topics": data.get("topics", []),
            "language": data.get("language"),
            "homepage": data.get("homepage") or "",
        }
    except Exception:
        return {}
