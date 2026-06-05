from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_MODEL = "deepseek-v4-flash"


class LLMError(RuntimeError):
    pass


def deepseek_enabled() -> bool:
    return bool(os.getenv("DEEPSEEK_API_KEY"))


def deepseek_model() -> str:
    return os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL)


def generate_with_deepseek(
    *,
    goal: str,
    persona: str,
    sources: list[dict],
    guardrails: list[dict],
    action_plan: list[str],
    temperature: float,
    timeout: float = 45,
) -> str:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise LLMError("DEEPSEEK_API_KEY is not configured.")

    evidence = "\n\n".join(
        f"[{index}] {source['title']} score={source['score']}\n{source['snippet']}"
        for index, source in enumerate(sources, start=1)
    )
    risks = "\n".join(
        f"- {item['level']}: {item['title']}，{item['detail']}" for item in guardrails
    )
    steps = "\n".join(f"{index}. {item}" for index, item in enumerate(action_plan, start=1))

    messages = [
        {
            "role": "system",
            "content": (
                "你是一个面向普通用户的 AI 应用方案助手。"
                "请用中文回答，表达要清楚、具体、易懂。"
                "优先基于给定参考资料和用户需求生成方案。"
                "如果参考资料不足，可以结合通用 AI 应用开发经验回答，但要避免编造不存在的数据、链接、指标或案例。"
                "输出 3 段：第一段说明这个 AI 应用能解决什么问题；第二段说明核心功能；第三段说明落地注意事项。"
                "不要使用 Markdown 标题，不要输出过长清单。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"用户需求：{goal}\n"
                f"分析视角：{persona}\n\n"
                f"参考资料：\n{evidence or '暂无参考资料，请结合通用 AI 应用开发经验回答，并提醒用户后续可补充业务资料提高准确性。'}\n\n"
                f"已生成的落地步骤：\n{steps}\n\n"
                f"风险检查：\n{risks or '暂无明显风险'}"
            ),
        },
    ]

    payload = {
        "model": deepseek_model(),
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    request = urllib.request.Request(
        DEEPSEEK_API_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise LLMError(f"DeepSeek API HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise LLMError(f"DeepSeek API request failed: {exc.reason}") from exc

    data = json.loads(raw)
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError(f"Unexpected DeepSeek response: {raw[:300]}") from exc
