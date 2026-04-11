from .a01_risk import A01RiskAgent
from .a02_business import A02BusinessAgent
from .a04_platform import A04PlatformAgent
from .a05_market import A05MarketAgent
from .a06_niche import A06NicheAgent
from .a07_design import A07DesignAgent
from .a08_attribution import A08AttributionAgent
from .a09_profit import A09ProfitAgent
from .a10_listing import A10ListingAgent
from .a11_optimize import A11OptimizeAgent
from .a12_content import A12ContentAgent
from .a13_task_dispatch import A13TaskDispatchAgent
from .a14_review import A14ReviewAgent
from .a15_performance import A15PerformanceAgent
from .a16_memory import A16MemoryAgent

AGENT_REGISTRY = {
    "a01_risk": A01RiskAgent,
    "a02_business": A02BusinessAgent,
    "a04_platform": A04PlatformAgent,
    "a05_market": A05MarketAgent,
    "a06_niche": A06NicheAgent,
    "a07_design": A07DesignAgent,
    "a08_attribution": A08AttributionAgent,
    "a09_profit": A09ProfitAgent,
    "a10_listing": A10ListingAgent,
    "a11_optimize": A11OptimizeAgent,
    "a12_content": A12ContentAgent,
    "a13_task_dispatch": A13TaskDispatchAgent,
    "a14_review": A14ReviewAgent,
    "a15_performance": A15PerformanceAgent,
    "a16_memory": A16MemoryAgent,
}
