"""Application entry point — FastAPI app with all routes and lifecycle."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.config import get_config
from app.core.database import Database

logger = logging.getLogger(__name__)

APP_VERSION = "12.0.0"


@asynccontextmanager
async def lifespan(application: FastAPI):
    cfg = get_config()
    cfg.setup_logging()
    logger.info("Starting 千方百计AI ...")

    db = Database.get_instance(cfg.db_path)
    db.run_migrations()
    table_count = len(db.execute("SELECT name FROM sqlite_master WHERE type='table'"))
    logger.info("Database ready, %d tables", table_count)

    from app.dashboard.auth import ensure_admin_user
    try:
        ensure_admin_user()
    except Exception as e:
        logger.warning("ensure_admin_user failed: %s", e)

    try:
        from app.runtime.agent_loop import AgentLoop
        from app.channels.router import set_inbound_handler

        async def handle_inbound(msg):
            loop = AgentLoop(db=db)
            team_row = db.get_by_id("teams", msg.team_id)
            if not team_row:
                logger.warning("AgentLoop: team not found: %s", msg.team_id)
                return None
            team = dict(team_row)
            employee = None
            if msg.employee_id:
                emp_row = db.get_by_id("employees", msg.employee_id)
                if emp_row:
                    employee = dict(emp_row)
            conversation_id = ""
            if isinstance(msg.raw, dict):
                conversation_id = (msg.raw.get("conversation_id") or "").strip()
            resp = await loop.run(
                msg,
                team=team,
                employee=employee,
                conversation_id=conversation_id,
            )
            text = (resp.content or "").strip()
            return text or None

        set_inbound_handler(handle_inbound)
        logger.info("Agent Runtime wired to inbound message router")
    except Exception as e:
        logger.warning("Agent Runtime wiring failed: %s", e)

    try:
        from app.infra.eventbus import EventBus

        bus = EventBus.get_instance()
        bus.start()
        logger.info("EventBus initialized and dispatch loop started")
    except Exception as e:
        logger.warning("EventBus init failed: %s", e)

    try:
        from app.infra.hooks import HookEngine
        hook_engine = HookEngine.get_instance()
        hook_engine.register_with_eventbus()
        logger.info("HookEngine registered with EventBus")
    except Exception as e:
        logger.warning("HookEngine registration failed: %s", e)

    try:
        from app.channels.notification import NotificationService

        ns = NotificationService.get_instance()
        ns.start()
        logger.info("NotificationService started")
    except Exception as e:
        logger.warning("NotificationService failed: %s", e)

    try:
        from app.skills.registry import SkillRegistry
        registry = SkillRegistry.get_instance()
        registry.register_builtin_skills()
        logger.info("Skill registry initialized with builtin skills")
    except Exception as e:
        logger.warning("Skill registry init failed: %s", e)

    try:
        from app.channels.wecom import WeComManager
        wecom_mgr = WeComManager.get_instance()
        team_bots = db.query("team_bots", {"channel": "wecom", "enabled": 1})
        for bot in team_bots:
            ws_url = bot.get("webhook_url", "")
            extra = bot.get("extra_json", {})
            if isinstance(extra, str):
                import json as _json
                try:
                    extra = _json.loads(extra)
                except (ValueError, TypeError):
                    extra = {}
            token = extra.get("token", "")
            if ws_url:
                await wecom_mgr.start_for_team(bot["team_id"], ws_url, token)
        if team_bots:
            logger.info("WeCom WebSocket started for %d team(s)", len(team_bots))
    except Exception as e:
        logger.warning("WeCom startup failed: %s", e)

    try:
        from app.dream.scheduler import setup_dream_scheduler, start_scheduler

        setup_dream_scheduler()
        start_scheduler()
        logger.info("Dream scheduler started with jobs")
    except Exception as e:
        logger.warning("Dream scheduler failed: %s", e)

    logger.info("千方百计AI started on %s:%d", cfg.host, cfg.port)
    yield

    db.close()
    logger.info("千方百计AI shutdown complete")


def create_app() -> FastAPI:
    application = FastAPI(
        title="千方百计AI",
        description="Enterprise AI Governance System",
        version=APP_VERSION,
        lifespan=lifespan,
    )

    @application.get("/health")
    async def health_check():
        try:
            db = Database.get_instance()
            db.execute("SELECT 1")
            return JSONResponse({"status": "ok", "version": APP_VERSION})
        except Exception as e:
            return JSONResponse({"status": "error", "detail": str(e)}, status_code=503)

    from app.dashboard.auth import auth_middleware
    application.middleware("http")(auth_middleware)

    from app.dashboard.auth import router as auth_router
    from app.dashboard.wizard import router as wizard_router
    from app.dashboard.ws import router as ws_router
    from app.dashboard.api.overview import router as overview_router
    from app.dashboard.api.teams import router as teams_router
    from app.dashboard.api.commands import router as commands_router
    from app.dashboard.api.approval import router as approval_router
    from app.dashboard.api.tasks import router as tasks_router
    from app.dashboard.api.kpi import router as kpi_router
    from app.dashboard.api.escalation import router as escalation_router
    from app.dashboard.api.employees import router as employees_router
    from app.dashboard.api.dispute import router as dispute_router
    from app.dashboard.api.knowledge import router as knowledge_router
    from app.dashboard.api.memory import router as memory_router
    from app.dashboard.api.models import router as models_router
    from app.dashboard.api.salary import router as salary_router
    from app.dashboard.api.customers import router as customers_router
    from app.dashboard.api.my import router as my_router
    from app.dashboard.api.chat import router as chat_api_router
    from app.dashboard.api.hiring import router as hiring_router
    from app.dashboard.api.decisions import router as decisions_router
    from app.dashboard.api.webhook import router as webhook_data_router
    from app.dashboard.api.upload import router as upload_router

    application.include_router(auth_router)
    application.include_router(ws_router)
    application.include_router(wizard_router, prefix="/wizard")
    application.include_router(overview_router)
    application.include_router(teams_router)
    application.include_router(commands_router)
    application.include_router(approval_router)
    application.include_router(tasks_router)
    application.include_router(kpi_router)
    application.include_router(escalation_router)
    application.include_router(employees_router, prefix="/employees", tags=["employees"])
    application.include_router(dispute_router)
    application.include_router(knowledge_router)
    application.include_router(memory_router)
    application.include_router(models_router)
    application.include_router(salary_router)
    application.include_router(customers_router)
    application.include_router(hiring_router)
    application.include_router(decisions_router)
    application.include_router(webhook_data_router)
    application.include_router(upload_router)
    application.include_router(my_router, prefix="/my", tags=["my"])
    application.include_router(chat_api_router, prefix="/api")

    upload_dir = Path("data/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    from fastapi.staticfiles import StaticFiles

    application.mount("/uploads", StaticFiles(directory=str(upload_dir)), name="uploads")

    from app.channels.feishu import handle_feishu_event

    @application.post("/webhook/feishu")
    async def feishu_webhook(request: Request):
        return await handle_feishu_event(request)

    logger.info("All routes registered at app creation time")
    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn
    cfg = get_config()
    uvicorn.run("app.main:app", host=cfg.host, port=cfg.port, reload=cfg.debug)
