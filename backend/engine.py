from __future__ import annotations

import math
import re
import time
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field

try:
    from .models import (
        AgentStep,
        Evaluation,
        GuardrailFinding,
        KnowledgeDocument,
        RunRequest,
        RunResponse,
        Source,
    )
    from .llm import LLMError, deepseek_enabled, deepseek_model, generate_with_deepseek
except ImportError:
    from models import (
        AgentStep,
        Evaluation,
        GuardrailFinding,
        KnowledgeDocument,
        RunRequest,
        RunResponse,
        Source,
    )
    from llm import LLMError, deepseek_enabled, deepseek_model, generate_with_deepseek


STOP_WORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "into",
    "用户",
    "系统",
    "需要",
    "进行",
    "通过",
    "一个",
    "可以",
}

RISK_TERMS = {
    "隐私": "涉及用户隐私，需要最小化采集并脱敏处理。",
    "手机号": "包含个人信息字段，应避免直接进入提示词。",
    "身份证": "高敏身份信息，建议阻断或脱敏后再处理。",
    "医疗": "医疗建议属于高风险场景，需要人工复核。",
    "金融": "金融决策场景需要合规边界和免责声明。",
    "密码": "禁止在模型上下文中传递明文凭证。",
}

PERSONA_LABELS = {
    "product_manager": "产品经理",
    "backend_engineer": "后端工程师",
    "ai_engineer": "AI 应用工程师",
    "ops_lead": "运维负责人",
}


@dataclass
class Chunk:
    id: str
    title: str
    content: str
    tags: list[str]
    tf: Counter[str] = field(default_factory=Counter)


