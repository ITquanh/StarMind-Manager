"""
StarMind Manager - 主程序（GUI 入口）
基于 CustomTkinter 的三面板管理界面
支持获取任意 GitHub 用户的 Star 项目
"""

import os
import sys
import threading
import json
import webbrowser
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import customtkinter as ctk

import db
import github_api
import llm
import exporter

# ──────────── 全局样式 ────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_config(cfg: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


class StarMindApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("⭐ StarMind Manager")
        self.geometry("920x680")
        self.minsize(820, 580)

        self._running = False
        self._stop_event = threading.Event()
        self._stats = {"success": 0, "fail": 0, "skip": 0, "total": 0}
        self._config = load_config()

        self._build_ui()
        self._restore_config()

    # ═══════════════════════════════════
    #              UI 构建
    # ═══════════════════════════════════

    def _build_ui(self):
        self.tabview = ctk.CTkTabview(self, anchor="nw")
        self.tabview.pack(fill="both", expand=True, padx=12, pady=(8, 12))

        self._build_config_tab()
        self._build_task_tab()
        self._build_export_tab()

    # ────────── Tab 1: 配置 ──────────

    def _build_config_tab(self):
        tab = self.tabview.add("⚙️ 配置")

        # -- GitHub 区 --
        gh_frame = ctk.CTkFrame(tab)
        gh_frame.pack(fill="x", padx=10, pady=(10, 5))

        ctk.CTkLabel(gh_frame, text="🔑  GitHub 配置", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=12, pady=(10, 4))

        # GitHub Token
        row_token = ctk.CTkFrame(gh_frame, fg_color="transparent")
        row_token.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(row_token, text="Personal Access Token：", width=180, anchor="e").pack(side="left")
        self.gh_token_entry = ctk.CTkEntry(row_token, show="•", placeholder_text="ghp_xxxxxxxxxxxx")
        self.gh_token_entry.pack(side="left", fill="x", expand=True, padx=(4, 0))

        # 目标用户名（支持获取任意用户）
        row_user = ctk.CTkFrame(gh_frame, fg_color="transparent")
        row_user.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(row_user, text="GitHub 用户名 (可选)：", width=180, anchor="e").pack(side="left")
        self.gh_username_entry = ctk.CTkEntry(row_user, placeholder_text="留空则获取 Token 拥有者的 Star")
        self.gh_username_entry.pack(side="left", fill="x", expand=True, padx=(4, 0))

        # 帮助按钮行
        row_help = ctk.CTkFrame(gh_frame, fg_color="transparent")
        row_help.pack(fill="x", padx=12, pady=(2, 4))
        self.rate_btn = ctk.CTkButton(row_help, text="🔍 检测 Rate Limit", width=150, command=self._check_rate_limit)
        self.rate_btn.pack(side="left")
        self.get_token_btn = ctk.CTkButton(
            row_help, text="🔗 获取 Token", width=120,
            fg_color="#6366f1", hover_color="#4f46e5",
            command=lambda: webbrowser.open(github_api.TOKEN_URL)
        )
        self.get_token_btn.pack(side="left", padx=8)
        self.rate_label = ctk.CTkLabel(row_help, text="", text_color="gray")
        self.rate_label.pack(side="left", padx=8)

        # Token 获取帮助说明
        help_frame = ctk.CTkFrame(gh_frame, fg_color=("gray92", "gray17"))
        help_frame.pack(fill="x", padx=12, pady=(2, 10))
        ctk.CTkLabel(
            help_frame,
            text=github_api.TOKEN_HELP,
            font=ctk.CTkFont(size=11),
            text_color=("gray40", "gray60"),
            justify="left",
            wraplength=700,
        ).pack(padx=10, pady=8, anchor="w")

        # -- LLM 区 --
        llm_frame = ctk.CTkFrame(tab)
        llm_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(llm_frame, text="🤖  LLM 配置", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=12, pady=(10, 4))

        for label_text, attr_name, placeholder, show_char in [
            ("Base URL：", "llm_url_entry", "https://api.openai.com/v1", None),
            ("API Key：", "llm_key_entry", "sk-xxxxxxxx", "•"),
            ("模型名称：", "llm_model_entry", "gpt-3.5-turbo / deepseek-chat", None),
        ]:
            row = ctk.CTkFrame(llm_frame, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=3)
            ctk.CTkLabel(row, text=label_text, width=180, anchor="e").pack(side="left")
            entry = ctk.CTkEntry(row, placeholder_text=placeholder, show=show_char or "")
            entry.pack(side="left", fill="x", expand=True, padx=(4, 0))
            setattr(self, attr_name, entry)

        row_btn2 = ctk.CTkFrame(llm_frame, fg_color="transparent")
        row_btn2.pack(fill="x", padx=12, pady=(2, 10))
        self.llm_test_btn = ctk.CTkButton(row_btn2, text="🧪 测试连通性", width=140, command=self._test_llm)
        self.llm_test_btn.pack(side="left")
        self.llm_test_label = ctk.CTkLabel(row_btn2, text="", text_color="gray")
        self.llm_test_label.pack(side="left", padx=12)

        # LLM 帮助文本
        llm_help_frame = ctk.CTkFrame(llm_frame, fg_color=("gray92", "gray17"))
        llm_help_frame.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkLabel(
            llm_help_frame,
            text="💡 支持所有 OpenAI 兼容接口（DeepSeek、Qwen、Kimi、Ollama 等）\n   Base URL 示例：https://api.deepseek.com/v1",
            font=ctk.CTkFont(size=11),
            text_color=("gray40", "gray60"),
            justify="left",
        ).pack(padx=10, pady=6, anchor="w")

        # 保存按钮
        ctk.CTkButton(tab, text="💾 保存配置", command=self._save_config, height=36).pack(pady=10)

    # ────────── Tab 2: 任务 ──────────

    def _build_task_tab(self):
        tab = self.tabview.add("🚀 任务")

        # 并发滑块
        slider_frame = ctk.CTkFrame(tab, fg_color="transparent")
        slider_frame.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(slider_frame, text="并发线程数：").pack(side="left")
        self.thread_label = ctk.CTkLabel(slider_frame, text="5", width=30, font=ctk.CTkFont(weight="bold"))
        self.thread_label.pack(side="left", padx=(4, 8))
        self.thread_slider = ctk.CTkSlider(slider_frame, from_=1, to=20, number_of_steps=19,
                                            command=lambda v: self.thread_label.configure(text=str(int(v))))
        self.thread_slider.set(5)
        self.thread_slider.pack(side="left", fill="x", expand=True)

        # 控制按钮行
        btn_frame = ctk.CTkFrame(tab, fg_color="transparent")
        btn_frame.pack(fill="x", padx=12, pady=6)
        self.start_btn = ctk.CTkButton(btn_frame, text="▶ 开始同步", fg_color="#16a34a", hover_color="#15803d",
                                        command=self._start_sync, height=38)
        self.start_btn.pack(side="left", padx=(0, 8))
        self.stop_btn = ctk.CTkButton(btn_frame, text="⏹ 停止", fg_color="#dc2626", hover_color="#b91c1c",
                                       command=self._stop_sync, state="disabled", height=38)
        self.stop_btn.pack(side="left")

        # 进度条 + 计数
        self.progress_bar = ctk.CTkProgressBar(tab)
        self.progress_bar.pack(fill="x", padx=12, pady=(6, 2))
        self.progress_bar.set(0)
        self.stats_label = ctk.CTkLabel(tab, text="就绪", text_color="gray")
        self.stats_label.pack(anchor="w", padx=14)

        # 日志文本框
        self.log_box = ctk.CTkTextbox(tab, state="disabled", font=ctk.CTkFont(family="Consolas", size=12))
        self.log_box.pack(fill="both", expand=True, padx=12, pady=(6, 10))

    # ────────── Tab 3: 导出 ──────────

    def _build_export_tab(self):
        tab = self.tabview.add("📤 导出")

        info_frame = ctk.CTkFrame(tab)
        info_frame.pack(fill="x", padx=10, pady=15)

        self.db_count_label = ctk.CTkLabel(info_frame, text="数据库中共 0 个项目", font=ctk.CTkFont(size=14))
        self.db_count_label.pack(pady=12)

        ctk.CTkButton(info_frame, text="🔄 刷新统计", width=140, command=self._refresh_count).pack(pady=(0, 12))

        ctk.CTkButton(tab, text="🌐 导出为 HTML 知识库", height=42, font=ctk.CTkFont(size=14, weight="bold"),
                       command=self._export_html).pack(pady=20)

        self.export_status_label = ctk.CTkLabel(tab, text="", text_color="gray")
        self.export_status_label.pack()

    # ═══════════════════════════════════
    #             功能逻辑
    # ═══════════════════════════════════

    def _restore_config(self):
        cfg = self._config
        if cfg.get("github_token"):
            self.gh_token_entry.insert(0, cfg["github_token"])
        if cfg.get("github_username"):
            self.gh_username_entry.insert(0, cfg["github_username"])
        if cfg.get("llm_base_url"):
            self.llm_url_entry.insert(0, cfg["llm_base_url"])
        if cfg.get("llm_api_key"):
            self.llm_key_entry.insert(0, cfg["llm_api_key"])
        if cfg.get("llm_model"):
            self.llm_model_entry.insert(0, cfg["llm_model"])
        self._refresh_count()

    def _save_config(self):
        self._config = {
            "github_token": self.gh_token_entry.get().strip(),
            "github_username": self.gh_username_entry.get().strip(),
            "llm_base_url": self.llm_url_entry.get().strip(),
            "llm_api_key": self.llm_key_entry.get().strip(),
            "llm_model": self.llm_model_entry.get().strip(),
        }
        save_config(self._config)
        self._log("✅ 配置已保存到本地。")

    def _get_token(self) -> str:
        return self.gh_token_entry.get().strip()

    def _get_username(self) -> str:
        return self.gh_username_entry.get().strip()

    def _get_llm_params(self) -> tuple:
        return (
            self.llm_url_entry.get().strip(),
            self.llm_key_entry.get().strip(),
            self.llm_model_entry.get().strip(),
        )

    # ──── Rate Limit ────

    def _check_rate_limit(self):
        token = self._get_token()
        if not token:
            self.rate_label.configure(text="⚠️ 请先填写 Token", text_color="orange")
            return
        try:
            info = github_api.check_rate_limit(token)
            self.rate_label.configure(
                text=f"剩余 {info['remaining']} / {info['limit']}",
                text_color="green" if info["remaining"] > 100 else "orange"
            )
        except Exception as e:
            self.rate_label.configure(text=f"❌ {e}", text_color="red")

    # ──── LLM 测试 ────

    def _test_llm(self):
        base_url, api_key, model = self._get_llm_params()
        if not all([base_url, api_key, model]):
            self.llm_test_label.configure(text="⚠️ 请填写完整 LLM 参数", text_color="orange")
            return
        self.llm_test_label.configure(text="🔄 测试中...", text_color="gray")
        self.update()

        def _do():
            ok, msg = llm.test_connection(base_url, api_key, model)
            self.after(0, lambda: self.llm_test_label.configure(
                text=msg, text_color="green" if ok else "red"))

        threading.Thread(target=_do, daemon=True).start()

    # ──── 同步主流程 ────

    def _start_sync(self):
        token = self._get_token()
        if not token:
            self._log("⚠️ GitHub Token 为空，请先在「配置」填写。")
            return

        self._running = True
        self._stop_event.clear()
        self._stats = {"success": 0, "fail": 0, "skip": 0, "total": 0}
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.progress_bar.set(0)

        threading.Thread(target=self._sync_worker, daemon=True).start()

    def _stop_sync(self):
        self._stop_event.set()
        self._log("🛑 正在停止同步...")

    def _sync_worker(self):
        """后台同步工作线程"""
        token = self._get_token()
        username = self._get_username()
        base_url, api_key, model = self._get_llm_params()
        has_llm = all([base_url, api_key, model])

        try:
            # Step 1: 获取远程 Star 列表
            target = username if username else "当前 Token 用户"
            self._log(f"📡 正在获取 [{target}] 的 GitHub Star 列表...")
            remote_repos = github_api.fetch_starred_repos(
                token,
                username=username,
                callback=lambda page, repos: self._log(f"  ✓ 第 {page} 页：获取到 {len(repos)} 个项目")
            )
            self._log(f"📊 远程共 {len(remote_repos)} 个 Star 项目。")

            # Step 2: 进度恢复与按用户增量同步
            # 只获取当前要同步的这个用户的已存在记录
            existing_ids = db.get_existing_ids(username)
            new_repos = [r for r in remote_repos if r["id"] not in existing_ids]
            
            # 记录跳过数量
            skipped_count = len(remote_repos) - len(new_repos)
            if username:
                self._log(f"🆕 发现 {len(new_repos)} 个新项目（属于 {username}）。已跳过 {skipped_count} 个已备份项目。")
            else:
                self._log(f"🆕 发现 {len(new_repos)} 个新项目。已跳过 {skipped_count} 个已备份项目。")

            self._stats["total"] = len(new_repos)
            self._stats["skip"] = skipped_count

            if not new_repos:
                self._log("✅ 无新增项目，数据库已是最新。")
                self._finish_sync()
                return

            # Step 3: 多线程处理每个新项目
            max_workers = int(self.thread_slider.get())
            processed = 0

            def process_one(repo):
                """
                单个项目处理流程 —— 多级内容获取策略：
                1. 尝试获取 Readme 文本
                2. 使用项目 Description
                3. 获取项目文件树结构
                4. 将上述内容传入 LLM 进行分析（LLM 内部也会按优先级使用）
                5. 若 LLM 全部失败，回填 GitHub 原始数据
                """
                if self._stop_event.is_set():
                    return None
                try:
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
                    self._log(f"  📄 获取 Readme：{repo['name']}")
                    readme_text = github_api.fetch_readme(token, repo["name"])

                    # 2) 获取更详细的项目信息
                    if not readme_text:
                        self._log(f"  📋 无 Readme，获取项目详情：{repo['name']}")
                        info = github_api.fetch_repo_info(token, repo["name"])
                        if info.get("description"):
                            extra_desc = info["description"]
                        if info.get("topics"):
                            repo_data["tags"] = info["topics"][:3]

                    # 3) 无 Readme 也无有效描述时，获取文件结构
                    if not readme_text and not extra_desc:
                        self._log(f"  🌳 分析项目结构：{repo['name']}")
                        repo_tree = github_api.fetch_repo_tree(token, repo["name"])

                    # 4) 调用 LLM 分析（多级降级策略）
                    if has_llm:
                        self._log(f"  🤖 AI 分析中：{repo['name']}")
                        ai_result = llm.summarize_repo(
                            base_url, api_key, model,
                            readme_text=readme_text,
                            description=extra_desc,
                            repo_tree=repo_tree,
                            repo_name=repo["name"],
                            is_stopped=self._stop_event.is_set,
                        )
                        if ai_result:
                            repo_data["summary"] = ai_result.get("summary")
                            repo_data["category"] = ai_result.get("category")
                            repo_data["tags"] = ai_result.get("tags", [])
                            if ai_result.get("language"):
                                repo_data["language"] = ai_result["language"]

                    # 5) 最终兜底：无 AI 结果时回填原始数据
                    if not repo_data.get("summary"):
                        repo_data["summary"] = extra_desc or repo["description"]
                    if not repo_data.get("tags"):
                        repo_data["tags"] = repo.get("topics", [])[:3]
                    if not repo_data.get("category"):
                        repo_data["category"] = "其他"

                    # 落库，带上当前的 owner_username
                    db.upsert_repo(repo_data, owner_username=username)

                    # 为免费版 API 增加 3 秒冷却保护，防止触发每分钟请求频率限制
                    if has_llm:
                        import time
                        for _ in range(15):
                            if self._stop_event.is_set():
                                return False
                            time.sleep(0.2)

                    return True
                except Exception as e:
                    self._log(f"  ❌ 处理失败 {repo['name']}: {e}")
                    return False

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(process_one, r): r for r in new_repos}
                for future in as_completed(futures):
                    repo = futures[future]
                    result = future.result()
                    processed += 1

                    if result is True:
                        self._stats["success"] += 1
                        self._log(f"  ✅ [{processed}/{len(new_repos)}] {repo['name']}")
                    elif result is False:
                        self._stats["fail"] += 1

                    progress = processed / len(new_repos) if new_repos else 1
                    self.after(0, lambda p=progress: self.progress_bar.set(p))
                    self.after(0, self._update_stats_label)

                    if self._stop_event.is_set():
                        break

            self._log(f"\n🏁 同步完成！成功 {self._stats['success']}，失败 {self._stats['fail']}。")

        except Exception as e:
            self._log(f"\n❌ 同步出错：{e}")
        finally:
            self._finish_sync()

    def _finish_sync(self):
        self._running = False
        self.after(0, lambda: self.start_btn.configure(state="normal"))
        self.after(0, lambda: self.stop_btn.configure(state="disabled"))
        self.after(0, self._refresh_count)

    def _update_stats_label(self):
        s = self._stats
        self.stats_label.configure(
            text=f"✅ 成功 {s['success']}  ❌ 失败 {s['fail']}  ⏭ 跳过 {s['skip']}  / 总计 {s['total'] + s['skip']}"
        )

    # ──── 导出 ────

    def _refresh_count(self):
        count = db.get_repo_count()
        self.db_count_label.configure(text=f"数据库中共 {count} 个项目")

    def _export_html(self):
        try:
            count = db.get_repo_count()
            if count == 0:
                self.export_status_label.configure(text="⚠️ 数据库为空，请先执行同步任务。", text_color="orange")
                return
            path = exporter.export_html()
            self.export_status_label.configure(text=f"✅ 已导出到：{path}", text_color="green")
            self._log(f"📤 HTML 已导出：{path}")
            webbrowser.open(f"file://{path}")
        except Exception as e:
            self.export_status_label.configure(text=f"❌ 导出失败：{e}", text_color="red")

    # ──── 日志 ────

    def _log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}\n"

        def _append():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", line)
            self.log_box.see("end")
            self.log_box.configure(state="disabled")

        if threading.current_thread() is threading.main_thread():
            _append()
        else:
            self.after(0, _append)


def main():
    app = StarMindApp()
    app.mainloop()


if __name__ == "__main__":
    main()
