# -*- coding: utf-8 -*-
"""E-T20 最小用户、角色和服务端会话身份。"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from src.v7_metadata_store import V7MetadataStore


@dataclass(frozen=True)
class ResearchIdentity:
    user_id: str
    username: str
    roles: tuple[str, ...]


def _password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310000)
    return f"{salt.hex()}${digest.hex()}"


def _matches(password: str, stored: str) -> bool:
    salt_hex, digest = stored.split("$", 1)
    return hmac.compare_digest(_password_hash(password, bytes.fromhex(salt_hex)), stored)


class ResearchIdentityStore:
    def __init__(self, store: V7MetadataStore) -> None:
        self._store = store
        store.initialize()

    def ensure_bootstrap_admin(self) -> None:
        username = os.getenv("RESEARCH_BOOTSTRAP_USERNAME", "").strip()
        password = os.getenv("RESEARCH_BOOTSTRAP_PASSWORD", "")
        if not username or not password:
            return
        with self._store.connect() as connection:
            if connection.execute("SELECT 1 FROM v7_research_users LIMIT 1").fetchone():
                return
            user_id = f"user:{username}"
            connection.execute("INSERT INTO v7_research_users(user_id, username, password_hash, enabled) VALUES (?, ?, ?, 1)", (user_id, username, _password_hash(password)))
            for role in ("admin", "approver", "researcher", "viewer"):
                connection.execute("INSERT OR IGNORE INTO v7_research_roles(role_id) VALUES (?)", (role,))
                connection.execute("INSERT INTO v7_research_user_roles(user_id, role_id) VALUES (?, ?)", (user_id, role))
            connection.commit()

    def login(self, username: str, password: str) -> tuple[str, ResearchIdentity] | None:
        self.ensure_bootstrap_admin()
        with self._store.connect() as connection:
            row = connection.execute("SELECT user_id, username, password_hash FROM v7_research_users WHERE username=? AND enabled=1", (username,)).fetchone()
            if row is None or not _matches(password, row[2]):
                return None
            roles = tuple(item[0] for item in connection.execute("SELECT role_id FROM v7_research_user_roles WHERE user_id=? ORDER BY role_id", (row[0],)).fetchall())
            token = secrets.token_urlsafe(32)
            connection.execute("INSERT INTO v7_research_sessions(token_hash, user_id, expires_at) VALUES (?, ?, ?)", (hashlib.sha256(token.encode()).hexdigest(), row[0], (datetime.now(timezone.utc)+timedelta(hours=8)).isoformat()))
            connection.commit()
        return token, ResearchIdentity(row[0], row[1], roles)

    def identity(self, token: str | None) -> ResearchIdentity | None:
        if not token:
            return None
        with self._store.connect() as connection:
            row = connection.execute("SELECT u.user_id, u.username FROM v7_research_sessions s JOIN v7_research_users u ON u.user_id=s.user_id WHERE s.token_hash=? AND s.expires_at>? AND u.enabled=1", (hashlib.sha256(token.encode()).hexdigest(), datetime.now(timezone.utc).isoformat())).fetchone()
            if row is None:
                return None
            roles = tuple(item[0] for item in connection.execute("SELECT role_id FROM v7_research_user_roles WHERE user_id=? ORDER BY role_id", (row[0],)).fetchall())
        return ResearchIdentity(row[0], row[1], roles)

    def logout(self, token: str | None) -> None:
        if token:
            with self._store.connect() as connection:
                connection.execute("DELETE FROM v7_research_sessions WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),)); connection.commit()
