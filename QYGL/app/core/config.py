"""F05: Config Loader — database is the source of truth, YAML for import templates only."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class AppConfig:
    """Application-wide configuration loaded from environment variables."""

    def __init__(self) -> None:
        self.db_path: str = os.environ.get("QFBJ_DB_PATH", "data/qfbj.db")
        self.host: str = os.environ.get("QFBJ_HOST", "0.0.0.0")
        self.port: int = int(os.environ.get("QFBJ_PORT", "8000"))
        self.debug: bool = os.environ.get("QFBJ_DEBUG", "false").lower() == "true"
        self.encrypt_key: str = os.environ.get(
            "QFBJ_ENCRYPT_KEY",
            "qfbj-default-encrypt-key-change-in-prod-32b",
        )
        self.log_level: str = os.environ.get("QFBJ_LOG_LEVEL", "INFO")

        self.feishu_webhook_path: str = "/webhook/feishu"
        self.backup_dir: str = os.environ.get("QFBJ_BACKUP_DIR", "data/backups")
        self.knowledge_dir: str = os.environ.get("QFBJ_KNOWLEDGE_DIR", "knowledge")
        self.max_agent_turns: int = int(os.environ.get("QFBJ_MAX_AGENT_TURNS", "15"))
        self.context_compress_threshold: float = float(
            os.environ.get("QFBJ_CONTEXT_COMPRESS_THRESHOLD", "0.8")
        )
        self.context_keep_recent_turns: int = int(
            os.environ.get("QFBJ_CONTEXT_KEEP_RECENT", "5")
        )

        # Feishu Open Platform (webhook verification + optional global bot credentials)
        self.feishu_app_id: str = os.environ.get("FEISHU_APP_ID", "")
        self.feishu_app_secret: str = os.environ.get("FEISHU_APP_SECRET", "")
        self.feishu_encrypt_key: str = os.environ.get("FEISHU_ENCRYPT_KEY", "")
        self.feishu_verification_token: str = os.environ.get("FEISHU_VERIFICATION_TOKEN", "")

    def setup_logging(self) -> None:
        logging.basicConfig(
            level=getattr(logging, self.log_level.upper(), logging.INFO),
            format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )


def load_yaml_template(path: str | Path) -> dict[str, Any]:
    """Load a YAML file as a template for importing into the database."""
    import yaml  # noqa: delayed import to avoid hard dependency

    p = Path(path)
    if not p.exists():
        logger.warning("Template file not found: %s", p)
        return {}
    with open(p, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


_config: AppConfig | None = None


def get_config() -> AppConfig:
    global _config
    if _config is None:
        _config = AppConfig()
    return _config
