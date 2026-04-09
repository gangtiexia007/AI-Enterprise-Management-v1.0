"""F13 Knowledge Skill — BM25 + jieba search over the knowledge base.

Tools:
    knowledge__search — BM25-ranked Chinese text search
    knowledge__upload — add new knowledge entries
    knowledge__list   — browse by scope / category
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from typing import Any

from app.core.database import Database, new_id
from app.core.enums import KnowledgeScope, KnowledgeSource, KnowledgeStatus, PermissionLevel
from app.skills.sdk import ToolContext, tool

logger = logging.getLogger(__name__)

# ── Tokenizer ─────────────────────────────────────────────────────────

_jieba_loaded = False


def _tokenize(text: str) -> list[str]:
    """Tokenize Chinese + English text using jieba (with fallback)."""
    global _jieba_loaded
    try:
        import jieba
        if not _jieba_loaded:
            jieba.setLogLevel(logging.WARNING)
            _jieba_loaded = True
        tokens = list(jieba.cut_for_search(text))
    except ImportError:
        tokens = re.findall(r"[\u4e00-\u9fff]+|[a-zA-Z0-9]+", text)
    return [t.strip().lower() for t in tokens if t.strip() and len(t.strip()) > 1]


# ── BM25 Scorer ──────────────────────────────────────────────────────

_BM25_K1 = 1.5
_BM25_B = 0.75


def _bm25_score(
    query_tokens: list[str],
    doc_tokens: list[str],
    avg_dl: float,
    n_docs: int,
    df: dict[str, int],
) -> float:
    """Compute BM25 score for a single document."""
    dl = len(doc_tokens)
    tf_map = Counter(doc_tokens)
    score = 0.0
    for qt in query_tokens:
        doc_freq = df.get(qt, 0)
        if doc_freq == 0:
            continue
        idf = math.log((n_docs - doc_freq + 0.5) / (doc_freq + 0.5) + 1.0)
        tf = tf_map.get(qt, 0)
        numerator = tf * (_BM25_K1 + 1)
        denominator = tf + _BM25_K1 * (1 - _BM25_B + _BM25_B * dl / max(avg_dl, 1))
        score += idf * (numerator / denominator)
    return score


# ── Tools ─────────────────────────────────────────────────────────────


@tool(permission=PermissionLevel.P0, description="Search knowledge base with BM25 ranking")
def knowledge__search(
    ctx: ToolContext,
    *,
    query: str,
    scope: str = "",
    category: str = "",
    limit: int = 10,
) -> list[dict[str, Any]]:
    """BM25-ranked search over the ``knowledge`` table."""
    db = Database.get_instance()

    sql = "SELECT * FROM knowledge WHERE status = ?"
    params: list[Any] = [KnowledgeStatus.ACTIVE]

    if scope:
        sql += " AND scope = ?"
        params.append(scope)
    if category:
        sql += " AND category = ?"
        params.append(category)

    sql += " LIMIT 500"
    rows = db.execute(sql, tuple(params))

    if not rows:
        return []

    query_tokens = _tokenize(query)
    if not query_tokens:
        return rows[:limit]

    docs_tokens = [_tokenize(f"{r.get('title', '')} {r.get('content', '')}") for r in rows]

    total_len = sum(len(dt) for dt in docs_tokens)
    avg_dl = total_len / max(len(docs_tokens), 1)
    n_docs = len(docs_tokens)

    df: dict[str, int] = {}
    for dt in docs_tokens:
        for tok in set(dt):
            df[tok] = df.get(tok, 0) + 1

    scored = []
    for i, row in enumerate(rows):
        s = _bm25_score(query_tokens, docs_tokens[i], avg_dl, n_docs, df)
        if s > 0:
            scored.append((s, row))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored[:limit]]


@tool(permission=PermissionLevel.P2, description="Add a new knowledge entry")
def knowledge__upload(
    ctx: ToolContext,
    *,
    title: str,
    content: str,
    scope: str = KnowledgeScope.COMPANY,
    category: str = "",
    department: str = "",
    source: str = KnowledgeSource.MANUAL,
    status: str = KnowledgeStatus.ACTIVE,
) -> dict[str, Any]:
    """Insert a new row into the ``knowledge`` table."""
    db = Database.get_instance()
    kid = new_id()
    db.insert("knowledge", {
        "id": kid,
        "title": title,
        "content": content,
        "scope": scope,
        "department": department or ctx.department,
        "category": category,
        "source": source,
        "status": status,
        "created_by": ctx.actor or ctx.employee_id or "system",
    })
    row = db.get_by_id("knowledge", kid)
    return row or {"id": kid}


@tool(permission=PermissionLevel.P0, description="List knowledge entries by scope or category")
def knowledge__list(
    ctx: ToolContext,
    *,
    scope: str = "",
    category: str = "",
    status: str = KnowledgeStatus.ACTIVE,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Browse knowledge entries with optional filters."""
    db = Database.get_instance()
    conditions: dict[str, Any] = {}
    if scope:
        conditions["scope"] = scope
    if category:
        conditions["category"] = category
    if status:
        conditions["status"] = status
    return db.query(
        "knowledge", conditions or None,
        order_by="created_at DESC", limit=limit, offset=offset,
    )
