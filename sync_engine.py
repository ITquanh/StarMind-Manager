"""
StarMind Manager - 同步引擎
提取自 main.py 的同步/重分析逻辑，供 GUI 和 CLI 共用
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import db
import github_api
import llm


class SyncEngine:
    """同步引擎：封装 GitHub Star 同步与 LLM 重分析的核心流程"""

    def __init__(self, config: dict):
        self.config = config
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def is_stopped(self) -> bool:
        return self._stop_event.is_set()

    # ═══════════════════════════════════
    #            Star 同步
    # ═══════════════════════════════════

    def sync(self, max_workers: int = 5, callback=None):
        """
        执行完整同步流程。
        callback(event_type, data) 可接收事件：
            ('log', message: str)
            ('progress', processed, total)
            ('stats', success, fail, skip, total)
            ('done', success, fail)
        """
        self._stop_event.clear()
        cb = callback or (lambda *a: None)
        token = self.config.get("github_token", "")
        username = self.config.get("github_username", "")
        base_url = self.config.get("llm_base_url", "")
        api_key = self.config.get("llm_api_key", "")
        model = self.config.get("llm_model", "")
        has_llm = all([base_url, api_key, model])

        if not token:
            cb('log', "⚠️ GitHub Token 为空，请先配置。")
            return

        stats = {"success": 0, "fail": 0, "skip": 0}

        try:
            # Step 1: 获取远程 Star 列表
            target = username if username else "当前 Token 用户"
            cb('log', f"📡 正在获取 [{target}] 的 GitHub Star 列表...")

            def _page_cb(page, repos):
                cb('log', f"  ✓ 第 {page} 页：获取到 {len(repos)} 个项目")

            remote_repos = github_api.fetch_starred_repos(token, username=username, callback=_page_cb)
            cb('log', f"📊 远程共 {len(remote_repos)} 个 Star 项目。")

            # Step 2: 增量同步
            existing_ids = db.get_existing_ids(username)
            new_repos = [r for r in remote_repos if r["id"] not in existing_ids]
            skipped = len(remote_repos) - len(new_repos)
            stats["skip"] = skipped

            label = f"属于 {username}" if username else ""
            cb('log', f"🆕 发现 {len(new_repos)} 个新项目{label}。已跳过 {skipped} 个已备份项目。")

            if not new_repos:
                cb('log', "✅ 无新增项目，数据库已是最新。")
                cb('done', 0, 0)
                return

            # Step 3: 多线程处理
            processed = 0

            def process_one(repo):
                if self._stop_event.is_set():
                    return None
                try:
                    return self._process_repo(repo, token, username, has_llm,
                                              base_url, api_key, model, cb)
                except Exception as e:
                    cb('log', f"  ❌ 处理失败 {repo['name']}: {e}")
                    return False

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(process_one, r): r for r in new_repos}
                for future in as_completed(futures):
                    repo = futures[future]
                    result = future.result()
                    processed += 1

                    if result is True:
                        stats["success"] += 1
                        cb('log', f"  ✅ [{processed}/{len(new_repos)}] {repo['name']}")
                    elif result is False:
                        stats["fail"] += 1

                    cb('progress', processed, len(new_repos))

                    if self._stop_event.is_set():
                        break

            cb('log', f"\n🏁 同步完成！成功 {stats['success']}，失败 {stats['fail']}。")
            cb('done', stats['success'], stats['fail'])

        except Exception as e:
            cb('log', f"\n❌ 同步出错：{e}")
            cb('done', stats['success'], stats['fail'])

    def _process_repo(self, repo, token, username, has_llm,
                      base_url, api_key, model, cb) -> bool:
        """处理单个仓库：获取内容 → LLM 分析 → 入库"""
        repo_data = {
            "id": repo["id"],
            "name": repo["name"],
            "stars": repo["stars"],
            "language": repo["language"],
            "url": repo["url"],
            "description": repo["description"],
            "starred_at": repo.get("starred_at", ""),
        }

        readme_text = ""
        repo_tree = ""
        extra_desc = repo["description"]

        # 1) 获取 Readme
        cb('log', f"  📄 获取 Readme：{repo['name']}")
        readme_text = github_api.fetch_readme(token, repo["name"])

        # 2) 无 Readme 时获取详情
        if not readme_text:
            cb('log', f"  📋 无 Readme，获取项目详情：{repo['name']}")
            info = github_api.fetch_repo_info(token, repo["name"])
            if info.get("description"):
                extra_desc = info["description"]
            if info.get("topics"):
                repo_data["tags"] = info["topics"][:3]

        # 3) 无 Readme 也无描述时，获取文件树
        if not readme_text and not extra_desc:
            cb('log', f"  🌳 分析项目结构：{repo['name']}")
            repo_tree = github_api.fetch_repo_tree(token, repo["name"])

        # 4) LLM 分析
        if has_llm:
            cb('log', f"  🤖 AI 分析中：{repo['name']}")
            ai_result = llm.summarize_repo(
                base_url, api_key, model,
                readme_text=readme_text, description=extra_desc,
                repo_tree=repo_tree, repo_name=repo["name"],
                is_stopped=self._stop_event.is_set,
            )
            if ai_result:
                repo_data["summary"] = ai_result.get("summary")
                repo_data["category"] = ai_result.get("category")
                repo_data["tags"] = ai_result.get("tags", [])
                if ai_result.get("language"):
                    repo_data["language"] = ai_result["language"]

        # 5) 兜底
        if not repo_data.get("summary"):
            repo_data["summary"] = extra_desc or repo["description"]
        if not repo_data.get("tags"):
            repo_data["tags"] = repo.get("topics", [])[:3]
        if not repo_data.get("category"):
            repo_data["category"] = "其他"

        db.upsert_repo(repo_data, owner_username=username)

        # 限流保护
        if has_llm:
            for _ in range(15):
                if self._stop_event.is_set():
                    return False
                time.sleep(0.2)

        return True

    # ═══════════════════════════════════
    #          重新分析
    # ═══════════════════════════════════

    def reanalyze(self, repo_ids: list = None, max_workers: int = 3, callback=None):
        """
        重新分析指定项目（或全部）。
        repo_ids: 要重新分析的项目 ID 列表，None 表示全部
        """
        self._stop_event.clear()
        cb = callback or (lambda *a: None)
        token = self.config.get("github_token", "")
        base_url = self.config.get("llm_base_url", "")
        api_key = self.config.get("llm_api_key", "")
        model = self.config.get("llm_model", "")
        has_llm = all([base_url, api_key, model])

        if not has_llm:
            cb('log', "⚠️ 未配置 LLM，无法重新分析。")
            return

        if repo_ids:
            repos = [db.get_repo_by_id(rid) for rid in repo_ids]
            repos = [r for r in repos if r]
        else:
            repos = db.get_all_repos(include_hidden=True)

        if not repos:
            cb('log', "没有需要分析的项目。")
            return

        cb('log', f"🔄 开始重新分析 {len(repos)} 个项目...")
        processed = 0
        success = 0
        fail = 0

        def process_one(repo):
            if self._stop_event.is_set():
                return None
            try:
                repo_name = repo["name"]
                readme_text = github_api.fetch_readme(token, repo_name)
                description = repo.get("description", "")
                repo_tree = ""

                if not readme_text and not description:
                    repo_tree = github_api.fetch_repo_tree(token, repo_name)

                ai_result = llm.summarize_repo(
                    base_url, api_key, model,
                    readme_text=readme_text, description=description,
                    repo_tree=repo_tree, repo_name=repo_name,
                    is_stopped=self._stop_event.is_set,
                )

                if ai_result:
                    db.update_repo_metadata(
                        repo["id"],
                        summary=ai_result.get("summary"),
                        category=ai_result.get("category"),
                        tags=ai_result.get("tags", []),
                    )
                    return True
                return False
            except Exception as e:
                cb('log', f"  ❌ 重分析失败 {repo['name']}: {e}")
                return False

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_one, r): r for r in repos}
            for future in as_completed(futures):
                repo = futures[future]
                result = future.result()
                processed += 1
                if result is True:
                    success += 1
                    cb('log', f"  ✅ [{processed}/{len(repos)}] {repo['name']}")
                elif result is False:
                    fail += 1
                cb('progress', processed, len(repos))
                if self._stop_event.is_set():
                    break
                # 限流
                for _ in range(15):
                    if self._stop_event.is_set():
                        break
                    time.sleep(0.2)

        cb('log', f"\n🏁 重新分析完成！成功 {success}，失败 {fail}。")
        cb('done', success, fail)
