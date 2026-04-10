from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base
from routers import tasks, goals, kpi, knowledge, settings, agent, employees, reports, approvals, audit_logs, coaching
from routers import agent_admin, scheduled_tasks, teams, bitable, feishu_webhook


def _safe_migrate(engine):
    """Add any missing columns to existing tables without touching data."""
    import sqlalchemy as sa
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    with engine.connect() as conn:
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            existing = {c["name"] for c in inspector.get_columns(table.name)}
            for col in table.columns:
                if col.name not in existing:
                    col_type = col.type.compile(engine.dialect)
                    default = ""
                    if col.default is not None and col.default.is_scalar:
                        v = col.default.arg
                        default = f" DEFAULT '{v}'" if isinstance(v, str) else f" DEFAULT {v}"
                    elif not col.nullable:
                        default = " DEFAULT ''"
                    try:
                        conn.execute(text(
                            f"ALTER TABLE {table.name} ADD COLUMN {col.name} {col_type}{default}"
                        ))
                        conn.commit()
                    except Exception as e:
                        pass  # Column may already exist in a race condition


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _safe_migrate(engine)

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
app.include_router(scheduled_tasks.router, prefix="/api/scheduled-tasks", tags=["scheduled-tasks"])
app.include_router(teams.router, prefix="/api/teams", tags=["teams"])
app.include_router(bitable.router, prefix="/api/bitable", tags=["bitable"])
app.include_router(feishu_webhook.router, prefix="/api/feishu", tags=["feishu-webhook"])


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "6.0"}
