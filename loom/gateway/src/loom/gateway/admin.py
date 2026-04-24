"""Admin REST API — /api/admin/*.

All state is stored as JSON files under ~/.loom/:
  models.json   — registered MLX model entries
  config.json   — default generation parameters
  users.json    — local user accounts (passwords hashed via hashlib sha-256)
  keys.json     — API key metadata (secrets stored as sha-256 hashes)
"""

from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# ── Storage helpers ────────────────────────────────────────────────────────────

_LOOM_DIR = Path.home() / ".loom"


def _read(name: str, default: Any) -> Any:
    path = _LOOM_DIR / name
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _write(name: str, data: Any) -> None:
    _LOOM_DIR.mkdir(parents=True, exist_ok=True)
    (_LOOM_DIR / name).write_text(json.dumps(data, indent=2))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Router ─────────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ── Models ─────────────────────────────────────────────────────────────────────


class ModelEntry(BaseModel):
    id: str
    path: str
    description: str = ""


@router.get("/models", response_model=list[ModelEntry])
async def list_models() -> list[dict]:
    return _read("models.json", [])


@router.post("/models", response_model=ModelEntry, status_code=201)
async def add_model(entry: ModelEntry) -> dict:
    models: list[dict] = _read("models.json", [])
    if any(m["id"] == entry.id for m in models):
        raise HTTPException(status_code=409, detail=f"Model '{entry.id}' already exists")
    record = entry.model_dump()
    models.append(record)
    _write("models.json", models)
    return record


@router.delete("/models/{model_id}", status_code=204)
async def remove_model(model_id: str) -> None:
    models: list[dict] = _read("models.json", [])
    remaining = [m for m in models if m["id"] != model_id]
    if len(remaining) == len(models):
        raise HTTPException(status_code=404, detail="Model not found")
    _write("models.json", remaining)


# ── AI Config ──────────────────────────────────────────────────────────────────


class AIConfig(BaseModel):
    temperature: float = 0.7
    max_tokens: int = 512
    top_p: float = 1.0
    system_prompt: str = ""


_DEFAULT_CONFIG = AIConfig().model_dump()


@router.get("/config", response_model=AIConfig)
async def get_config() -> dict:
    return {**_DEFAULT_CONFIG, **_read("config.json", {})}


@router.put("/config", response_model=AIConfig)
async def set_config(config: AIConfig) -> dict:
    data = config.model_dump()
    _write("config.json", data)
    return data


# ── Users ──────────────────────────────────────────────────────────────────────


class CreateUser(BaseModel):
    username: str
    password: str
    role: str = "user"


class UserOut(BaseModel):
    username: str
    role: str
    created_at: str


def _hash_pw(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


@router.get("/users", response_model=list[UserOut])
async def list_users() -> list[dict]:
    users: list[dict] = _read("users.json", [])
    return [{"username": u["username"], "role": u["role"], "created_at": u["created_at"]} for u in users]


@router.post("/users", response_model=UserOut, status_code=201)
async def create_user(body: CreateUser) -> dict:
    users: list[dict] = _read("users.json", [])
    if any(u["username"] == body.username for u in users):
        raise HTTPException(status_code=409, detail=f"User '{body.username}' already exists")
    if body.role not in ("admin", "user"):
        raise HTTPException(status_code=422, detail="role must be 'admin' or 'user'")
    record = {
        "username": body.username,
        "password_hash": _hash_pw(body.password),
        "role": body.role,
        "created_at": _now(),
    }
    users.append(record)
    _write("users.json", users)
    return {"username": record["username"], "role": record["role"], "created_at": record["created_at"]}


@router.delete("/users/{username}", status_code=204)
async def delete_user(username: str) -> None:
    users: list[dict] = _read("users.json", [])
    remaining = [u for u in users if u["username"] != username]
    if len(remaining) == len(users):
        raise HTTPException(status_code=404, detail="User not found")
    _write("users.json", remaining)


# ── Security / API keys ────────────────────────────────────────────────────────


class CreateKey(BaseModel):
    name: str


class ApiKeyOut(BaseModel):
    id: str
    name: str
    prefix: str
    created_at: str


class NewKeyResponse(BaseModel):
    key: ApiKeyOut
    secret: str


@router.get("/security/keys", response_model=list[ApiKeyOut])
async def list_keys() -> list[dict]:
    keys: list[dict] = _read("keys.json", [])
    return [{"id": k["id"], "name": k["name"], "prefix": k["prefix"], "created_at": k["created_at"]} for k in keys]


@router.post("/security/keys", response_model=NewKeyResponse, status_code=201)
async def create_key(body: CreateKey) -> dict:
    raw = f"lk-{secrets.token_urlsafe(32)}"
    prefix = raw[:10]
    record = {
        "id": str(uuid.uuid4()),
        "name": body.name,
        "prefix": prefix,
        "hash": hashlib.sha256(raw.encode()).hexdigest(),
        "created_at": _now(),
    }
    keys: list[dict] = _read("keys.json", [])
    keys.append(record)
    _write("keys.json", keys)
    out = {"id": record["id"], "name": record["name"], "prefix": record["prefix"], "created_at": record["created_at"]}
    return {"key": out, "secret": raw}


@router.delete("/security/keys/{key_id}", status_code=204)
async def delete_key(key_id: str) -> None:
    keys: list[dict] = _read("keys.json", [])
    remaining = [k for k in keys if k["id"] != key_id]
    if len(remaining) == len(keys):
        raise HTTPException(status_code=404, detail="Key not found")
    _write("keys.json", remaining)
