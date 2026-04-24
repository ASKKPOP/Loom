"""Connector API — /api/connectors/*.

Connector types:
  filesystem  — read local files (optionally scoped to a root path)
  sqlite      — query a local SQLite database file
  http        — proxy an HTTP request to a configured base URL

Stored in ~/.loom/connectors.json.
Each connector gets a unique id and a type-specific config blob.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# ── Storage ────────────────────────────────────────────────────────────────────

_LOOM_DIR = Path.home() / ".loom"
_FILE = "connectors.json"


def _read() -> list[dict]:
    path = _LOOM_DIR / _FILE
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except Exception:
        return []


def _write(data: list[dict]) -> None:
    _LOOM_DIR.mkdir(parents=True, exist_ok=True)
    (_LOOM_DIR / _FILE).write_text(json.dumps(data, indent=2))


# ── Models ─────────────────────────────────────────────────────────────────────

VALID_TYPES = {"filesystem", "sqlite", "http"}


class ConnectorCreate(BaseModel):
    name: str
    type: str
    description: str = ""
    config: dict[str, Any] = {}


class ConnectorOut(BaseModel):
    id: str
    name: str
    type: str
    description: str
    config: dict[str, Any]
    created_at: str


class QueryRequest(BaseModel):
    params: dict[str, Any] = {}


# ── Router ─────────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/api/connectors", tags=["connectors"])


@router.get("", response_model=list[ConnectorOut])
async def list_connectors() -> list[dict]:
    return _read()


@router.post("", response_model=ConnectorOut, status_code=201)
async def create_connector(body: ConnectorCreate) -> dict:
    if body.type not in VALID_TYPES:
        raise HTTPException(status_code=422, detail=f"type must be one of: {', '.join(VALID_TYPES)}")
    connectors = _read()
    record: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "name": body.name,
        "type": body.type,
        "description": body.description,
        "config": body.config,
        "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    }
    connectors.append(record)
    _write(connectors)
    return record


@router.delete("/{connector_id}", status_code=204)
async def delete_connector(connector_id: str) -> None:
    connectors = _read()
    remaining = [c for c in connectors if c["id"] != connector_id]
    if len(remaining) == len(connectors):
        raise HTTPException(status_code=404, detail="Connector not found")
    _write(remaining)


@router.post("/{connector_id}/query")
async def query_connector(connector_id: str, body: QueryRequest) -> dict:
    connectors = _read()
    connector = next((c for c in connectors if c["id"] == connector_id), None)
    if connector is None:
        raise HTTPException(status_code=404, detail="Connector not found")

    ctype = connector["type"]
    cfg = connector.get("config", {})
    params = body.params

    if ctype == "filesystem":
        return _query_filesystem(cfg, params)
    elif ctype == "sqlite":
        return _query_sqlite(cfg, params)
    elif ctype == "http":
        return await _query_http(cfg, params)
    else:
        raise HTTPException(status_code=500, detail=f"Unknown type: {ctype}")


# ── Filesystem ─────────────────────────────────────────────────────────────────


def _query_filesystem(cfg: dict, params: dict) -> dict:
    raw_path = params.get("path", "")
    if not raw_path:
        raise HTTPException(status_code=422, detail="params.path is required")

    root = cfg.get("root_path", "")
    if root:
        root_p = Path(root).expanduser().resolve()
        target = (root_p / raw_path).resolve()
        # Prevent path traversal outside root
        try:
            target.relative_to(root_p)
        except ValueError:
            raise HTTPException(status_code=403, detail="Path escapes configured root")
    else:
        target = Path(raw_path).expanduser().resolve()

    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Path not found: {target}")

    if target.is_dir():
        entries = []
        for p in sorted(target.iterdir()):
            entries.append({"name": p.name, "type": "dir" if p.is_dir() else "file", "size": p.stat().st_size if p.is_file() else None})
        return {"type": "directory", "path": str(target), "entries": entries}

    # File — read up to 128 KB
    MAX = 128 * 1024
    content = target.read_bytes()
    truncated = len(content) > MAX
    try:
        text = content[:MAX].decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=422, detail="File is binary — only text files are supported")

    return {"type": "file", "path": str(target), "content": text, "truncated": truncated, "size": len(content)}


# ── SQLite ─────────────────────────────────────────────────────────────────────


def _query_sqlite(cfg: dict, params: dict) -> dict:
    db_path = cfg.get("db_path", "")
    if not db_path:
        raise HTTPException(status_code=422, detail="Connector missing db_path config")

    query = params.get("query", "").strip()
    if not query:
        raise HTTPException(status_code=422, detail="params.query is required")

    # Allow only SELECT statements for safety
    if not query.upper().startswith("SELECT"):
        raise HTTPException(status_code=422, detail="Only SELECT queries are allowed")

    db = Path(db_path).expanduser().resolve()
    if not db.exists():
        raise HTTPException(status_code=404, detail=f"Database not found: {db}")

    try:
        con = sqlite3.connect(str(db), check_same_thread=False)
        con.row_factory = sqlite3.Row
        cur = con.execute(query)
        rows = cur.fetchmany(500)  # cap at 500 rows
        columns = [d[0] for d in cur.description] if cur.description else []
        data = [dict(r) for r in rows]
        con.close()
        return {"columns": columns, "rows": data, "count": len(data)}
    except sqlite3.Error as e:
        raise HTTPException(status_code=400, detail=f"SQLite error: {e}")


# ── HTTP ───────────────────────────────────────────────────────────────────────


async def _query_http(cfg: dict, params: dict) -> dict:
    base_url = cfg.get("base_url", "").rstrip("/")
    if not base_url:
        raise HTTPException(status_code=422, detail="Connector missing base_url config")

    endpoint = params.get("endpoint", "")
    method = params.get("method", "GET").upper()
    body = params.get("body", None)
    extra_headers = params.get("headers", {})

    url = f"{base_url}/{endpoint.lstrip('/')}" if endpoint else base_url

    # Merge connector-level headers with per-request headers
    headers = {**cfg.get("headers", {}), **extra_headers}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.request(method, url, headers=headers, json=body if body else None)
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                try:
                    return {"status": response.status_code, "body": response.json(), "content_type": content_type}
                except Exception:
                    pass
            return {"status": response.status_code, "body": response.text[:10_000], "content_type": content_type}
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Request failed: {e}")
