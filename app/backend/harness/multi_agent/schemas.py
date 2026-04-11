"""POD 多 Agent 系统的统一输入输出结构。"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Optional


class DataSufficiency(str, enum.Enum):
    SUFFICIENT = "sufficient"
    RESEARCH_ONLY = "research_only"
    INSUFFICIENT = "insufficient"


class Confidence(str, enum.Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RiskLevel(str, enum.Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


@dataclass
class DataPayload:
    impressions: Optional[int] = None
    clicks: Optional[int] = None
    ctr: Optional[float] = None
    visits: Optional[int] = None
    orders: Optional[int] = None
    gmv: Optional[float] = None
    conversion_rate: Optional[float] = None
    gross_margin: Optional[float] = None
    ad_spend: Optional[float] = None
    refund_rate: Optional[float] = None


@dataclass
class ConstraintsPayload:
    budget: Optional[float] = None
    timeline: Optional[str] = None
    platform_restrictions: Optional[list[str]] = field(default_factory=list)


@dataclass
class HistoryPayload:
    past_results: Optional[list[dict]] = field(default_factory=list)
    notes: Optional[str] = None


@dataclass
class MemoryWritebackItem:
    memory_type: str = ""
    title: str = ""
    platform: str = ""
    market: str = ""
    persona: str = ""
    niche: str = ""
    conditions: list[str] = field(default_factory=list)
    action: str = ""
    result: str = ""
    why: str = ""
    reusable: bool = True

    def model_dump(self) -> dict:
        return {
            "memory_type": self.memory_type,
            "title": self.title,
            "platform": self.platform,
            "market": self.market,
            "persona": self.persona,
            "niche": self.niche,
            "conditions": self.conditions,
            "action": self.action,
            "result": self.result,
            "why": self.why,
            "reusable": self.reusable,
        }


@dataclass
class AgentInput:
    task_id: str = ""
    task_type: str = ""
    source: str = "user"
    platform: str = ""
    market: str = ""
    store_id: str = ""
    product_type: str = "POD T-shirt"
    niche: str = ""
    design_concept: str = ""
    target_persona: str = ""
    language_style: str = ""
    business_line: str = ""
    data: Any = field(default_factory=dict)
    constraints: Any = field(default_factory=dict)
    history: Any = field(default_factory=dict)
    attachments: list[str] = field(default_factory=list)
    question: str = ""

    def _data_dict(self) -> dict:
        if isinstance(self.data, DataPayload):
            return {k: v for k, v in self.data.__dict__.items() if v is not None}
        if isinstance(self.data, dict):
            return self.data
        return {}

    def _constraints_dict(self) -> dict:
        if isinstance(self.constraints, ConstraintsPayload):
            return {k: v for k, v in self.constraints.__dict__.items() if v is not None}
        if isinstance(self.constraints, dict):
            return self.constraints
        return {}

    def to_prompt_context(self) -> str:
        parts: list[str] = []
        if self.platform:
            parts.append(f"平台: {self.platform}")
        if self.market:
            parts.append(f"市场: {self.market}")
        if self.business_line:
            parts.append(f"业务线: {self.business_line}")
        if self.niche:
            parts.append(f"Niche: {self.niche}")
        if self.target_persona:
            parts.append(f"目标人群: {self.target_persona}")
        if self.design_concept:
            parts.append(f"设计方向: {self.design_concept}")
        if self.language_style:
            parts.append(f"语言风格: {self.language_style}")
        if self.store_id:
            parts.append(f"店铺ID: {self.store_id}")
        dd = self._data_dict()
        if dd:
            data_lines = [f"  {k}: {v}" for k, v in dd.items() if v is not None]
            if data_lines:
                parts.append("数据:\n" + "\n".join(data_lines))
        cd = self._constraints_dict()
        if cd:
            constraint_lines = [f"  {k}: {v}" for k, v in cd.items() if v is not None]
            if constraint_lines:
                parts.append("约束:\n" + "\n".join(constraint_lines))
        if self.question:
            parts.append(f"问题: {self.question}")
        return "\n".join(parts)


@dataclass
class AgentOutput:
    agent_name: str = ""
    task_type: str = ""
    data_sufficiency: DataSufficiency = DataSufficiency.INSUFFICIENT
    missing_fields: list[str] = field(default_factory=list)
    judgment: str = ""
    confidence: Confidence = Confidence.LOW
    evidence: list[str] = field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW
    risk_notes: list[str] = field(default_factory=list)
    scores: dict[str, Any] = field(default_factory=dict)
    next_actions: list[str] = field(default_factory=list)
    need_escalation: bool = False
    escalate_to: str = ""
    memory_writeback: list[Any] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    raw_response: str = ""
    total_tokens: int = 0

    def to_dict(self) -> dict:
        return {
            "agent_name": self.agent_name,
            "task_type": self.task_type,
            "data_sufficiency": self.data_sufficiency.value if isinstance(self.data_sufficiency, DataSufficiency) else str(self.data_sufficiency),
            "missing_fields": self.missing_fields,
            "judgment": self.judgment,
            "confidence": self.confidence.value if isinstance(self.confidence, Confidence) else str(self.confidence),
            "evidence": self.evidence,
            "risk_level": self.risk_level.value if isinstance(self.risk_level, RiskLevel) else str(self.risk_level),
            "risk_notes": self.risk_notes,
            "scores": self.scores,
            "next_actions": self.next_actions,
            "need_escalation": self.need_escalation,
            "escalate_to": self.escalate_to,
            "memory_writeback": [
                mw.model_dump() if hasattr(mw, "model_dump") else mw
                for mw in self.memory_writeback
            ],
            "notes": self.notes,
            "raw_response": self.raw_response,
            "total_tokens": self.total_tokens,
        }
