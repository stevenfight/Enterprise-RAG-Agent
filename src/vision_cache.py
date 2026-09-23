# -*- coding: utf-8 -*-
"""视觉模型成功响应缓存与只追加调用账本。"""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass
from typing import Any, Mapping

from .v7_metadata_store import V7MetadataStore
from .vision_provider import BaseVisionProvider, VisionRequest, VisionResponse, VisionUsage


@dataclass(frozen=True)
class VisionCallLedgerRecord:
    """视觉 Provider 调用或缓存命中的最小审计记录。"""

    ledger_id: int
    cache_key: str
    event_type: str
    status: str
    manifest_id: str
    artifact_id: str
    content_sha256: str
    capability: str
    provider_name: str
    model: str
    input_tokens: int
    output_tokens: int


class VisionCallCache:
    """按内容与版本隔离视觉成功响应，并记录实际调用和命中。"""

    _LOCK = threading.RLock()

    def __init__(self, metadata_store: V7MetadataStore, *, code_version: str = "vision-cache-v1") -> None:
        if not isinstance(metadata_store, V7MetadataStore):
            raise TypeError("视觉缓存必须使用 V7MetadataStore")
        if not isinstance(code_version, str) or not code_version.strip():
            raise ValueError("视觉缓存代码版本不能为空")
        self.metadata_store = metadata_store
        self.code_version = code_version.strip()
        self.metadata_store.initialize()

    def analyze(self, provider: BaseVisionProvider, request: VisionRequest) -> VisionResponse:
        """命中成功缓存时不调用 Provider；失败响应只记账，不写成功缓存。"""
        if not isinstance(provider, BaseVisionProvider):
            raise TypeError("视觉缓存需要 BaseVisionProvider")
        if not isinstance(request, VisionRequest):
            raise TypeError("视觉缓存需要 VisionRequest")
        material = self._cache_material(provider, request)
        cache_key = self._cache_key(material)
        with self._LOCK:
            cached = self._read_cached_response(cache_key)
            if cached is not None:
                self._append_ledger(material, cache_key, "cache_hit", cached, {"cache_stored": True})
                return cached

            response = provider.analyze(request)
            response_json = self._serialize_response(response) if response.success else None
            self._write_call_result(material, cache_key, response, response_json)
            return response

    def cache_entry_count(self) -> int:
        """返回当前成功视觉响应缓存条数。"""
        with self.metadata_store.connect() as connection:
            row = connection.execute("SELECT COUNT(*) FROM v7_vision_call_cache").fetchone()
        return int(row[0])

    def list_ledger(self, cache_key: str | None = None) -> tuple[VisionCallLedgerRecord, ...]:
        """按追加顺序读取视觉调用账本，可按缓存键筛选。"""
        query = (
            "SELECT ledger_id, cache_key, event_type, status, manifest_id, artifact_id, "
            "content_sha256, capability, provider_name, model, input_tokens, output_tokens "
            "FROM v7_vision_call_ledger"
        )
        parameters: tuple[Any, ...] = ()
        if cache_key is not None:
            query += " WHERE cache_key=?"
            parameters = (cache_key,)
        query += " ORDER BY ledger_id"
        with self.metadata_store.connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return tuple(VisionCallLedgerRecord(*row) for row in rows)

    def _read_cached_response(self, cache_key: str) -> VisionResponse | None:
        with self.metadata_store.connect() as connection:
            row = connection.execute(
                "SELECT response_json FROM v7_vision_call_cache WHERE cache_key=?",
                (cache_key,),
            ).fetchone()
        if row is None:
            return None
        return self._deserialize_response(row[0])

    def _write_call_result(
        self,
        material: dict[str, str],
        cache_key: str,
        response: VisionResponse,
        response_json: str | None,
    ) -> None:
        with self.metadata_store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                cache_stored = response_json is not None
                if response_json is not None:
                    connection.execute(
                        """
                        INSERT OR IGNORE INTO v7_vision_call_cache(
                            cache_key, manifest_id, artifact_id, content_sha256,
                            capability, provider_name, model, prompt_sha256,
                            prompt_version, code_version, artifact_version, response_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            cache_key,
                            material["manifest_id"],
                            material["artifact_id"],
                            material["content_sha256"],
                            material["capability"],
                            material["provider_name"],
                            material["model"],
                            material["prompt_sha256"],
                            material["prompt_version"],
                            material["code_version"],
                            material["artifact_version"],
                            response_json,
                        ),
                    )
                self._insert_ledger(
                    connection,
                    material,
                    cache_key,
                    "provider_call",
                    response,
                    {"cache_stored": cache_stored},
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def _append_ledger(
        self,
        material: dict[str, str],
        cache_key: str,
        event_type: str,
        response: VisionResponse,
        details: Mapping[str, Any],
    ) -> None:
        with self.metadata_store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                self._insert_ledger(connection, material, cache_key, event_type, response, details)
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    @staticmethod
    def _insert_ledger(
        connection: Any,
        material: dict[str, str],
        cache_key: str,
        event_type: str,
        response: VisionResponse,
        details: Mapping[str, Any],
    ) -> None:
        connection.execute(
            """
            INSERT INTO v7_vision_call_ledger(
                cache_key, event_type, status, manifest_id, artifact_id,
                content_sha256, capability, provider_name, model,
                input_tokens, output_tokens, details_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cache_key,
                event_type,
                response.status,
                material["manifest_id"],
                material["artifact_id"],
                material["content_sha256"],
                material["capability"],
                material["provider_name"],
                material["model"],
                response.usage.input_tokens,
                response.usage.output_tokens,
                json.dumps(dict(details), ensure_ascii=False, sort_keys=True),
            ),
        )

    def _cache_material(self, provider: BaseVisionProvider, request: VisionRequest) -> dict[str, str]:
        context = request.cache_context
        if not isinstance(context, Mapping):
            raise ValueError("视觉缓存上下文必须是映射")
        manifest_id = self._required_context(context, "manifest_id")
        artifact_id = self._required_context(context, "artifact_id")
        artifact_version = self._optional_context(context, "artifact_version", "unknown")
        prompt_version = self._optional_context(context, "prompt_version", "unknown")
        provider_name = self._optional_context(
            context,
            "provider_name",
            f"{provider.__class__.__module__}.{provider.__class__.__name__}",
        )
        model = request.model or provider.config.model
        if not isinstance(model, str) or not model.strip():
            raise ValueError("视觉缓存需要明确模型")
        return {
            "manifest_id": manifest_id,
            "artifact_id": artifact_id,
            "content_sha256": self._sha256(request.image_bytes),
            "capability": request.capability,
            "provider_name": provider_name,
            "model": model.strip(),
            "prompt_sha256": self._sha256(request.prompt.encode("utf-8")),
            "prompt_version": prompt_version,
            "code_version": self.code_version,
            "artifact_version": artifact_version,
        }

    @staticmethod
    def _cache_key(material: Mapping[str, str]) -> str:
        encoded = json.dumps(dict(material), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    @staticmethod
    def _serialize_response(response: VisionResponse) -> str | None:
        try:
            return json.dumps(
                {
                    "success": response.success,
                    "status": response.status,
                    "payload": dict(response.payload),
                    "error": response.error,
                    "model": response.model,
                    "usage": {
                        "input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens,
                    },
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _deserialize_response(value: str) -> VisionResponse:
        payload = json.loads(value)
        usage = payload["usage"]
        return VisionResponse(
            success=bool(payload["success"]),
            status=str(payload["status"]),
            payload=dict(payload["payload"]),
            error=str(payload.get("error", "")),
            model=str(payload.get("model", "")),
            usage=VisionUsage(
                input_tokens=int(usage["input_tokens"]),
                output_tokens=int(usage["output_tokens"]),
            ),
        )

    @staticmethod
    def _required_context(context: Mapping[str, Any], key: str) -> str:
        value = context.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"视觉缓存上下文缺少 {key}")
        return value.strip()

    @staticmethod
    def _optional_context(context: Mapping[str, Any], key: str, default: str) -> str:
        value = context.get(key, default)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"视觉缓存上下文 {key} 必须是非空字符串")
        return value.strip()

    @staticmethod
    def _sha256(value: bytes) -> str:
        return hashlib.sha256(value).hexdigest()
