"""MultiAgentOrchestrator: A0 main agent / central orchestration.

Responsibilities:
1. Classify task type from user message
2. Build AgentInput
3. Run data gate (A3)
4. Execute route chain sequentially
5. Aggregate outputs, format final response
6. Log AgentRun to database
"""
import json
import logging
import time
import uuid
from datetime import datetime
from typing import Optional

from harness.multi_agent.schemas import (
    AgentInput, AgentOutput, DataSufficiency, DataPayload,
    ConstraintsPayload, HistoryPayload, RiskLevel,
)
from harness.multi_agent.data_gate import data_gate
from harness.multi_agent.routes import ROUTE_CHAINS, TASK_TYPE_KEYWORDS

logger = logging.getLogger(__name__)


class MultiAgentOrchestrator:
    """A0 - the single orchestrator that routes to specialist agents."""

    def __init__(self):
        self._agent_registry: dict = {}
        self._initialized = False

    def _ensure_init(self):
        if self._initialized:
            return
        try:
            from harness.multi_agent.agents import AGENT_REGISTRY
            self._agent_registry = AGENT_REGISTRY
            self._initialized = True
            logger.info(f"MultiAgentOrchestrator initialized with {len(self._agent_registry)} agents")
        except Exception as e:
            logger.error(f"Failed to load agent registry: {e}", exc_info=True)

    async def run(self, user_message: str, db_session, extra_data: Optional[dict] = None) -> str:
        self._ensure_init()
        run_id = str(uuid.uuid4())
        start_time = time.time()
        agents_called: list[str] = []
        agent_outputs: list[AgentOutput] = []

        try:
            task_type = await self._classify_task(user_message, db_session)
            input_data = self._build_input(user_message, task_type, extra_data)

            sufficiency, missing = data_gate.check(input_data)

            if sufficiency == DataSufficiency.INSUFFICIENT:
                result = self._format_insufficient_response(task_type, missing)
                self._log_run(db_session, run_id, task_type, task_type, [], input_data, result, 0, start_time, sufficiency.value)
                return result

            route = ROUTE_CHAINS.get(task_type)
            if not route:
                result = f"[POD Multi-Agent] 无法识别任务类型: {task_type}。支持的类型: {', '.join(ROUTE_CHAINS.keys())}"
                self._log_run(db_session, run_id, task_type, "", [], input_data, result, 0, start_time, sufficiency.value)
                return result

            context: dict = {
                "prior_outputs": [],
                "data_sufficiency": sufficiency.value,
                "missing_fields": missing,
                "run_id": run_id,
            }

            try:
                from harness.memory_manager import memory_manager
                l3_knowledge = memory_manager.get_l3_knowledge(limit=5)
                l4_patterns = memory_manager.get_l4_patterns(limit=3)
                context["memory"] = {"knowledge": l3_knowledge, "patterns": l4_patterns}
            except Exception as e:
                logger.warning(f"Failed to load memory: {e}")
                context["memory"] = {}

            try:
                from models import AuditLog
                from datetime import timedelta
                cutoff = datetime.utcnow() - timedelta(hours=24)
                alerts = db_session.query(AuditLog).filter(
                    AuditLog.action.like("rule_alert:%"),
                    AuditLog.created_at > cutoff,
                ).order_by(AuditLog.created_at.desc()).limit(10).all()
                if alerts:
                    context["active_alerts"] = [
                        {"action": a.action, "detail": a.detail, "time": a.created_at.isoformat() if a.created_at else ""}
                        for a in alerts
                    ]
            except Exception as e:
                logger.warning(f"Failed to load rule alerts: {e}")

            for agent_id in route:
                if agent_id == "a03_data_gate":
                    agents_called.append("a03_data_gate")
                    continue

                agent_cls = self._agent_registry.get(agent_id)
                if not agent_cls:
                    logger.warning(f"Agent '{agent_id}' not found in registry, skipping")
                    continue

                agent = agent_cls()
                if not agent.enabled:
                    logger.info(f"Agent '{agent_id}' is disabled, skipping")
                    continue

                if sufficiency == DataSufficiency.RESEARCH_ONLY:
                    input_data.task_type = task_type

                try:
                    output = await agent.run(input_data, context, db_session)
                    agent_outputs.append(output)
                    context["prior_outputs"].append(output)
                    agents_called.append(agent_id)

                    if len(context["prior_outputs"]) > 2:
                        context["prior_outputs_summary"] = self._compress_prior_outputs(context["prior_outputs"])

                    risk_val = output.risk_level.value if isinstance(output.risk_level, RiskLevel) else str(output.risk_level)
                    if risk_val == "high" and agent_id == "a01_risk":
                        logger.info(f"A01 flagged high risk, stopping chain for task {run_id}")
                        break

                except Exception as e:
                    logger.error(f"Agent {agent_id} failed: {e}", exc_info=True)
                    agent_outputs.append(AgentOutput(
                        agent_name=agent_id,
                        task_type=task_type,
                        judgment=f"Agent execution failed: {str(e)}",
                        notes=[f"error: {str(e)}"],
                    ))
                    agents_called.append(agent_id)

            result = self._format_final_response(task_type, agent_outputs, sufficiency)

            try:
                from harness.memory_manager import memory_manager
                for out in agent_outputs:
                    if out.memory_writeback:
                        for mw in out.memory_writeback:
                            mw_text = json.dumps(mw, ensure_ascii=False) if isinstance(mw, dict) else str(mw)
                            memory_manager.store_knowledge_from_conversation(input_data.question, mw_text)
            except Exception as e:
                logger.warning(f"Memory writeback failed: {e}")

            total_tokens = sum(getattr(out, 'total_tokens', 0) for out in agent_outputs)
            self._log_run(db_session, run_id, task_type, task_type, agents_called, input_data, result, total_tokens, start_time, sufficiency.value)
            return result

        except Exception as e:
            logger.error(f"Orchestrator error: {e}", exc_info=True)
            duration_ms = int((time.time() - start_time) * 1000)
            return f"Multi-Agent system error: {str(e)}"

    async def _classify_task(self, message: str, db_session) -> str:
        """Keyword-based classification with LLM fallback."""
        msg_lower = message.lower()

        best_type = ""
        best_score = 0
        for task_type, keywords in TASK_TYPE_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in msg_lower)
            if score > best_score:
                best_score = score
                best_type = task_type

        if best_score > 0:
            return best_type

        try:
            from harness.ai_client import ai_client
            classify_prompt = (
                "You are a task classifier for a POD (Print on Demand) e-commerce system.\n"
                "Classify the user message into exactly ONE of these task types:\n"
                "- new_direction: evaluating new product directions or niches\n"
                "- link_analysis: analyzing existing product listing performance\n"
                "- market_expansion: expanding to new markets or platforms\n"
                "- team_action: team work arrangement and task assignment\n"
                "- content_event: content marketing and event planning\n"
                "- review: retrospective review and knowledge capture\n\n"
                "Respond with ONLY the task type string, nothing else."
            )
            response = await ai_client.chat(
                messages=[
                    {"role": "system", "content": classify_prompt},
                    {"role": "user", "content": message},
                ],
                max_tokens=50,
                temperature=0.1,
            )
            classified = response.strip().lower().replace('"', "").replace("'", "")
            if classified in ROUTE_CHAINS:
                return classified
        except Exception as e:
            logger.warning(f"LLM classification fallback failed: {e}")

        return "new_direction"

    def _build_input(self, message: str, task_type: str, extra_data: Optional[dict] = None) -> AgentInput:
        input_data = AgentInput(
            task_id=str(uuid.uuid4()),
            task_type=task_type,
            source="user",
            question=message,
        )

        if extra_data:
            if "platform" in extra_data:
                input_data.platform = extra_data["platform"]
            if "market" in extra_data:
                input_data.market = extra_data["market"]
            if "store_id" in extra_data:
                input_data.store_id = extra_data["store_id"]
            if "niche" in extra_data:
                input_data.niche = extra_data["niche"]
            if "target_persona" in extra_data:
                input_data.target_persona = extra_data["target_persona"]
            if "design_concept" in extra_data:
                input_data.design_concept = extra_data["design_concept"]
            if "business_line" in extra_data:
                input_data.business_line = extra_data["business_line"]
            if "language_style" in extra_data:
                input_data.language_style = extra_data["language_style"]

            if "data" in extra_data and isinstance(extra_data["data"], dict):
                input_data.data = DataPayload(**extra_data["data"])
            if "constraints" in extra_data and isinstance(extra_data["constraints"], dict):
                input_data.constraints = ConstraintsPayload(**extra_data["constraints"])
            if "history" in extra_data and isinstance(extra_data["history"], dict):
                input_data.history = HistoryPayload(**extra_data["history"])
            if "attachments" in extra_data and isinstance(extra_data["attachments"], list):
                input_data.attachments = extra_data["attachments"]

        return input_data

    def _compress_prior_outputs(self, prior_outputs: list) -> str:
        parts = []
        for out in prior_outputs:
            if isinstance(out, AgentOutput):
                judgment = out.judgment[:200] if out.judgment else ""
                parts.append(f"[{out.agent_name}] {judgment}")
            elif isinstance(out, dict):
                parts.append(f"[{out.get('agent_name','')}] {out.get('judgment','')[:200]}")
        return "\n".join(parts)

    def _format_insufficient_response(self, task_type: str, missing: list[str]) -> str:
        field_labels = {
            "platform": "platform (Temu/TikTok Shop/Shopee)",
            "market": "market (PH/SEA/EU/US)",
            "target_persona": "target persona / audience",
            "niche": "niche / sub-category",
            "data.impressions": "impressions data",
            "data.clicks|data.ctr": "clicks or CTR data",
            "data.orders": "order count",
            "data.gmv": "GMV",
            "data.gross_margin": "gross margin",
            "data.ad_spend": "ad spend",
            "question": "question / description",
        }
        missing_labels = [field_labels.get(f, f) for f in missing]
        missing_str = "\n".join([f"  - {label}" for label in missing_labels])
        return (
            f"## Data Insufficient - Cannot Proceed\n\n"
            f"**Task Type**: {task_type}\n\n"
            f"**Status**: Data insufficiency gate (A3) has blocked this request.\n\n"
            f"**Missing Required Fields**:\n{missing_str}\n\n"
            f"Please provide the missing information and try again.\n"
            f"Without sufficient data, the system cannot provide reliable business judgments."
        )

    def _format_final_response(self, task_type: str, agent_outputs: list[AgentOutput], data_sufficiency: DataSufficiency) -> str:
        if not agent_outputs:
            return "No agent outputs were generated."

        sections: list[str] = []
        sections.append(f"## POD Multi-Agent Analysis Report")
        sections.append(f"**Task Type**: {task_type}")
        sections.append(f"**Data Sufficiency**: {data_sufficiency.value}")
        sections.append(f"**Agents Called**: {len(agent_outputs)}")

        if data_sufficiency == DataSufficiency.RESEARCH_ONLY:
            sections.append("\n> Note: Data is partially available. The following analysis is for research purposes only and should NOT be treated as a definitive business judgment.\n")

        escalations: list[str] = []
        all_risks: list[str] = []
        all_next_actions: list[str] = []
        memory_items: list[dict] = []

        for out in agent_outputs:
            sections.append(f"\n### {out.agent_name}")
            if out.judgment:
                sections.append(out.judgment)
            risk_val = out.risk_level.value if isinstance(out.risk_level, RiskLevel) else str(out.risk_level)
            if risk_val != "low":
                sections.append(f"**Risk**: {risk_val}")
                all_risks.extend(out.risk_notes)
            if out.scores:
                score_parts = [f"{k}: {v}" for k, v in out.scores.items()]
                sections.append(f"**Scores**: {', '.join(score_parts)}")
            if out.next_actions:
                all_next_actions.extend(out.next_actions)
            if out.need_escalation:
                escalations.append(f"{out.agent_name} -> {out.escalate_to}")
            for mw in out.memory_writeback:
                if hasattr(mw, "model_dump"):
                    memory_items.append(mw.model_dump())
                elif isinstance(mw, dict):
                    memory_items.append(mw)

        if all_risks:
            sections.append("\n### Risk Summary")
            for note in all_risks:
                sections.append(f"- {note}")

        if all_next_actions:
            sections.append("\n### Recommended Next Actions")
            for i, action in enumerate(all_next_actions, 1):
                sections.append(f"{i}. {action}")

        if escalations:
            sections.append("\n### Escalation Needed")
            for esc in escalations:
                sections.append(f"- {esc}")

        return "\n".join(sections)

    def _log_run(
        self, db_session, run_id: str, task_type: str, route_name: str,
        agents_called: list[str], input_data: AgentInput, result: str,
        total_tokens: int, start_time: float, data_sufficiency: str,
    ):
        try:
            from models import AgentRun
            duration_ms = int((time.time() - start_time) * 1000)
            record = AgentRun(
                run_id=run_id,
                task_type=task_type,
                route_name=route_name,
                agents_called=json.dumps(agents_called, ensure_ascii=False),
                input_summary=input_data.question[:500] if input_data.question else "",
                final_output=result[:2000],
                total_tokens=total_tokens,
                duration_ms=duration_ms,
                data_sufficiency=data_sufficiency,
            )
            db_session.add(record)
            db_session.commit()
        except Exception as e:
            logger.error(f"Failed to log agent run: {e}")
            try:
                db_session.rollback()
            except Exception:
                pass

    def get_agent_configs(self) -> list[dict]:
        self._ensure_init()
        configs = []
        for agent_id, agent_cls in self._agent_registry.items():
            agent = agent_cls()
            configs.append({
                "agent_id": agent.agent_id,
                "agent_name": agent.agent_name,
                "description": agent.description,
                "enabled": agent.enabled,
            })
        return configs


orchestrator = MultiAgentOrchestrator()