class KnowledgeEngine:
    def __init__(self) -> None:
        self.documents: list[KnowledgeDocument] = []
        self.chunks: list[Chunk] = []
        self.idf: dict[str, float] = {}
        self.seed()

    def seed(self) -> None:
        samples = [
            KnowledgeDocument(
                title="RAG 应用交付规范",
                tags=["rag", "retrieval", "grounding"],
                content=(
                    "企业知识库问答应包含文档采集、文本清洗、语义分段、召回检索、提示词组装、引用溯源、"
                    "答案生成和质量评测。检索阶段需要展示来源文档、片段分数和证据内容，生成阶段应要求模型"
                    "只基于引用回答，无法回答时明确说明知识库依据不足。"
                ),
            ),
            KnowledgeDocument(
                title="Agent 工作流设计",
                tags=["agent", "workflow", "tool"],
                content=(
                    "多 Agent 应用适合拆分为 Planner、Retriever、Reasoner、Verifier 和 Reporter。Planner 负责拆解任务，"
                    "Retriever 获取证据，Reasoner 形成结论，Verifier 检查幻觉、敏感信息和业务风险，Reporter 输出结构化结果。"
                ),
            ),
            KnowledgeDocument(
                title="AI 应用安全与治理",
                tags=["guardrail", "security", "compliance"],
                content=(
                    "AI 应用需要输入检查、敏感信息识别、提示词注入防护、输出审计、人工复核和日志追踪。"
                    "涉及隐私、医疗、金融、法律等高风险场景时，应降低自动化等级并保留人工确认入口。"
                ),
            ),
            KnowledgeDocument(
                title="LLM 可观测性指标",
                tags=["observability", "evaluation", "metrics"],
                content=(
                    "上线后的 AI 应用需要跟踪延迟、命中率、召回覆盖度、答案相关性、引用充分性、风险告警、"
                    "用户反馈和成本。评测可以从 groundedness、relevance、coverage、risk 四个维度进行。"
                ),
            ),
            KnowledgeDocument(
                title="后端工程化实践",
                tags=["backend", "api", "deployment"],
                content=(
                    "AI 应用后端通常使用 REST API 或 SSE 暴露能力，包含请求校验、错误处理、日志记录、配置管理、"
                    "缓存、限流和部署脚本。FastAPI 适合快速构建类型清晰的 AI 应用服务。"
                ),
            ),
        ]
        for item in samples:
            self.add_document(item)

    def add_document(self, document: KnowledgeDocument) -> None:
        self.documents.append(document)
        self._rebuild()

    def status(self) -> dict[str, int]:
        terms = {term for chunk in self.chunks for term in chunk.tf}
        return {
            "documents": len(self.documents),
            "chunks": len(self.chunks),
            "terms": len(terms),
            "agents": 5,
        }

    def run(self, payload: RunRequest) -> RunResponse:
        started = time.perf_counter()
        sources = self.retrieve(payload.goal, payload.top_k)
        guardrails = self.scan_risk(payload.goal, sources)
        agents = self.build_agents(payload, sources, guardrails)
        action_plan = self.make_action_plan(payload, sources, guardrails)
        answer = self.compose_answer(payload, sources, guardrails, action_plan)
        provider = "local-rule"
        if deepseek_enabled():
            try:
                answer = generate_with_deepseek(
                    goal=payload.goal,
                    persona=PERSONA_LABELS.get(payload.persona, payload.persona),
                    sources=[source.model_dump() for source in sources],
                    guardrails=[finding.model_dump() for finding in guardrails],
                    action_plan=action_plan,
                    temperature=payload.temperature,
                )
                provider = f"deepseek:{deepseek_model()}"
            except LLMError as exc:
                guardrails.append(
                    GuardrailFinding(
                        level="warning",
                        title="AI 模型调用失败，已使用本地规则生成",
                        detail=str(exc)[:180],
                    )
                )
        evaluation = self.evaluate(payload, sources, guardrails)
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        metrics = {
            "latency_ms": latency_ms,
            "retrieved_chunks": len(sources),
            "estimated_tokens": len(payload.goal) + sum(len(source.snippet) for source in sources),
            "mode": payload.risk_mode,
            "provider": provider,
        }
        return RunResponse(
            answer=answer,
            action_plan=action_plan,
            sources=sources,
            agents=agents,
            guardrails=guardrails,
            evaluation=evaluation,
            metrics=metrics,
        )

    def retrieve(self, query: str, top_k: int) -> list[Source]:
        query_tf = Counter(tokenize(query))
        ranked: list[tuple[float, Chunk]] = []
        for chunk in self.chunks:
            score = cosine_score(query_tf, chunk.tf, self.idf)
            if score > 0:
                ranked.append((score, chunk))

        ranked.sort(key=lambda item: item[0], reverse=True)
        return [
            Source(
                title=chunk.title,
                chunk_id=chunk.id,
                score=round(score, 4),
                snippet=chunk.content,
                tags=chunk.tags,
            )
            for score, chunk in ranked[:top_k]
        ]

    def scan_risk(self, goal: str, sources: list[Source]) -> list[GuardrailFinding]:
        text = goal + " " + " ".join(source.snippet for source in sources)
        findings = []
        for term, detail in RISK_TERMS.items():
            if term in text:
                findings.append(
                    GuardrailFinding(level="warning", title=f"检测到「{term}」", detail=detail)
                )
        if "忽略" in goal and "规则" in goal:
            findings.append(
                GuardrailFinding(
                    level="critical",
                    title="疑似提示词注入",
                    detail="输入包含绕过规则的表达，应启用系统提示词隔离和工具调用白名单。",
                )
            )
        if not findings:
            findings.append(
                GuardrailFinding(
                    level="pass",
                    title="未发现明显高风险信号",
                    detail="仍建议保留日志审计、引用检查和人工确认机制。",
                )
            )
        return findings

    def build_agents(
        self,
        payload: RunRequest,
        sources: list[Source],
        guardrails: list[GuardrailFinding],
    ) -> list[AgentStep]:
        persona = PERSONA_LABELS.get(payload.persona, "业务用户")
        return [
            AgentStep(
                role="Planner",
                title="任务拆解",
                detail=f"面向{persona}将目标拆解为检索、分析、校验和交付四个阶段。",
                status="done",
            ),
            AgentStep(
                role="Retriever",
                title="证据召回",
                detail=f"从知识库召回 {len(sources)} 个相关片段，并保留来源、标签和相似度分数。",
                status="done",
            ),
            AgentStep(
                role="Reasoner",
                title="上下文推理",
                detail="基于召回证据组合答案，优先输出可落地的功能、架构和工程实践。",
                status="done",
            ),
            AgentStep(
                role="Verifier",
                title="风险校验",
                detail=f"完成 {len(guardrails)} 项护栏检查，覆盖隐私、注入、高风险行业和依据充分性。",
                status="done",
            ),
            AgentStep(
                role="Reporter",
                title="结构化交付",
                detail="输出回答、行动计划、引用、评测指标和运行日志，方便作品集展示。",
                status="done",
            ),
        ]

    def compose_answer(
        self,
        payload: RunRequest,
        sources: list[Source],
        guardrails: list[GuardrailFinding],
        action_plan: list[str],
    ) -> str:
        source_titles = "、".join(source.title for source in sources[:3]) or "当前输入"
        if sources:
            risk_note = "；已启用引用依据与风险提示" if payload.strict_grounding else "；允许结合通用工程经验扩展"
            evidence_note = f"本次主要依据来自：{source_titles}{risk_note}。"
        else:
            evidence_note = "当前知识库没有召回到足够资料，以下内容基于用户需求和通用 AI 应用开发经验生成。"
        first_step = action_plan[0] if action_plan else "先补充资料并明确目标。"
        return (
            f"建议将该需求设计为一个可观测的 AI 应用工作流：以「{payload.goal}」为目标，"
            f"先通过知识库召回证据，再由 Agent 编排完成任务拆解、上下文推理、风险校验和结构化输出。"
            f"{evidence_note}系统应重点展示引用来源、召回分数、"
            f"评测指标和护栏结果。建议第一步先做：{first_step}"
        )

    def make_action_plan(
        self,
        payload: RunRequest,
        sources: list[Source],
        guardrails: list[GuardrailFinding],
    ) -> list[str]:
        plan = [
            "接入知识数据：支持文档上传、清洗、分段、标签化和索引重建。",
            "构建 RAG 核心链路：实现 Top-K 召回、引用溯源、严格上下文回答和无依据兜底。",
            "编排 Agent 工作流：规划、检索、推理、校验、报告五类角色分工协作。",
            "加入评测与观测：输出 groundedness、relevance、coverage、risk、延迟和召回数量。",
            "完善安全治理：检测敏感信息、提示词注入和高风险场景，保留人工复核策略。",
        ]
        if any(finding.level == "critical" for finding in guardrails):
            plan.insert(0, "优先拦截高风险输入：隔离用户指令与系统规则，避免提示词注入影响工具链。")
        if len(sources) < max(2, payload.top_k // 2):
            plan.append("补充更多业务资料或 FAQ 样本，提高召回覆盖度和答案可信度。")
        return plan

    def evaluate(
        self,
        payload: RunRequest,
        sources: list[Source],
        guardrails: list[GuardrailFinding],
    ) -> Evaluation:
        best_score = sources[0].score if sources else 0
        groundedness = min(96, 55 + len(sources) * 7 + round(best_score * 35))
        relevance = min(98, 60 + round(best_score * 40))
        coverage = min(94, 50 + len({tag for source in sources for tag in source.tags}) * 8)
        risk_penalty = 25 if any(item.level == "critical" for item in guardrails) else 10
        risk = max(5, 35 - risk_penalty + (8 if payload.risk_mode == "strict" else 0))
        return Evaluation(
            groundedness=groundedness,
            relevance=relevance,
            coverage=coverage,
            risk=risk,
        )

    def _rebuild(self) -> None:
        self.chunks = []
        for document in self.documents:
            for index, content in enumerate(split_chunks(document.content)):
                self.chunks.append(
                    Chunk(
                        id=f"{uuid.uuid4().hex[:8]}-{index}",
                        title=document.title,
                        content=content,
                        tags=document.tags,
                        tf=Counter(tokenize(content + " " + " ".join(document.tags))),
                    )
                )

        doc_freq: dict[str, int] = defaultdict(int)
        for chunk in self.chunks:
            for term in chunk.tf:
                doc_freq[term] += 1

        total = max(1, len(self.chunks))
        self.idf = {
            term: math.log((total + 1) / (count + 1)) + 1
            for term, count in doc_freq.items()
        }


def split_chunks(text: str, chunk_size: int = 160) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if len(normalized) <= chunk_size:
        return [normalized]
    chunks = []
    start = 0
    while start < len(normalized):
        chunks.append(normalized[start : start + chunk_size])
        start += chunk_size - 30
    return chunks


def tokenize(text: str) -> list[str]:
    lowered = text.lower()
    english = re.findall(r"[a-z0-9+#.-]{2,}", lowered)
    chinese = re.findall(r"[\u4e00-\u9fa5]{2,}", lowered)
    pairs = [
        phrase[index : index + 2]
        for phrase in chinese
        for index in range(max(0, len(phrase) - 1))
    ]
    return [term for term in [*english, *chinese, *pairs] if term not in STOP_WORDS]


def cosine_score(query: Counter[str], document: Counter[str], idf: dict[str, float]) -> float:
    if not query or not document:
        return 0.0

    dot = 0.0
    q_norm = 0.0
    d_norm = 0.0
    for term, count in query.items():
        weight = count * idf.get(term, 0.7)
        q_norm += weight * weight
        if term in document:
            dot += weight * document[term] * idf.get(term, 0.7)

    for term, count in document.items():
        weight = count * idf.get(term, 0.7)
        d_norm += weight * weight

    if q_norm == 0 or d_norm == 0:
        return 0.0
    return dot / (math.sqrt(q_norm) * math.sqrt(d_norm))
