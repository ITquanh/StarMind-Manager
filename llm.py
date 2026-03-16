"""
StarMind Manager - LLM 智能处理模块
调用 OpenAI 兼容接口，对 Readme / 项目描述 / 项目结构进行中文摘要与分析
支持多级内容来源的智能降级策略
"""

import json
import time
from openai import OpenAI


SYSTEM_PROMPT = """你是一个 GitHub 项目分析助手。根据用户提供的项目信息，输出以下 JSON 格式的分析结果（不要输出任何多余文本，只输出纯 JSON）：
{
  "summary": "一句话中文精准摘要（不超过80字）",
  "language": "该项目的主要编程语言",
  "tags": ["技术标签1", "技术标签2", "技术标签3"],
  "category": "项目所属类别，从以下选项中选取最匹配的一个：AI/ML, Web框架, 移动开发, DevOps/运维, 数据库, 安全工具, 命令行工具, 编程语言/编译器, 前端UI, 后端框架, 文档/知识库, 测试工具, 网络/通信, 多媒体, 游戏开发, 系统工具, 区块链, 数据分析, 自动化, 其他"
}"""

MAX_README_CHARS = 1500
MAX_RETRIES = 3


def _parse_llm_json(content: str) -> dict | None:
    """从 LLM 返回内容中提取 JSON（兼容 markdown 代码块包裹）"""
    text = content.strip()

    # 移除 ```json ... ``` 包裹
    if text.startswith("```"):
        lines = text.split("\n")
        json_lines = []
        in_block = False
        for line in lines:
            if line.strip().startswith("```"):
                in_block = not in_block
                continue
            json_lines.append(line)
        text = "\n".join(json_lines).strip()

    try:
        result = json.loads(text)
        if "summary" in result and "category" in result:
            # 确保 tags 是列表
            if isinstance(result.get("tags"), str):
                result["tags"] = [result["tags"]]
            elif not isinstance(result.get("tags"), list):
                result["tags"] = []
            return result
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def _call_llm(client: OpenAI, model: str, user_content: str) -> dict | None:
    """发送请求到 LLM 并解析 JSON 结果，带指数退避重试"""
    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.3,
                max_tokens=500,
                timeout=30,
            )
            content = response.choices[0].message.content
            if content:
                result = _parse_llm_json(content)
                if result:
                    return result
        except Exception:
            pass
        if attempt < MAX_RETRIES - 1:
            time.sleep(2 ** attempt)
    return None


def summarize_repo(
    base_url: str,
    api_key: str,
    model: str,
    readme_text: str = "",
    description: str = "",
    repo_tree: str = "",
    repo_name: str = "",
) -> dict | None:
    """
    多级内容降级分析策略：
    1. 优先使用 Readme 文本内容
    2. 其次使用项目 Description（简介）
    3. 最后使用项目文件结构树 → 让 AI 根据结构推断项目用途
    
    成功返回 dict: {summary, language, tags, category}
    失败返回 None（调用者需做最终降级处理）
    """
    client = OpenAI(base_url=base_url, api_key=api_key)

    # ── 策略 1：Readme 最为信息丰富 ──
    if readme_text and readme_text.strip():
        truncated = readme_text[:MAX_README_CHARS]
        result = _call_llm(client, model, f"请分析以下 GitHub 项目 [{repo_name}] 的 README 内容：\n\n{truncated}")
        if result:
            return result

    # ── 策略 2：使用 Description + Topics ──
    if description and description.strip():
        prompt = f"以下是 GitHub 项目 [{repo_name}] 的简介描述：\n\n{description}\n\n请根据这段简介分析该项目。"
        result = _call_llm(client, model, prompt)
        if result:
            return result

    # ── 策略 3：使用文件结构分析 ──
    if repo_tree and repo_tree.strip():
        prompt = (
            f"这是 GitHub 项目 [{repo_name}] 的顶层文件目录结构，请根据文件和目录名推断这个项目的功能、技术栈和用途：\n\n"
            f"{repo_tree}"
        )
        result = _call_llm(client, model, prompt)
        if result:
            return result

    return None


def test_connection(base_url: str, api_key: str, model: str) -> tuple[bool, str]:
    """
    测试 LLM API 连通性。
    返回 (成功与否, 消息)
    """
    try:
        client = OpenAI(base_url=base_url, api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Hi, respond with OK."}],
            max_tokens=10,
            timeout=15,
        )
        
        # 安全获取 content，防止某些模型返回 None
        content = response.choices[0].message.content
        if content is None:
            reply = "无返回文本(响应被拒绝或为空)"
        else:
            reply = content.strip()
            
        return True, f"连接成功！模型回复：{reply}"
    except Exception as e:
        return False, f"连接失败：{str(e)}"
