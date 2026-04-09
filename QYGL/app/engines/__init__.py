"""Business engines — orchestrate domain logic without raw SQL.

All engines inherit from EngineBase and use its wrapped DB access methods.
"""

from app.engines.anomaly import detect_anomalies
from app.engines.base import EngineBase
from app.engines.calc import CalcEngine
from app.engines.cross_team import CrossTeamEngine
from app.engines.customer import CustomerEngine
from app.engines.decision import DecisionEngine
from app.engines.escalation import EscalationEngine, check_overdue_tasks
from app.engines.goal import GoalEngine
from app.engines.hiring import HiringEngine
from app.engines.kpi import KPIEngine, auto_score_system_kpis
from app.engines.task import TaskEngine

__all__ = [
    "EngineBase",
    "CalcEngine",
    "CrossTeamEngine",
    "CustomerEngine",
    "DecisionEngine",
    "EscalationEngine",
    "GoalEngine",
    "HiringEngine",
    "KPIEngine",
    "TaskEngine",
    "auto_score_system_kpis",
    "check_overdue_tasks",
    "detect_anomalies",
]
