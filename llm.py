"""
StarMind Manager - LLM 智能处理模块
调用 OpenAI 兼容接口，对 Readme / 项目描述 / 项目结构进行中文摘要与分析
支持多级内容来源的智能降级策略
"""

import json
import time
from openai import OpenAI


SYSTEM_PROMPT = """你是一个专业的 GitHub 项目分析助手。请根据用户提供的项目内容（Readme、描述或目录结构），进行深度总结。
请务必输出以下 JSON 格式的分析结果（不要输出任何多余的解释、寒暄或非 JSON 文本，只输出纯 JSON 包裹的数据）：
{
  "summary": "请用详细、通顺专业的【中文】总结该项目的核心功能、技术特点、主要用途以及适用场景（字数严格在300字到350字之间）。注意：无论原文是什么语言，这里必须输出对应的中文。",
  "language": "该项目的主要编程语言（保留英文原名，如 Python, Vue, Rust）",
  "tags": ["技术标签1", "技术标签2", "技术标签3"],
  "category": "项目所属类别，请务必从以下选项中严格选取最匹配的一个：AI与大模型, 后端开发, 前端开发, 移动端开发, 数据库与存储, 运维/DevOps, 测试与安全, 效率辅助工具, 桌面系统应用, 爬虫与数据提取, 影音媒体处理, 独立游戏与开发引擎, 区块链/Web3, 学习教程与资料, 其他"
}
注意：如果无法判断分类，请统一填写为 "其他"。任何情况下都必须返回上述合法的 JSON 格式。"""

MAX_README_CHARS = 1500
MAX_RETRIES = 5


def _parse_llm_json(content: str) -> dict | None:
    """从 LLM 返回内容中提取 JSON（兼容 markdown 代码块包裹）"""
    text = content.strip()

    # 使用正则表达式提取大括号内的内容
    import re
    match = re.search(r'(\{.*\})', text, re.DOTALL)
    if match:
        text = match.group(1)

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

def _smart_sleep(seconds: float, is_stopped=None):
    """可被随时中断的安全休眠"""
    if is_stopped is None:
        time.sleep(seconds)
        return
        
    steps = int(seconds * 5)
    for _ in range(max(1, steps)):
        if is_stopped():
            raise InterruptedError("Stopped by user")
        time.sleep(0.2)

def _call_llm(client: OpenAI, model: str, user_content: str, is_stopped=None) -> dict | None:
    """发送请求到 LLM 并解析 JSON 结果，带 429 感知的智能退避重试"""
    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.3,
                max_tokens=2000,
                timeout=60,
            )
            content = response.choices[0].message.content
            if content:
                result = _parse_llm_json(content)
                if result:
                    return result
        except Exception as e:
            err_str = str(e)
            safe_e = err_str.encode('ascii', errors='ignore').decode('ascii')
            print(f"LLM call or parse error on attempt {attempt+1}: {safe_e}")

            # 针对 429 频率限制错误，使用更长的等待时间（15~45秒）
            if '429' in err_str:
                wait_time = 15 * (attempt + 1)  # 15s, 30s, 45s, 60s, 75s
                print(f"  -> Rate limited (429). Waiting {wait_time}s before retry...")
                _smart_sleep(wait_time, is_stopped)
                continue

        if attempt < MAX_RETRIES - 1:
            _smart_sleep(2 ** attempt, is_stopped)
    return None

def summarize_repo(
    base_url: str,
    api_key: str,
    model: str,
    readme_text: str = "",
    description: str = "",
    repo_tree: str = "",
    repo_name: str = "",
    is_stopped = None
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
        result = _call_llm(client, model, f"请分析以下 GitHub 项目 [{repo_name}] 的 README 内容：\n\n{truncated}", is_stopped)
        if result:
            return result

    # ── 策略 2：使用 Description + Topics ──
    if description and description.strip():
        prompt = f"以下是 GitHub 项目 [{repo_name}] 的简介描述：\n\n{description}\n\n请根据这段简介分析该项目。"
        result = _call_llm(client, model, prompt, is_stopped)
        if result:
            return result

    # ── 策略 3：使用文件结构分析 ──
    if repo_tree and repo_tree.strip():
        prompt = (
            f"这是 GitHub 项目 [{repo_name}] 的顶层文件目录结构，请根据文件和目录名推断这个项目的功能、技术栈和用途：\n\n"
            f"{repo_tree}"
        )
        result = _call_llm(client, model, prompt, is_stopped)
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
        safe_err = str(e).encode('ascii', errors='ignore').decode('ascii')
        return False, f"连接失败：{safe_err}"
