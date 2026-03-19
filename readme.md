# ⭐ StarMind Manager

一款面向开发者的 **GitHub Star 资产智能管理工具**。用 AI 将你收藏的项目转化为结构化的中文知识库，支持离线搜索和智能分类。

## ✨ 核心功能

- **🔐 可视化配置** - GUI 界面轻松管理 GitHub Token 和 LLM API 密钥
- **📡 智能同步** - 支持增量更新，只处理新增项目，节省时间和成本
- **🤖 AI 分析** - 接入大模型自动生成中文摘要、技术标签和分类
- **🌐 离线知识库** - 导出为单页 HTML，支持全文搜索、标签过滤、暗黑模式
- **⚡ 高效并发** - 可调节线程数，快速处理数百个项目

## 🚀 快速开始

### 环境要求
- Python 3.10+
- pip

### 安装

```bash
# 克隆项目
git clone https://github.com/yourusername/GetGithub.git
cd GetGithub

# 安装依赖
pip install -r requirements.txt
```

### 运行

```bash
python main.py
```

## 📖 使用步骤

### 1️⃣ 配置阶段（⚙️ 配置 Tab）

**GitHub 配置：**
- 填写 Personal Access Token（[获取方法](https://github.com/settings/tokens/new?scopes=repo,read:user&description=StarMind+Manager)）
- 可选：指定目标用户名（留空则获取 Token 拥有者的 Star）
- 点击「🔍 检测 Rate Limit」验证 Token 有效性

**LLM 配置：**
- Base URL：支持所有 OpenAI 兼容接口（DeepSeek、Qwen、Kimi、Ollama 等）
- API Key：填写对应服务的密钥
- 模型名称：如 `gpt-3.5-turbo`、`deepseek-chat` 等
- 点击「🧪 测试连通性」验证配置

### 2️⃣ 同步阶段（🚀 任务 Tab）

- 调节「并发线程数」（建议 5-10，防止被限流）
- 点击「▶ 开始同步」启动任务
- 实时查看日志和进度条
- 支持中途「⏹ 停止」

### 3️⃣ 导出阶段（📤 导出 Tab）

- 点击「🔄 刷新统计」查看数据库项目数
- 点击「🌐 导出为 HTML 知识库」生成离线站点
- 自动打开浏览器预览，可双击 `index.html` 随时查看

## 🛠 技术栈

| 模块 | 技术 |
|------|------|
| **GUI** | CustomTkinter |
| **数据库** | SQLite3 |
| **网络** | requests + ThreadPoolExecutor |
| **模板** | Jinja2 |
| **前端** | HTML/JS + Vue 3 (CDN) + Tailwind CSS + Fuse.js |

## 📊 数据库结构

项目信息存储在 SQLite 中，包含：
- 项目名称、URL、Star 数量
- AI 生成的中文摘要
- 智能分类和技术标签
- 主要编程语言
- 处理时间戳

## 🔒 安全说明

- GitHub Token 和 LLM API Key 保存在本地 `config.json`
- **建议**：不要将 `config.json` 上传到公开仓库
- 可使用系统密钥链进一步加密敏感信息

## 📝 常见问题

**Q: 为什么同步很慢？**
A: 受 GitHub API 限流影响。建议：
- 使用高权限 Token（提高限额）
- 减少并发线程数
- 利用增量更新功能

**Q: LLM 分析失败怎么办？**
A: 系统会自动降级，使用 GitHub 原生的 Description 和 Topics 字段，确保数据不丢失。

**Q: 导出的 HTML 能在哪里打开？**
A: 纯静态文件，任何浏览器都支持。可本地打开、上传到 GitHub Pages、Vercel 等。

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

**Made with ❤️ for developers who love open source**
