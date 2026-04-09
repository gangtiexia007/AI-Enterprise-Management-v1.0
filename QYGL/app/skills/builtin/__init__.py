"""Builtin skills — imported to register @tool functions into the global registry.

Importing this package triggers registration of all builtin tools.
"""

from app.skills.builtin import (  # noqa: F401
    calc_engine,
    file_parser,
    knowledge,
    notification,
    sqlite_data,
    feishu_im,
    wecom_im,
    feishu_bitable,
)

__all__ = [
    "sqlite_data",
    "knowledge",
    "file_parser",
    "calc_engine",
    "notification",
    "feishu_im",
    "wecom_im",
    "feishu_bitable",
]
