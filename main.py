"""
StarMind Manager - 主程序（GUI 入口）
基于 CustomTkinter 的四面板管理界面
v2.0: 管理Tab、编辑弹窗、集合、批量操作、多格式导出、快捷键、定时同步
"""

import os
import sys
import threading
import json
import webbrowser
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import customtkinter as ctk
from tkinter import filedialog, messagebox

import db
import github_api
import llm
import exporter
from sync_engine import SyncEngine

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
        self.title("\u2b50 StarMind Manager")
        self.geometry("1020x720")
        self.minsize(900, 620)

        self._running = False
        self._stop_event = threading.Event()
        self._stats = {"success": 0, "fail": 0, "skip": 0, "total": 0}
        self._config = load_config()
        self._engine = SyncEngine(self._config)
        self._schedule_job = None
        self._mgmt_page = 1
        self._mgmt_page_size = 50
        self._mgmt_total = 0
        self._mgmt_check_vars = {}

        self._build_ui()
        self._restore_config()
        self._bind_shortcuts()

    # ═══════════════════════════════════
    #              UI 构建
    # ═══════════════════════════════════

    def _build_ui(self):
        self.tabview = ctk.CTkTabview(self, anchor="nw")
        self.tabview.pack(fill="both", expand=True, padx=12, pady=(8, 12))
        self._build_config_tab()
        self._build_task_tab()
        self._build_management_tab()
        self._build_export_tab()

    # ────────── Tab 1: 配置 ──────────

    def _build_config_tab(self):
        tab = self.tabview.add("\u2699\ufe0f \u914d\u7f6e")

        gh_frame = ctk.CTkFrame(tab)
        gh_frame.pack(fill="x", padx=10, pady=(10, 5))
        ctk.CTkLabel(gh_frame, text="\U0001f511  GitHub \u914d\u7f6e",
                     font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=12, pady=(10, 4))

        for label, attr, placeholder, show in [
            ("Personal Access Token\uff1a", "gh_token_entry", "ghp_xxxxxxxxxxxx", "\u2022"),
            ("GitHub \u7528\u6237\u540d (\u53ef\u9009)\uff1a", "gh_username_entry",
             "\u7559\u7a7a\u5219\u83b7\u53d6 Token \u62e5\u6709\u8005\u7684 Star", None),
        ]:
            row = ctk.CTkFrame(gh_frame, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=4)
            ctk.CTkLabel(row, text=label, width=180, anchor="e").pack(side="left")
            entry = ctk.CTkEntry(row, placeholder_text=placeholder, show=show or "")
            entry.pack(side="left", fill="x", expand=True, padx=(4, 0))
            setattr(self, attr, entry)

        row_help = ctk.CTkFrame(gh_frame, fg_color="transparent")
        row_help.pack(fill="x", padx=12, pady=(2, 4))
        ctk.CTkButton(row_help, text="\U0001f50d \u68c0\u6d4b Rate Limit", width=150,
                      command=self._check_rate_limit).pack(side="left")
        ctk.CTkButton(row_help, text="\U0001f517 \u83b7\u53d6 Token", width=120,
                      fg_color="#6366f1", hover_color="#4f46e5",
                      command=lambda: webbrowser.open(github_api.TOKEN_URL)).pack(side="left", padx=8)
        self.rate_label = ctk.CTkLabel(row_help, text="", text_color="gray")
        self.rate_label.pack(side="left", padx=8)

        help_frame = ctk.CTkFrame(gh_frame, fg_color=("gray92", "gray17"))
        help_frame.pack(fill="x", padx=12, pady=(2, 10))
        ctk.CTkLabel(help_frame, text=github_api.TOKEN_HELP,
                     font=ctk.CTkFont(size=11), text_color=("gray40", "gray60"),
                     justify="left", wraplength=700).pack(padx=10, pady=8, anchor="w")

        # LLM section
        llm_frame = ctk.CTkFrame(tab)
        llm_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(llm_frame, text="\U0001f916  LLM \u914d\u7f6e",
                     font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=12, pady=(10, 4))

        for lt, an, ph, sc in [
            ("Base URL\uff1a", "llm_url_entry", "https://api.openai.com/v1", None),
            ("API Key\uff1a", "llm_key_entry", "sk-xxxxxxxx", "\u2022"),
            ("\u6a21\u578b\u540d\u79f0\uff1a", "llm_model_entry",
             "gpt-3.5-turbo / deepseek-chat", None),
        ]:
            row = ctk.CTkFrame(llm_frame, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=3)
            ctk.CTkLabel(row, text=lt, width=180, anchor="e").pack(side="left")
            entry = ctk.CTkEntry(row, placeholder_text=ph, show=sc or "")
            entry.pack(side="left", fill="x", expand=True, padx=(4, 0))
            setattr(self, an, entry)

        row_btn2 = ctk.CTkFrame(llm_frame, fg_color="transparent")
        row_btn2.pack(fill="x", padx=12, pady=(2, 10))
        ctk.CTkButton(row_btn2, text="\U0001f9ea \u6d4b\u8bd5\u8fde\u901a\u6027",
                      width=140, command=self._test_llm).pack(side="left")
        self.llm_test_label = ctk.CTkLabel(row_btn2, text="", text_color="gray")
        self.llm_test_label.pack(side="left", padx=12)

        llm_help = ctk.CTkFrame(llm_frame, fg_color=("gray92", "gray17"))
        llm_help.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkLabel(llm_help,
                     text="\U0001f4a1 \u652f\u6301\u6240\u6709 OpenAI \u517c\u5bb9\u63a5\u53e3\uff08DeepSeek\u3001Qwen\u3001Kimi\u3001Ollama \u7b49\uff09\n   Base URL \u793a\u4f8b\uff1ahttps://api.deepseek.com/v1",
                     font=ctk.CTkFont(size=11), text_color=("gray40", "gray60"),
                     justify="left").pack(padx=10, pady=6, anchor="w")

        # Schedule section
        sched_frame = ctk.CTkFrame(tab)
        sched_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(sched_frame, text="\U0001f552  \u5b9a\u65f6\u540c\u6b65",
                     font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=12, pady=(10, 4))
        sched_row = ctk.CTkFrame(sched_frame, fg_color="transparent")
        sched_row.pack(fill="x", padx=12, pady=(2, 10))
        self.schedule_var = ctk.BooleanVar(value=self._config.get("schedule_enabled", False))
        ctk.CTkCheckBox(sched_row, text="\u542f\u7528\u5b9a\u65f6\u540c\u6b65",
                        variable=self.schedule_var,
                        command=self._toggle_schedule).pack(side="left")
        self.schedule_combo = ctk.CTkComboBox(
            sched_row, values=["\u6bcf\u5c0f\u65f6", "\u6bcf\u5929", "\u6bcf\u5468"],
            width=100, command=lambda v: self._toggle_schedule())
        self.schedule_combo.set(self._config.get("schedule_interval", "\u6bcf\u5929"))
        self.schedule_combo.pack(side="left", padx=12)
        self.schedule_status = ctk.CTkLabel(sched_row, text="", text_color="gray")
        self.schedule_status.pack(side="left", padx=8)

        ctk.CTkButton(tab, text="\U0001f4be \u4fdd\u5b58\u914d\u7f6e",
                      command=self._save_config, height=36).pack(pady=10)

    # ────────── Tab 2: 任务 ──────────

    def _build_task_tab(self):
        tab = self.tabview.add("\U0001f680 \u4efb\u52a1")
        slider_frame = ctk.CTkFrame(tab, fg_color="transparent")
        slider_frame.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(slider_frame, text="\u5e76\u53d1\u7ebf\u7a0b\u6570\uff1a").pack(side="left")
        self.thread_label = ctk.CTkLabel(slider_frame, text="5", width=30,
                                          font=ctk.CTkFont(weight="bold"))
        self.thread_label.pack(side="left", padx=(4, 8))
        self.thread_slider = ctk.CTkSlider(
            slider_frame, from_=1, to=20, number_of_steps=19,
            command=lambda v: self.thread_label.configure(text=str(int(v))))
        self.thread_slider.set(5)
        self.thread_slider.pack(side="left", fill="x", expand=True)

        btn_frame = ctk.CTkFrame(tab, fg_color="transparent")
        btn_frame.pack(fill="x", padx=12, pady=6)
        self.start_btn = ctk.CTkButton(
            btn_frame, text="\u25b6 \u5f00\u59cb\u540c\u6b65",
            fg_color="#16a34a", hover_color="#15803d",
            command=self._start_sync, height=38)
        self.start_btn.pack(side="left", padx=(0, 8))
        self.stop_btn = ctk.CTkButton(
            btn_frame, text="\u23f9 \u505c\u6b62",
            fg_color="#dc2626", hover_color="#b91c1c",
            command=self._stop_sync, state="disabled", height=38)
        self.stop_btn.pack(side="left")

        self.progress_bar = ctk.CTkProgressBar(tab)
        self.progress_bar.pack(fill="x", padx=12, pady=(6, 2))
        self.progress_bar.set(0)
        self.stats_label = ctk.CTkLabel(tab, text="\u5c31\u7eea", text_color="gray")
        self.stats_label.pack(anchor="w", padx=14)
        self.log_box = ctk.CTkTextbox(tab, state="disabled",
                                       font=ctk.CTkFont(family="Consolas", size=12))
        self.log_box.pack(fill="both", expand=True, padx=12, pady=(6, 10))

    # ────────── Tab 3: 管理 ──────────

    def _build_management_tab(self):
        tab = self.tabview.add("\U0001f4cb \u7ba1\u7406")

        filter_frame = ctk.CTkFrame(tab)
        filter_frame.pack(fill="x", padx=10, pady=(10, 5))
        self.mgmt_search = ctk.CTkEntry(filter_frame,
                                         placeholder_text="\u641c\u7d22\u9879\u76ee\u540d\u3001\u6458\u8981...",
                                         width=250)
        self.mgmt_search.pack(side="left", padx=(10, 5), pady=8)
        self.mgmt_search.bind("<Return>", lambda e: self._refresh_management())

        self.mgmt_cat_var = ctk.StringVar(value="\u5168\u90e8")
        self.mgmt_cat_combo = ctk.CTkComboBox(
            filter_frame, values=["\u5168\u90e8"], variable=self.mgmt_cat_var,
            width=150, command=lambda v: self._refresh_management())
        self.mgmt_cat_combo.pack(side="left", padx=5, pady=8)

        self.mgmt_hidden_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(filter_frame, text="\u663e\u793a\u9690\u85cf",
                        variable=self.mgmt_hidden_var,
                        command=self._refresh_management).pack(side="left", padx=5, pady=8)
        ctk.CTkButton(filter_frame, text="\U0001f50d \u641c\u7d22", width=80,
                      command=self._refresh_management).pack(side="left", padx=5, pady=8)

        self.mgmt_scroll = ctk.CTkScrollableFrame(tab, label_text="\u9879\u76ee\u5217\u8868")
        self.mgmt_scroll.pack(fill="both", expand=True, padx=10, pady=5)

        page_frame = ctk.CTkFrame(tab, fg_color="transparent")
        page_frame.pack(fill="x", padx=10, pady=4)
        self.mgmt_prev_btn = ctk.CTkButton(
            page_frame, text="\u25c0 \u4e0a\u4e00\u9875", width=80,
            command=lambda: self._mgmt_change_page(-1))
        self.mgmt_prev_btn.pack(side="left")
        self.mgmt_page_label = ctk.CTkLabel(page_frame, text="\u7b2c 1 \u9875")
        self.mgmt_page_label.pack(side="left", padx=12)
        self.mgmt_next_btn = ctk.CTkButton(
            page_frame, text="\u4e0b\u4e00\u9875 \u25b6", width=80,
            command=lambda: self._mgmt_change_page(1))
        self.mgmt_next_btn.pack(side="left")
        self.mgmt_count_label = ctk.CTkLabel(page_frame, text="", text_color="gray")
        self.mgmt_count_label.pack(side="right", padx=8)

        batch_frame = ctk.CTkFrame(tab)
        batch_frame.pack(fill="x", padx=10, pady=(2, 5))
        self.mgmt_select_all_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(batch_frame, text="\u5168\u9009",
                        variable=self.mgmt_select_all_var,
                        command=self._mgmt_select_all).pack(side="left", padx=5, pady=6)
        ctk.CTkButton(batch_frame, text="\U0001f5d1 \u6279\u91cf\u5220\u9664", width=90,
                      fg_color="#dc2626", hover_color="#b91c1c",
                      command=self._batch_delete).pack(side="left", padx=3, pady=6)
        ctk.CTkButton(batch_frame, text="\U0001f441 \u6279\u91cf\u9690\u85cf", width=90,
                      command=self._batch_hide).pack(side="left", padx=3, pady=6)

        self.batch_cat_var = ctk.StringVar(value="\u6279\u91cf\u6539\u5206\u7c7b")
        ctk.CTkComboBox(
            batch_frame,
            values=["AI\u4e0e\u5927\u6a21\u578b", "\u540e\u7aef\u5f00\u53d1",
                    "\u524d\u7aef\u5f00\u53d1", "\u79fb\u52a8\u7aef\u5f00\u53d1",
                    "\u6570\u636e\u5e93\u4e0e\u5b58\u50a8", "\u8fd0\u7ef4/DevOps",
                    "\u6d4b\u8bd5\u4e0e\u5b89\u5168", "\u6548\u7387\u8f85\u52a9\u5de5\u5177",
                    "\u684c\u9762\u7cfb\u7edf\u5e94\u7528", "\u722c\u866b\u4e0e\u6570\u636e\u63d0\u53d6",
                    "\u5f71\u97f3\u5a92\u4f53\u5904\u7406", "\u72ec\u7acb\u6e38\u620f\u4e0e\u5f00\u53d1\u5f15\u64ce",
                    "\u533a\u5757\u94fe/Web3", "\u5b66\u4e60\u6559\u7a0b\u4e0e\u8d44\u6599",
                    "\u5176\u4ed6"],
            variable=self.batch_cat_var, width=120,
            command=self._batch_change_cat).pack(side="left", padx=3, pady=6)

        self.batch_coll_var = ctk.StringVar(value="\u52a0\u5165\u96c6\u5408")
        self.batch_coll_combo = ctk.CTkComboBox(
            batch_frame, values=["\u52a0\u5165\u96c6\u5408"],
            variable=self.batch_coll_var, width=120,
            command=self._batch_add_to_collection)
        self.batch_coll_combo.pack(side="left", padx=3, pady=6)

        ctk.CTkButton(batch_frame, text="\ud83d\udd04 \u91cd\u5206\u6790\u82f1\u6587\u7b80\u4ecb", width=140,
                      fg_color="#6366f1", hover_color="#4f46e5",
                      command=self._reanalyze_english).pack(side="left", padx=8, pady=6)

        coll_frame = ctk.CTkFrame(tab)
        coll_frame.pack(fill="x", padx=10, pady=(0, 5))
        ctk.CTkLabel(coll_frame, text="\U0001f4c1 \u96c6\u5408\u7ba1\u7406:",
                     font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(10, 5), pady=6)
        self.new_coll_entry = ctk.CTkEntry(coll_frame,
                                            placeholder_text="\u65b0\u96c6\u5408\u540d", width=150)
        self.new_coll_entry.pack(side="left", padx=3, pady=6)
        ctk.CTkButton(coll_frame, text="\u521b\u5efa", width=60,
                      command=self._create_collection).pack(side="left", padx=3, pady=6)
        ctk.CTkButton(coll_frame, text="\u67e5\u770b\u96c6\u5408", width=80,
                      command=self._open_collection_dialog).pack(side="left", padx=3, pady=6)

        self._refresh_management()

    # ────────── Tab 4: 导出 ──────────

    def _build_export_tab(self):
        tab = self.tabview.add("\U0001f4e4 \u5bfc\u51fa")
        info_frame = ctk.CTkFrame(tab)
        info_frame.pack(fill="x", padx=10, pady=15)
        self.db_count_label = ctk.CTkLabel(info_frame,
                                            text="\u6570\u636e\u5e93\u4e2d\u5171 0 \u4e2a\u9879\u76ee",
                                            font=ctk.CTkFont(size=14))
        self.db_count_label.pack(pady=12)
        ctk.CTkButton(info_frame, text="\U0001f504 \u5237\u65b0\u7edf\u8ba1", width=140,
                      command=self._refresh_count).pack(pady=(0, 12))

        fmt_frame = ctk.CTkFrame(tab)
        fmt_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(fmt_frame, text="\u5bfc\u51fa\u683c\u5f0f\uff1a",
                     font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=12, pady=(10, 4))
        self.export_format_var = ctk.StringVar(value="html_card")
        for val, label in [
            ("html_card", "\U0001f310 HTML \u77e5\u8bc6\u5e93\uff08\u5361\u7247\u89c6\u56fe\uff09"),
            ("html_list", "\U0001f4cb HTML \u77e5\u8bc6\u5e93\uff08\u5217\u8868\u89c6\u56fe\uff09"),
            ("markdown", "\U0001f4dd Markdown \u6587\u6863"),
            ("json", "\U0001f4e6 JSON \u6570\u636e\uff08\u53ef\u5907\u4efd\u6062\u590d\uff09"),
            ("csv", "\U0001f4ca CSV \u8868\u683c"),
        ]:
            ctk.CTkRadioButton(fmt_frame, text=label, variable=self.export_format_var,
                               value=val).pack(anchor="w", padx=20, pady=2)

        ctk.CTkButton(tab, text="\U0001f4e4 \u5bfc\u51fa", height=42,
                      font=ctk.CTkFont(size=14, weight="bold"),
                      command=self._do_export).pack(pady=15)
        self.export_status_label = ctk.CTkLabel(tab, text="", text_color="gray")
        self.export_status_label.pack()

        import_frame = ctk.CTkFrame(tab)
        import_frame.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(import_frame, text="\U0001f4e5 \u5bfc\u5165\u6570\u636e",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=12, pady=(10, 4))
        ctk.CTkLabel(import_frame,
                     text="\u652f\u6301 JSON\uff08\u5907\u4efd\u6587\u4ef6\uff09\u548c CSV \u683c\u5f0f",
                     text_color="gray").pack(anchor="w", padx=12)
        ctk.CTkButton(import_frame, text="\U0001f4c2 \u9009\u62e9\u6587\u4ef6\u5bfc\u5165",
                      width=160, command=self._import_data).pack(padx=12, pady=10)

    # ═══════════════════════════════════
    #          快捷键
    # ═══════════════════════════════════

    def _bind_shortcuts(self):
        self.bind("<Control-s>", lambda e: self._start_sync())
        self.bind("<Escape>", lambda e: self._stop_sync())
        self.bind("<Control-k>", lambda e: self.mgmt_search.focus_set())

    # ═══════════════════════════════════
    #        配置 Tab 功能逻辑
    # ═══════════════════════════════════

    def _restore_config(self):
        cfg = self._config
        for attr, key in [("gh_token_entry", "github_token"),
                          ("gh_username_entry", "github_username"),
                          ("llm_url_entry", "llm_base_url"),
                          ("llm_key_entry", "llm_api_key"),
                          ("llm_model_entry", "llm_model")]:
            if cfg.get(key):
                getattr(self, attr).insert(0, cfg[key])
        self._refresh_count()
        self._refresh_mgmt_categories()
        self._refresh_mgmt_collections()
        self._toggle_schedule()

    def _save_config(self):
        self._config = {
            "github_token": self.gh_token_entry.get().strip(),
            "github_username": self.gh_username_entry.get().strip(),
            "llm_base_url": self.llm_url_entry.get().strip(),
            "llm_api_key": self.llm_key_entry.get().strip(),
            "llm_model": self.llm_model_entry.get().strip(),
            "schedule_enabled": self.schedule_var.get(),
            "schedule_interval": self.schedule_combo.get(),
        }
        save_config(self._config)
        self._engine = SyncEngine(self._config)
        self._log("\u2705 配置已保存。")

    def _get_token(self):
        return self.gh_token_entry.get().strip()

    def _get_username(self):
        return self.gh_username_entry.get().strip()

    def _get_llm_params(self):
        return (self.llm_url_entry.get().strip(),
                self.llm_key_entry.get().strip(),
                self.llm_model_entry.get().strip())

    def _check_rate_limit(self):
        token = self._get_token()
        if not token:
            self.rate_label.configure(text="\u26a0\ufe0f 请先填写 Token", text_color="orange")
            return
        try:
            info = github_api.check_rate_limit(token)
            color = "green" if info["remaining"] > 100 else "orange"
            self.rate_label.configure(
                text=f"剩余 {info['remaining']} / {info['limit']}", text_color=color)
        except Exception as e:
            self.rate_label.configure(text=f"\u274c {e}", text_color="red")

    def _test_llm(self):
        base_url, api_key, model = self._get_llm_params()
        if not all([base_url, api_key, model]):
            self.llm_test_label.configure(text="\u26a0\ufe0f 请填写完整参数", text_color="orange")
            return
        self.llm_test_label.configure(text="\U0001f504 测试中...", text_color="gray")
        self.update()

        def _do():
            ok, msg = llm.test_connection(base_url, api_key, model)
            self.after(0, lambda: self.llm_test_label.configure(
                text=msg, text_color="green" if ok else "red"))
        threading.Thread(target=_do, daemon=True).start()

    # ═══════════════════════════════════
    #         任务 Tab 功能逻辑
    # ═══════════════════════════════════

    def _start_sync(self):
        if self._running:
            return
        token = self._get_token()
        if not token:
            self._log("\u26a0\ufe0f GitHub Token 为空，请先在「配置」填写。")
            return

        # 从 UI 实时读取最新配置
        self._config = {
            "github_token": self.gh_token_entry.get().strip(),
            "github_username": self.gh_username_entry.get().strip(),
            "llm_base_url": self.llm_url_entry.get().strip(),
            "llm_api_key": self.llm_key_entry.get().strip(),
            "llm_model": self.llm_model_entry.get().strip(),
            "schedule_enabled": self.schedule_var.get(),
            "schedule_interval": self.schedule_combo.get(),
        }

        self._running = True
        self._stop_event.clear()
        self._stats = {"success": 0, "fail": 0, "skip": 0, "total": 0}
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.progress_bar.set(0)

        self._engine = SyncEngine(self._config)
        max_workers = int(self.thread_slider.get())
        threading.Thread(target=self._engine.sync,
                         kwargs={"max_workers": max_workers,
                                 "callback": self._sync_callback},
                         daemon=True).start()

    def _stop_sync(self):
        if self._running:
            self._engine.stop()
            self._log("\U0001f6d1 正在停止...")

    def _sync_callback(self, event_type, *args):
        if event_type == "log":
            self._log(args[0] if args else "")
        elif event_type == "progress":
            processed = args[0] if len(args) > 0 else 0
            total = args[1] if len(args) > 1 else 0
            pct = processed / total if total else 0
            # 使用默认参数捕获当前值，避免闭包延迟绑定导致所有回调显示最终值
            self.after(0, lambda p=pct: self.progress_bar.set(p))
            self.after(0, lambda p=processed, t=total, pc=pct: self.stats_label.configure(
                text=f"进度: {p}/{t} ({int(pc*100)}%)"))
        elif event_type == "done":
            success = args[0] if len(args) > 0 else 0
            fail = args[1] if len(args) > 1 else 0
            self.after(0, lambda s=success, f=fail: messagebox.showinfo(
                "同步完成", f"成功: {s}\n失败: {f}"))
            self.after(0, self._finish_sync)

    def _finish_sync(self):
        self._running = False
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self._refresh_count()
        self._refresh_management()

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

    # ═══════════════════════════════════
    #        管理 Tab 功能逻辑
    # ═══════════════════════════════════

    def _refresh_mgmt_categories(self):
        cats = ["\u5168\u90e8"] + db.get_all_categories()
        self.mgmt_cat_combo.configure(values=cats)

    def _refresh_mgmt_collections(self):
        colls = [c["name"] for c in db.get_collections()]
        values = ["\u52a0\u5165\u96c6\u5408"] + colls
        self.batch_coll_combo.configure(values=values)

    def _refresh_management(self):
        search = self.mgmt_search.get().strip()
        cat = self.mgmt_cat_var.get()
        include_hidden = self.mgmt_hidden_var.get()
        if cat == "\u5168\u90e8":
            cat = ""

        repos, total = db.get_repos_paged(
            page=self._mgmt_page, page_size=self._mgmt_page_size,
            category=cat, search=search, include_hidden=include_hidden)
        self._mgmt_total = total
        self._mgmt_check_vars.clear()

        # Clear scroll frame
        for w in self.mgmt_scroll.winfo_children():
            w.destroy()

        # Build header
        hdr = ctk.CTkFrame(self.mgmt_scroll, fg_color=("gray80", "gray25"))
        hdr.pack(fill="x", pady=(0, 2))
        for txt, w in [("", 30), ("项目名称", 200), ("Star", 60), ("分类", 100),
                        ("标签", 150), ("操作", 200)]:
            ctk.CTkLabel(hdr, text=txt, width=w, font=ctk.CTkFont(size=11, weight="bold"),
                         anchor="w").pack(side="left", padx=2, pady=4)

        # Build rows
        for repo in repos:
            self._mgmt_build_row(self.mgmt_scroll, repo)

        # Update pagination
        total_pages = max(1, (total + self._mgmt_page_size - 1) // self._mgmt_page_size)
        self.mgmt_page_label.configure(text=f"\u7b2c {self._mgmt_page}/{total_pages} \u9875")
        self.mgmt_count_label.configure(text=f"\u5171 {total} \u4e2a\u9879\u76ee")
        self.mgmt_prev_btn.configure(state="normal" if self._mgmt_page > 1 else "disabled")
        self.mgmt_next_btn.configure(state="normal" if self._mgmt_page < total_pages else "disabled")

    def _mgmt_build_row(self, parent, repo):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=1)

        var = ctk.BooleanVar(value=False)
        self._mgmt_check_vars[repo["id"]] = var
        ctk.CTkCheckBox(row, text="", variable=var, width=30).pack(side="left", padx=2)

        name_text = repo["name"]
        if repo.get("hidden"):
            name_text += " [hidden]"
        ctk.CTkLabel(row, text=name_text, width=200, anchor="w",
                     font=ctk.CTkFont(size=11)).pack(side="left", padx=2)

        stars = repo.get("stars", 0)
        star_str = f"{stars/1000:.1f}k" if stars >= 1000 else str(stars)
        ctk.CTkLabel(row, text=star_str, width=60,
                     font=ctk.CTkFont(size=11)).pack(side="left", padx=2)

        cat = repo.get("category", "") or ""
        ctk.CTkLabel(row, text=cat, width=100, anchor="w",
                     font=ctk.CTkFont(size=11)).pack(side="left", padx=2)

        tags = repo.get("tags", [])
        tags_str = ", ".join(tags[:2]) if isinstance(tags, list) else ""
        ctk.CTkLabel(row, text=tags_str, width=150, anchor="w",
                     font=ctk.CTkFont(size=10), text_color="gray").pack(side="left", padx=2)

        # Action buttons
        act = ctk.CTkFrame(row, fg_color="transparent", width=200)
        act.pack(side="left", padx=2)
        ctk.CTkButton(act, text="\u270f\ufe0f", width=30, height=24,
                      command=lambda r=repo: self._open_edit_dialog(r["id"])).pack(side="left", padx=1)
        hidden_text = "\U0001f441" if not repo.get("hidden") else "\U0001f441\ufe0f"
        ctk.CTkButton(act, text=hidden_text, width=30, height=24,
                      command=lambda r=repo: self._toggle_hide(r)).pack(side="left", padx=1)
        fav_text = "\u2b50" if repo.get("favorite") else "\u2606"
        ctk.CTkButton(act, text=fav_text, width=30, height=24,
                      command=lambda r=repo: self._toggle_fav(r["id"])).pack(side="left", padx=1)
        ctk.CTkButton(act, text="\U0001f5d1", width=30, height=24, fg_color="#dc2626",
                      hover_color="#b91c1c",
                      command=lambda r=repo: self._delete_single(r)).pack(side="left", padx=1)

    def _mgmt_change_page(self, delta):
        self._mgmt_page = max(1, self._mgmt_page + delta)
        self._refresh_management()

    def _mgmt_select_all(self):
        val = self.mgmt_select_all_var.get()
        for var in self._mgmt_check_vars.values():
            var.set(val)

    def _get_selected_ids(self):
        return [rid for rid, var in self._mgmt_check_vars.items() if var.get()]

    def _toggle_hide(self, repo):
        db.toggle_hidden(repo["id"], not repo.get("hidden", False))
        self._refresh_management()

    def _toggle_fav(self, repo_id):
        db.toggle_favorite(repo_id)
        self._refresh_management()

    def _delete_single(self, repo):
        if messagebox.askyesno("确认删除", f"确定删除 {repo['name']}？"):
            db.hard_delete_repo(repo["id"])
            self._refresh_management()
            self._refresh_count()

    # ──── 编辑弹窗 ────

    def _open_edit_dialog(self, repo_id):
        repo = db.get_repo_by_id(repo_id)
        if not repo:
            return

        dlg = ctk.CTkToplevel(self)
        dlg.title(f"\u7f16\u8f91: {repo['name']}")
        dlg.geometry("520x560")
        dlg.transient(self)
        dlg.grab_set()

        ctk.CTkLabel(dlg, text=f"\u7f16\u8f91 {repo['name']}",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(padx=12, pady=(12, 6))

        ctk.CTkLabel(dlg, text="\u6458\u8981:").pack(anchor="w", padx=12)
        summary_box = ctk.CTkTextbox(dlg, height=120)
        summary_box.pack(fill="x", padx=12, pady=2)
        if repo.get("summary"):
            summary_box.insert("1.0", repo["summary"])

        ctk.CTkLabel(dlg, text="\u5206\u7c7b:").pack(anchor="w", padx=12, pady=(6, 0))
        cat_var = ctk.StringVar(value=repo.get("category", "\u5176\u4ed6"))
        cat_combo = ctk.CTkComboBox(
            dlg, variable=cat_var, width=300,
            values=["AI\u4e0e\u5927\u6a21\u578b", "\u540e\u7aef\u5f00\u53d1",
                    "\u524d\u7aef\u5f00\u53d1", "\u79fb\u52a8\u7aef\u5f00\u53d1",
                    "\u6570\u636e\u5e93\u4e0e\u5b58\u50a8", "\u8fd0\u7ef4/DevOps",
                    "\u6d4b\u8bd5\u4e0e\u5b89\u5168", "\u6548\u7387\u8f85\u52a9\u5de5\u5177",
                    "\u684c\u9762\u7cfb\u7edf\u5e94\u7528", "\u722c\u866b\u4e0e\u6570\u636e\u63d0\u53d6",
                    "\u5f71\u97f3\u5a92\u4f53\u5904\u7406", "\u72ec\u7acb\u6e38\u620f\u4e0e\u5f00\u53d1\u5f15\u64ce",
                    "\u533a\u5757\u94fe/Web3", "\u5b66\u4e60\u6559\u7a0b\u4e0e\u8d44\u6599",
                    "\u5176\u4ed6"])
        cat_combo.pack(padx=12, pady=2, anchor="w")

        ctk.CTkLabel(dlg, text="\u6807\u7b7e (\u9017\u53f7\u5206\u9694):").pack(anchor="w", padx=12, pady=(6, 0))
        tags_entry = ctk.CTkEntry(dlg, width=400)
        tags_entry.pack(padx=12, pady=2, anchor="w")
        if repo.get("tags") and isinstance(repo["tags"], list):
            tags_entry.insert(0, ", ".join(repo["tags"]))

        ctk.CTkLabel(dlg, text="\u5907\u6ce8:").pack(anchor="w", padx=12, pady=(6, 0))
        notes_box = ctk.CTkTextbox(dlg, height=60)
        notes_box.pack(fill="x", padx=12, pady=2)
        if repo.get("notes"):
            notes_box.insert("1.0", repo["notes"])

        status_lbl = ctk.CTkLabel(dlg, text="", text_color="gray")
        status_lbl.pack(pady=4)

        def _save():
            tags_text = tags_entry.get().strip()
            tags_list = [t.strip() for t in tags_text.split(",") if t.strip()] if tags_text else []
            db.update_repo_metadata(
                repo_id,
                summary=summary_box.get("1.0", "end-1c").strip() or None,
                category=cat_var.get(),
                tags=tags_list,
                notes=notes_box.get("1.0", "end-1c").strip() or None,
            )
            status_lbl.configure(text="\u2705 \u5df2\u4fdd\u5b58", text_color="green")
            self._refresh_management()

        def _reanalyze():
            status_lbl.configure(text="\U0001f504 AI \u91cd\u65b0\u5206\u6790\u4e2d...", text_color="gray")
            dlg.update()

            def _do():
                engine = SyncEngine(self._config)
                engine.reanalyze(repo_ids=[repo_id], callback=self._sync_callback)

            threading.Thread(target=_do, daemon=True).start()

        btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_row.pack(fill="x", padx=12, pady=10)
        ctk.CTkButton(btn_row, text="\U0001f4be \u4fdd\u5b58", command=_save).pack(side="left", padx=5)
        ctk.CTkButton(btn_row, text="\U0001f916 AI \u91cd\u65b0\u5206\u6790",
                      fg_color="#6366f1", hover_color="#4f46e5",
                      command=_reanalyze).pack(side="left", padx=5)
        ctk.CTkButton(btn_row, text="\u5173\u95ed", command=dlg.destroy).pack(side="right", padx=5)

    # ──── 集合弹窗 ────

    def _open_collection_dialog(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title("\u96c6\u5408\u7ba1\u7406")
        dlg.geometry("600x450")
        dlg.transient(self)
        dlg.grab_set()

        ctk.CTkLabel(dlg, text="\U0001f4c1 \u96c6\u5408\u7ba1\u7406",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(padx=12, pady=(12, 6))

        main_frame = ctk.CTkFrame(dlg)
        main_frame.pack(fill="both", expand=True, padx=12, pady=6)

        # Left: collection list
        left = ctk.CTkFrame(main_frame, width=200)
        left.pack(side="left", fill="y", padx=(0, 6), pady=6)
        ctk.CTkLabel(left, text="\u96c6\u5408\u5217\u8868",
                     font=ctk.CTkFont(weight="bold")).pack(pady=4)

        coll_scroll = ctk.CTkScrollableFrame(left, width=180)
        coll_scroll.pack(fill="both", expand=True, padx=4, pady=4)

        selected_coll = {"name": ""}  # \u7528 dict \u5305\u88c5\u4ee5\u4fbf\u5728\u95ed\u5305\u4e2d\u4fee\u6539

        # Right: repos in collection
        right = ctk.CTkFrame(main_frame)
        right.pack(side="right", fill="both", expand=True, pady=6)
        ctk.CTkLabel(right, text="\u96c6\u5408\u5185\u9879\u76ee",
                     font=ctk.CTkFont(weight="bold")).pack(pady=4)
        repo_listbox = ctk.CTkTextbox(right, state="disabled")
        repo_listbox.pack(fill="both", expand=True, padx=4, pady=4)

        def _select_coll(name):
            selected_coll["name"] = name
            _show_coll_repos()

        def _refresh_coll():
            for w in coll_scroll.winfo_children():
                w.destroy()
            colls = db.get_collections()
            for c in colls:
                btn = ctk.CTkButton(
                    coll_scroll, text=f"{c['name']} ({c['repo_count']}\u9879)",
                    anchor="w", width=170, height=28,
                    command=lambda n=c["name"]: _select_coll(n))
                btn.pack(fill="x", pady=1)
            self._refresh_mgmt_collections()
            # \u81ea\u52a8\u9009\u4e2d\u7b2c\u4e00\u4e2a\u96c6\u5408
            if colls and not selected_coll["name"]:
                selected_coll["name"] = colls[0]["name"]
                _show_coll_repos()

        def _show_coll_repos():
            name = selected_coll["name"]
            if not name:
                return
            repos = db.get_collection_repos(name)
            repo_listbox.configure(state="normal")
            repo_listbox.delete("1.0", "end")
            for r in repos:
                repo_listbox.insert("end", f"\u2b50 {r.get('stars',0)} {r['name']}\n")
            repo_listbox.configure(state="disabled")

        def _delete_selected():
            name = selected_coll["name"]
            if not name:
                return
            if messagebox.askyesno("\u786e\u8ba4", f"\u5220\u9664\u96c6\u5408 [{name}]\uff1f"):
                db.delete_collection(name)
                selected_coll["name"] = ""
                _refresh_coll()

        btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_row.pack(fill="x", padx=12, pady=6)
        ctk.CTkButton(btn_row, text="\U0001f504 \u5237\u65b0", width=80,
                      command=_refresh_coll).pack(side="left", padx=4)
        ctk.CTkButton(btn_row, text="\U0001f5d1 \u5220\u9664\u96c6\u5408", width=100,
                      fg_color="#dc2626", hover_color="#b91c1c",
                      command=_delete_selected).pack(side="left", padx=4)
        ctk.CTkButton(btn_row, text="\u5173\u95ed", width=80,
                      command=dlg.destroy).pack(side="right", padx=4)

        _refresh_coll()

    # ──── 集合操作 ────

    def _create_collection(self):
        name = self.new_coll_entry.get().strip()
        if not name:
            return
        db.create_collection(name)
        self.new_coll_entry.delete(0, "end")
        self._refresh_mgmt_collections()
        self._log(f"\u2705 \u96c6\u5408 [{name}] \u5df2\u521b\u5efa。")

    # ──── 批量操作 ────

    def _batch_delete(self):
        ids = self._get_selected_ids()
        if not ids:
            return
        if messagebox.askyesno("\u786e\u8ba4", f"\u786e\u5b9a\u5220\u9664 {len(ids)} \u4e2a\u9879\u76ee\uff1f"):
            db.batch_delete(ids)
            self._refresh_management()
            self._refresh_count()

    def _batch_hide(self):
        ids = self._get_selected_ids()
        if not ids:
            return
        db.batch_toggle_hidden(ids, True)
        self._refresh_management()

    def _batch_change_cat(self, new_cat):
        ids = self._get_selected_ids()
        if not ids or new_cat == "\u6279\u91cf\u6539\u5206\u7c7b":
            return
        db.batch_update_category(ids, new_cat)
        self._refresh_management()
        self._log(f"\u2705 \u5df2\u5c06 {len(ids)} \u4e2a\u9879\u76ee\u5206\u7c7b\u4e3a [{new_cat}]")

    def _batch_add_to_collection(self, coll_name):
        ids = self._get_selected_ids()
        if not ids or coll_name == "\u52a0\u5165\u96c6\u5408":
            return
        db.batch_add_to_collection(coll_name, ids)
        self._log(f"\u2705 \u5df2\u5c06 {len(ids)} \u4e2a\u9879\u76ee\u52a0\u5165 [{coll_name}]")

    def _reanalyze_english(self):
        """\u91cd\u65b0\u5206\u6790\u6240\u6709\u7b80\u4ecb\u4e3a\u82f1\u6587\u7684\u9879\u76ee"""
        if self._running:
            messagebox.showwarning("\u63d0\u793a", "\u5f53\u524d\u6709\u4efb\u52a1\u6b63\u5728\u8fd0\u884c\uff0c\u8bf7\u7b49\u5f85\u5b8c\u6210\u3002")
            return
        # \u5b9e\u65f6\u8bfb\u53d6\u6700\u65b0\u914d\u7f6e
        self._config = {
            "github_token": self.gh_token_entry.get().strip(),
            "github_username": self.gh_username_entry.get().strip(),
            "llm_base_url": self.llm_url_entry.get().strip(),
            "llm_api_key": self.llm_key_entry.get().strip(),
            "llm_model": self.llm_model_entry.get().strip(),
        }
        base_url = self._config.get("llm_base_url", "")
        api_key = self._config.get("llm_api_key", "")
        model = self._config.get("llm_model", "")
        if not all([base_url, api_key, model]):
            messagebox.showwarning("\u63d0\u793a", "\u8bf7\u5148\u5728\u300c\u914d\u7f6e\u300d\u9875\u586b\u5199 LLM \u76f8\u5173\u914d\u7f6e\u3002")
            return

        repo_ids = db.get_english_summary_repo_ids()
        if not repo_ids:
            messagebox.showinfo("\u63d0\u793a", "\u2705 \u6ca1\u6709\u53d1\u73b0\u82f1\u6587\u7b80\u4ecb\u7684\u9879\u76ee\uff0c\u65e0\u9700\u5904\u7406\u3002")
            return

        if not messagebox.askyesno("\u786e\u8ba4",
                                   f"\u53d1\u73b0 {len(repo_ids)} \u4e2a\u82f1\u6587\u7b80\u4ecb\u9879\u76ee\uff0c\u5c06\u8c03\u7528 AI \u91cd\u65b0\u5206\u6790\u3002\n\n\u662f\u5426\u7ee7\u7eed\uff1f"):
            return

        self._running = True
        self._stop_event.clear()
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.progress_bar.set(0)
        self._log(f"\ud83d\udd04 \u5f00\u59cb\u91cd\u65b0\u5206\u6790 {len(repo_ids)} \u4e2a\u82f1\u6587\u7b80\u4ecb\u9879\u76ee...")

        self._engine = SyncEngine(self._config)
        threading.Thread(
            target=self._engine.reanalyze,
            kwargs={"repo_ids": repo_ids,
                    "max_workers": 3,
                    "callback": self._sync_callback},
            daemon=True
        ).start()

    # ═══════════════════════════════════
    #          定时同步
    # ═══════════════════════════════════

    def _toggle_schedule(self):
        if self._schedule_job:
            self.after_cancel(self._schedule_job)
            self._schedule_job = None

        if self.schedule_var.get():
            interval = self.schedule_combo.get()
            ms = {"每小时": 3600000, "每天": 86400000, "每周": 604800000}.get(interval, 86400000)
            self.schedule_status.configure(
                text=f"\u2705 \u5c06\u5728 {interval} \u540e\u81ea\u52a8\u540c\u6b65",
                text_color="green")
            self._schedule_job = self.after(ms, self._scheduled_sync)
        else:
            self.schedule_status.configure(text="\u274c \u5df2\u7981\u7528", text_color="gray")

    def _scheduled_sync(self):
        if not self._running:
            self._log("\U0001f552 \u5b9a\u65f6\u540c\u6b65\u5f00\u59cb...")
            self._start_sync()
        # Reschedule
        self._toggle_schedule()

    # ═══════════════════════════════════
    #          导出 Tab 功能
    # ═══════════════════════════════════

    def _refresh_count(self):
        total = db.get_repo_count()
        hidden = db.get_repo_count(include_hidden=True) - total
        self.db_count_label.configure(text=f"\u6570\u636e\u5e93\u4e2d\u5171 {total} \u4e2a\u9879\u76ee (\u9690\u85cf: {hidden})")

    def _do_export(self):
        repos = db.get_all_repos()
        if not repos:
            self.export_status_label.configure(
                text="\u26a0\ufe0f \u6570\u636e\u5e93\u4e3a\u7a7a\uff0c\u8bf7\u5148\u6267\u884c\u540c\u6b65\u3002",
                text_color="orange")
            return

        fmt = self.export_format_var.get()
        try:
            if fmt == "html_card":
                path = exporter.export_html(repos=repos, template_name="index.html")
            elif fmt == "html_list":
                path = exporter.export_html(repos=repos, template_name="compact.html")
            elif fmt == "markdown":
                path = exporter.export_markdown(repos)
            elif fmt == "json":
                path = exporter.export_json(repos)
            elif fmt == "csv":
                path = exporter.export_csv(repos)
            else:
                return

            self.export_status_label.configure(
                text=f"\u2705 \u5df2\u5bfc\u51fa\u5230\uff1a{path}", text_color="green")
            self._log(f"\U0001f4e4 \u5df2\u5bfc\u51fa\uff1a{path}")
            if fmt.startswith("html"):
                from pathlib import Path
                webbrowser.open(Path(path).as_uri())
        except Exception as e:
            self.export_status_label.configure(
                text=f"\u274c \u5bfc\u51fa\u5931\u8d25\uff1a{e}", text_color="red")

    # ═══════════════════════════════════
    #          导入功能
    # ═══════════════════════════════════

    def _import_data(self):
        filepath = filedialog.askopenfilename(
            filetypes=[("JSON \u6587\u4ef6", "*.json"),
                       ("CSV \u6587\u4ef6", "*.csv"),
                       ("\u6240\u6709\u6587\u4ef6", "*.*")])
        if not filepath:
            return
        ext = os.path.splitext(filepath)[1].lower()
        if ext == ".json":
            threading.Thread(target=self._import_json, args=(filepath,), daemon=True).start()
        elif ext == ".csv":
            threading.Thread(target=self._import_csv, args=(filepath,), daemon=True).start()
        else:
            self._log("\u26a0\ufe0f \u4e0d\u652f\u6301\u7684\u6587\u4ef6\u683c\u5f0f")

    def _import_json(self, filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            repos = data.get("repos", data) if isinstance(data, dict) else data
            count = 0
            for r in repos:
                if "id" in r and "name" in r:
                    db.upsert_repo(r, owner_username=r.get("owner_username", ""))
                    count += 1
            self._log(f"\u2705 JSON \u5bfc\u5165\u5b8c\u6210\uff0c\u5171 {count} \u4e2a\u9879\u76ee")
            self.after(0, lambda: [self._refresh_count(), self._refresh_management()])
        except Exception as e:
            self._log(f"\u274c JSON \u5bfc\u5165\u5931\u8d25\uff1a{e}")

    def _import_csv(self, filepath):
        try:
            with open(filepath, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                count = 0
                for row in reader:
                    if "id" not in row or "name" not in row:
                        continue
                    tags_str = row.get("tags", "")
                    tags = [t.strip() for t in tags_str.split(";") if t.strip()] if tags_str else []
                    repo = {
                        "id": int(row["id"]),
                        "name": row["name"],
                        "stars": int(row.get("stars", 0)),
                        "summary": row.get("summary", ""),
                        "category": row.get("category", ""),
                        "tags": tags,
                        "language": row.get("language", ""),
                        "url": row.get("url", ""),
                        "description": row.get("description", ""),
                        "starred_at": row.get("starred_at", ""),
                    }
                    db.upsert_repo(repo, owner_username=row.get("owner_username", ""))
                    count += 1
            self._log(f"\u2705 CSV \u5bfc\u5165\u5b8c\u6210\uff0c\u5171 {count} \u4e2a\u9879\u76ee")
            self.after(0, lambda: [self._refresh_count(), self._refresh_management()])
        except Exception as e:
            self._log(f"\u274c CSV \u5bfc\u5165\u5931\u8d25\uff1a{e}")


def main():
    app = StarMindApp()
    app.mainloop()


if __name__ == "__main__":
    main()
