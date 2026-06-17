# ⭐ StarMind Manager v2.0

一款面向开发者的 **GitHub Star 资产智能管理与可视化知识库工具**。用 AI 将你收藏的项目转化为结构化的中文知识库，支持离线搜索、标签过滤、数据分析、集合分组与多格式导出。

> **v2.0 新版特性**：全新引入数据管理面板、集合分组、Chart.js 数据仪表盘、相似度推荐、趋势分析、多格式导出、定时同步及完整的 CLI 命令行工具，提供 24 项全新功能扩展。

---

## ✨ 核心功能

*   **🤖 AI 智能分析与翻译**：
    *   **深度分析**：自动读取 README/Description 提取生成中文摘要、技术分类与标签。
    *   **英文翻译兜底**：自动识别英文简介并翻译为中文摘要，保证非中文项目的阅读体验。
    *   **重分析功能**：支持对所有英文简介或特定项目一键调用 AI 进行重新分析。
*   **📋 强大的数据管理**：
    *   **分页表格**：在桌面端提供清晰的项目管理表格，支持手动编辑分类、摘要、标签与备注。
    *   **集合分组 (Collections)**：支持自定义集合，可对 Star 项目进行归类与收藏。
    *   **批量操作**：支持批量删除、批量修改分类以及批量加入集合。
*   **📊 数据可视化 Dashboard**：
    *   **图表分析**：内置 Chart.js 生成分类分布饼图、语言占比柱状图、Star 分布图与收藏时间线趋势图。
    *   **数据发现**：支持标签云展示、基于 Jaccard 算法的**相似项目推荐**以及**收藏趋势分析**。
*   **📤 多格式导出与数据导入**：
    *   **五种导出格式**：支持导出为精美 HTML 卡片、紧凑型 HTML 列表、Markdown 文档、JSON 数据（可用于备份）、CSV 表格。
    *   **筛选后导出**：支持根据管理面板中筛选后的结果进行精准导出。
    *   **导入恢复**：支持一键导入 JSON 备份或 CSV 文件恢复数据库。
*   **💻 命令行 CLI 模式**：
    *   提供完整的 `cli.py` 命令行程序，内置 6 大子命令，支持无界面（Headless）同步与服务器自动化运行。
*   **📦 Windows 一键运行**：
    *   内置一键打包脚本 `build.bat`。提供 Windows 免安装压缩包，解压后可直接双击运行。

---

## 🚀 快速开始

### 方式 A：直接运行 (Windows 免安装版)

1. 下载项目 Release 中的 [StarMind-Manager-Windows.zip](file:///C:/Users/84787/Desktop/GetGithub/StarMind-Manager-Windows.zip)。
2. 解压压缩包。
3. 双击解压目录中的 **`StarMind Manager.exe`** 即可打开图形界面使用。

### 方式 B：源码运行 (开发者模式)

#### 1. 环境要求
*   Python 3.10+
*   Git

#### 2. 安装步骤
```bash
# 克隆项目
git clone https://github.com/ITquanh/StarMind-Manager.git
cd StarMind-Manager

# 安装依赖
pip install -r requirements.txt
```

#### 3. 启动图形界面
```bash
python main.py
```

---

## 💻 CLI 命令行模式使用

StarMind Manager 提供了完整的命令行操作，方便进行自动化和服务器部署：

```bash
# 查看所有命令
python cli.py --help

# 1. 增量同步 GitHub Stars
python cli.py sync --workers 5

# 2. 导出知识库 (支持 html/json/csv/markdown)
python cli.py export -f html -t compact.html --output-dir ./my_export

# 3. 查看数据库统计信息
python cli.py stats

# 4. 离线全文搜索项目
python cli.py search "web app" --category "前端开发"

# 5. 重新分析项目 (支持仅重新分析英文简介项目)
python cli.py reanalyze --english-only --workers 3

# 6. 对比两个用户的 Star 差异
python cli.py compare user_a user_b
```

---

## 📖 GUI 界面指南

应用界面分为四大核心 Tab 页面：

1.  **⚙️ 配置 Tab**：
    *   配置 GitHub Token（[点此创建](https://github.com/settings/tokens/new?scopes=repo,read:user&description=StarMind+Manager)）和目标用户名。
    *   配置兼容 OpenAI 的大模型 API（如 DeepSeek、Qwen、Ollama、GPT 等）。
    *   设置**定时自动同步**（每小时/每天/每周）。
2.  **🚀 任务 Tab**：
    *   调整并发线程数。
    *   一键启动同步，实时查看进度条、完成率和详细日志，支持中途平滑停止。
3.  **📋 管理 Tab**：
    *   分页查看所有项目，支持按名称、分类、语言进行搜索和多重筛选。
    *   支持对单条项目进行详情查看、编辑（修改摘要/分类/标签/备注/收藏）、软删除/硬删除。
    *   右键或通过底部面板进行**批量操作**和**集合管理**。
4.  **📤 导出 Tab**：
    *   选择导出格式与导出模板，一键生成静态离线站点。
    *   支持从外部导入 JSON / CSV 数据，方便进行数据库的迁移与备份恢复。

---

## 🛠️ 技术栈

| 模块 | 使用技术 |
| :--- | :--- |
| **桌面 GUI** | CustomTkinter (Python 现代 GUI 库) |
| **本地数据库** | SQLite3 |
| **核心引擎** | requests + ThreadPoolExecutor + OpenAI SDK |
| **数据分析** | Jaccard 相似度算法 + 收藏趋势变化分析 |
| **导出模块** | Jinja2 模板引擎 |
| **离线知识库** | Vue 3 + Tailwind CSS + Fuse.js (模糊搜索) + Chart.js (图表) |
| **打包工具** | PyInstaller |

---

## 🔒 安全说明

*   所有的 GitHub Token、LLM API Key 以及项目数据全部**保存在本地本地**的 `config.json` 和 `starmind.db` 中，不经过任何第三方服务器。
*   打包生成的 `dist/` 和 `build/` 目录以及敏感配置文件 `config.json` 均已在 `.gitignore` 中配置忽略，防止意外推送到公开仓库。

---

## 📄 许可证

本项目采用 [MIT License](file:///C:/Users/84787/Desktop/GetGithub/LICENSE) 授权开源。
