from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base
from routers import tasks, goals, kpi, knowledge, settings, agent, employees, reports, approvals, audit_logs, coaching
from routers import agent_admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)

    from harness.skill_registry import skill_registry
    skill_registry.auto_discover_builtins()

    from harness.scheduler import start_scheduler
    start_scheduler()
    yield


app = FastAPI(title="千方百计AI - 老板管理助理", version="6.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(goals.router, prefix="/api/goals", tags=["goals"])
app.include_router(kpi.router, prefix="/api/kpi", tags=["kpi"])
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["knowledge"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(agent.router, prefix="/api/agent", tags=["agent"])
app.include_router(agent_admin.router, prefix="/api/agent", tags=["agent-admin"])
app.include_router(employees.router, prefix="/api/employees", tags=["employees"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
app.include_router(approvals.router, prefix="/api/approvals", tags=["approvals"])
app.include_router(audit_logs.router, prefix="/api/audit-logs", tags=["audit-logs"])
app.include_router(coaching.router, prefix="/api/coaching", tags=["coaching"])


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "6.0"}
