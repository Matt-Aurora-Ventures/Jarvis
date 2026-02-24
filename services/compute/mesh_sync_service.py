"""
Mesh sync service for encrypted NATS propagation of state deltas.

This module wires transport + envelope validation around Nosana mesh helpers,
with safe degraded behavior when optional dependencies are unavailable.
"""

from __future__ import annotations

import inspect
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Mapping, Optional, Protocol

from .nosana_client import DEFAULT_SYNC_TTL_SECONDS, NosanaClient, get_nosana_client

logger = logging.getLogger(__name__)

DEFAULT_NATS_URL = "nats://127.0.0.1:4222"
DEFAULT_MESH_SUBJECT = "jarvis.mesh.sync"
DEFAULT_MESH_STREAM = "JARVIS_MESH"
DEFAULT_MESH_DURABLE = "jarvis-mesh-sync"
DEFAULT_MESH_OUTBOX_PATH = "data/mesh/outbox.jsonl"


def _env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class MeshTransport(Protocol):
    async def publish(self, subject: str, payload: str) -> None:
        ...

    async def subscribe(
        self,
        subject: str,
        callback: Callable[[str], Awaitable[None]],
    ) -> Any:
        ...

    async def close(self) -> None:
        ...


class NatsJetStreamMeshTransport:
    """
    Optional transport backed by nats-py.

    Uses JetStream when possible and gracefully falls back to core NATS.
    """

    def __init__(
        self,
        *,
        nats_url: Optional[str] = None,
        stream_name: str = DEFAULT_MESH_STREAM,
        durable_name: str = DEFAULT_MESH_DURABLE,
        use_jetstream: Optional[bool] = None,
    ):
        self.nats_url = str(
            nats_url
            or os.environ.get("JARVIS_NATS_URL")
            or os.environ.get("NATS_URL")
            or DEFAULT_NATS_URL
        ).strip()
        self.stream_name = stream_name
        self.durable_name = durable_name
        self.use_jetstream = _env_flag("JARVIS_MESH_USE_JETSTREAM", True) if use_jetstream is None else use_jetstream
        self._nc: Any = None
        self._js: Any = None
        self._subscription: Any = None

    async def _connect(self) -> None:
        if self._nc is not None:
            return

        try:
            import nats  # type: ignore
        except Exception as exc:
            raise RuntimeError("nats-py is not installed") from exc

        self._nc = await nats.connect(
            servers=[self.nats_url],
            connect_timeout=5,
            max_reconnect_attempts=-1,
            reconnect_time_wait=2,
        )

        if self.use_jetstream:
            try:
                from nats.js.api import StreamConfig  # type: ignore

                self._js = self._nc.jetstream()
                await self._js.add_stream(
                    config=StreamConfig(
                        name=self.stream_name,
                        subjects=[f"{DEFAULT_MESH_SUBJECT}.>", DEFAULT_MESH_SUBJECT],
                    )
                )
            except Exception as exc:
                logger.debug("JetStream setup skipped/fell back to core NATS: %s", exc)
                self._js = None

    async def publish(self, subject: str, payload: str) -> None:
        await self._connect()
        encoded = payload.encode("utf-8")
        if self._js is not None:
            await self._js.publish(subject, encoded)
            return
        await self._nc.publish(subject, encoded)

    async def subscribe(
        self,
        subject: str,
        callback: Callable[[str], Awaitable[None]],
    ) -> Any:
        await self._connect()

        async def _on_msg(msg: Any) -> None:
            payload = bytes(msg.data).decode("utf-8")
            await callback(payload)
            if hasattr(msg, "ack"):
                try:
                    await msg.ack()
                except Exception:
                    pass

        if self._js is not None:
            self._subscription = await self._js.subscribe(
                subject,
                durable=self.durable_name,
                stream=self.stream_name,
                cb=_on_msg,
                manual_ack=True,
            )
            return self._subscription

        self._subscription = await self._nc.subscribe(subject, cb=_on_msg)
        return self._subscription

    async def close(self) -> None:
        try:
            if self._subscription is not None and hasattr(self._subscription, "unsubscribe"):
                maybe = self._subscription.unsubscribe()
                if inspect.isawaitable(maybe):
                    await maybe
        except Exception:
            pass

        if self._nc is not None:
            try:
                await self._nc.drain()
            except Exception:
                try:
                    await self._nc.close()
                except Exception:
                    pass
        self._nc = None
        self._js = None
        self._subscription = None


class MeshSyncService:
    def __init__(
        self,
        *,
        nosana_client: Optional[NosanaClient] = None,
        transport: Optional[MeshTransport] = None,
        shared_key_hex: Optional[str] = None,
        node_pubkey: Optional[str] = None,
        subject: Optional[str] = None,
        enabled: Optional[bool] = None,
        outbox_path: Optional[Path | str] = None,
    ):
        self.nosana_client = nosana_client or get_nosana_client()
        self.transport: Optional[MeshTransport] = transport
        self.shared_key_hex = str(
            shared_key_hex
            or os.environ.get("JARVIS_MESH_SHARED_KEY", "")
            or os.environ.get("JARVIS_MESH_SYNC_KEY", "")
        ).strip()
        self.node_pubkey = str(node_pubkey or os.environ.get("JARVIS_MESH_NODE_PUBKEY", "")).strip()
        self.subject = str(
            subject
            or os.environ.get("JARVIS_MESH_SYNC_SUBJECT")
            or os.environ.get("NATS_SUBJECT_MESH_SYNC")
            or DEFAULT_MESH_SUBJECT
        ).strip()
        self.enabled = (
            _env_flag("JARVIS_USE_MESH_SYNC", _env_flag("JARVIS_MESH_SYNC_ENABLED", False))
            if enabled is None
            else enabled
        )
        outbox_value = outbox_path or os.environ.get("JARVIS_MESH_OUTBOX_PATH") or DEFAULT_MESH_OUTBOX_PATH
        self.outbox_path = Path(str(outbox_value))
        self._listening = False
        self._on_state_delta: Optional[Callable[[Dict[str, Any], Dict[str, Any]], Any]] = None
        self._on_attestation: Optional[Callable[[str, Dict[str, Any], Dict[str, Any]], Any]] = None
        self._last_state_hash: Optional[str] = None
        self._last_error: Optional[str] = None
        self._last_validation: Optional[Dict[str, Any]] = None
        self._metrics: Dict[str, int] = {
            "published_messages": 0,
            "received_messages": 0,
            "validated_messages": 0,
            "invalid_messages": 0,
            "ignored_self_messages": 0,
            "outbox_records": 0,
            "retry_attempts": 0,
        }

    def _is_configured(self) -> bool:
        return bool(self.shared_key_hex and self.node_pubkey)

    async def _ensure_transport(self) -> bool:
        if self.transport is not None:
            return True
        try:
            self.transport = NatsJetStreamMeshTransport()
            return True
        except Exception as exc:
            self._last_error = str(exc)
            return False

    def _append_outbox(self, record: Mapping[str, Any]) -> None:
        try:
            self.outbox_path.parent.mkdir(parents=True, exist_ok=True)
            with self.outbox_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(dict(record), separators=(",", ":"), sort_keys=True))
                handle.write("\n")
            self._metrics["outbox_records"] += 1
        except Exception as exc:
            logger.warning("Failed to append mesh outbox record: %s", exc)

    def record_outbox_event(
        self,
        *,
        event_id: str,
        status: str,
        state_hash: Optional[str] = None,
        state_delta: Optional[Mapping[str, Any]] = None,
        envelope: Optional[Mapping[str, Any]] = None,
        reason: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> None:
        payload: Dict[str, Any] = {
            "timestamp": _utc_now_iso(),
            "event_id": str(event_id),
            "status": str(status),
            "state_hash": str(state_hash or ""),
        }
        if state_delta is not None:
            payload["state_delta"] = dict(state_delta)
        if envelope is not None:
            payload["envelope"] = dict(envelope)
        if reason:
            payload["reason"] = str(reason)
        if metadata:
            payload["metadata"] = dict(metadata)
        self._append_outbox(payload)

    def _read_outbox_entries(self) -> list[Dict[str, Any]]:
        if not self.outbox_path.exists():
            return []
        entries: list[Dict[str, Any]] = []
        for raw in self.outbox_path.read_text(encoding="utf-8").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except Exception:
                continue
            if isinstance(payload, dict):
                entries.append(payload)
        return entries

    def validate_envelope(self, envelope: Mapping[str, Any]) -> tuple[bool, str]:
        if not self._is_configured():
            self._last_error = "mesh_sync_config_missing"
            return False, "mesh_sync_config_missing"
        try:
            validation = self.nosana_client.validate_mesh_sync_envelope(
                envelope,
                shared_key_hex=self.shared_key_hex,
            )
        except Exception as exc:
            self._last_error = str(exc)
            self._last_validation = {"valid": False, "reason": str(exc)}
            return False, str(exc)

        self._last_validation = dict(validation)
        valid = bool(validation.get("valid"))
        reason = str(validation.get("reason", "invalid"))
        if not valid:
            self._last_error = reason
        return valid, reason

    async def publish_state_delta(
        self,
        state_delta: Mapping[str, Any],
        *,
        prev_state_hash: Optional[str] = None,
        ttl_seconds: int = DEFAULT_SYNC_TTL_SECONDS,
    ) -> Dict[str, Any]:
        state_delta_payload = dict(state_delta)
        event_id = str(state_delta_payload.get("event_id") or uuid.uuid4().hex)
        state_delta_payload.setdefault("event_id", event_id)

        if not self.enabled:
            return {
                "published": False,
                "status": "disabled",
                "reason": "mesh_sync_disabled",
                "event_id": event_id,
            }
        if not self._is_configured():
            return {
                "published": False,
                "status": "unconfigured",
                "reason": "mesh_sync_config_missing",
                "event_id": event_id,
            }
        if not await self._ensure_transport():
            self.record_outbox_event(
                event_id=event_id,
                status="pending_publish",
                state_delta=state_delta_payload,
                reason="transport_unavailable",
            )
            return {
                "published": False,
                "status": "degraded",
                "reason": "transport_unavailable",
                "event_id": event_id,
            }

        envelope = self.nosana_client.build_mesh_sync_envelope(
            state_delta=state_delta_payload,
            node_pubkey=self.node_pubkey,
            shared_key_hex=self.shared_key_hex,
            prev_state_hash=prev_state_hash or self._last_state_hash,
            ttl_seconds=ttl_seconds,
            message_id=event_id,
        )
        subject = str(envelope.get("channel") or self.subject)
        payload = json.dumps(envelope, separators=(",", ":"), sort_keys=True)
        try:
            await self.transport.publish(subject, payload)
        except Exception as exc:
            self._last_error = str(exc)
            self.record_outbox_event(
                event_id=event_id,
                status="pending_publish",
                state_hash=str(envelope.get("state_hash", "")),
                state_delta=state_delta_payload,
                envelope=envelope,
                reason=str(exc),
            )
            return {
                "published": False,
                "status": "pending_publish",
                "reason": str(exc),
                "subject": subject,
                "event_id": event_id,
                "state_hash": envelope.get("state_hash"),
                "envelope": envelope,
                "state_delta": state_delta_payload,
            }

        self._metrics["published_messages"] += 1
        self._last_state_hash = str(envelope.get("state_hash") or "")

        return {
            "published": True,
            "status": "published",
            "subject": subject,
            "message_id": envelope.get("message_id"),
            "event_id": event_id,
            "state_hash": envelope.get("state_hash"),
            "envelope": envelope,
            "state_delta": state_delta_payload,
        }

    async def start_listener(
        self,
        *,
        on_state_delta: Optional[Callable[[Dict[str, Any], Dict[str, Any]], Any]] = None,
        on_attestation: Optional[Callable[[str, Dict[str, Any], Dict[str, Any]], Any]] = None,
    ) -> Dict[str, Any]:
        if not self.enabled:
            return {"status": "disabled", "reason": "mesh_sync_disabled"}
        if not self._is_configured():
            return {"status": "unconfigured", "reason": "mesh_sync_config_missing"}
        if not await self._ensure_transport():
            return {"status": "degraded", "reason": "transport_unavailable"}
        if self._listening:
            return {"status": "listening", "reason": "already_started"}

        self._on_state_delta = on_state_delta
        self._on_attestation = on_attestation

        async def _handler(payload: str) -> None:
            await self._handle_payload(payload)

        await self.transport.subscribe(self.subject, _handler)
        self._listening = True
        return {"status": "listening", "subject": self.subject}

    async def _handle_payload(self, payload: str) -> None:
        self._metrics["received_messages"] += 1
        try:
            envelope = json.loads(payload)
        except Exception:
            self._metrics["invalid_messages"] += 1
            self._last_error = "invalid_json"
            return

        if not isinstance(envelope, dict):
            self._metrics["invalid_messages"] += 1
            self._last_error = "invalid_payload_type"
            return

        if str(envelope.get("node_pubkey", "")).strip() == self.node_pubkey:
            self._metrics["ignored_self_messages"] += 1
            return

        try:
            validation = self.nosana_client.verify_and_unpack_sync_envelope(
                envelope,
                shared_key_hex=self.shared_key_hex,
            )
        except Exception as exc:
            self._metrics["invalid_messages"] += 1
            self._last_error = str(exc)
            return

        self._metrics["validated_messages"] += 1
        self._last_validation = dict(validation)
        state_delta = validation.get("state_delta")
        if isinstance(state_delta, dict):
            self._last_state_hash = str(validation.get("state_hash") or self._last_state_hash or "")
            if self._on_state_delta is not None:
                maybe = self._on_state_delta(state_delta, {"envelope": envelope, "validation": validation})
                if inspect.isawaitable(maybe):
                    await maybe

            if self._on_attestation is not None and validation.get("state_hash"):
                maybe_attest = self._on_attestation(str(validation["state_hash"]), envelope, validation)
                if inspect.isawaitable(maybe_attest):
                    await maybe_attest

    async def retry_pending_mesh_events(self, limit: int = 100) -> Dict[str, Any]:
        entries = self._read_outbox_entries()
        latest_by_event: Dict[str, Dict[str, Any]] = {}
        for entry in entries:
            event_id = str(entry.get("event_id", "")).strip()
            if not event_id:
                continue
            latest_by_event[event_id] = entry

        pending_publish = [
            e for e in latest_by_event.values() if str(e.get("status")) == "pending_publish"
        ]
        pending_commit = [
            e for e in latest_by_event.values() if str(e.get("status")) == "pending_commit"
        ]
        ordered = pending_publish + pending_commit
        selected = ordered[: max(0, int(limit))]

        summary: Dict[str, Any] = {
            "retried": 0,
            "published": 0,
            "committed": 0,
            "still_pending": 0,
            "errors": [],
            "published_event_ids": [],
        }
        if not selected:
            return summary

        attestation_service = None
        try:
            from .mesh_attestation_service import get_mesh_attestation_service

            attestation_service = get_mesh_attestation_service()
        except Exception:
            attestation_service = None

        for entry in selected:
            self._metrics["retry_attempts"] += 1
            summary["retried"] += 1
            event_id = str(entry.get("event_id", "")).strip() or uuid.uuid4().hex
            status = str(entry.get("status", ""))

            if status == "pending_publish":
                envelope = entry.get("envelope")
                if not isinstance(envelope, dict):
                    self.record_outbox_event(
                        event_id=event_id,
                        status="invalid_envelope",
                        state_hash=str(entry.get("state_hash", "")),
                        state_delta=entry.get("state_delta") if isinstance(entry.get("state_delta"), dict) else None,
                        reason="missing_envelope",
                    )
                    summary["errors"].append({"event_id": event_id, "reason": "missing_envelope"})
                    continue

                if not await self._ensure_transport():
                    self.record_outbox_event(
                        event_id=event_id,
                        status="pending_publish",
                        state_hash=str(entry.get("state_hash", "")),
                        state_delta=entry.get("state_delta") if isinstance(entry.get("state_delta"), dict) else None,
                        envelope=envelope,
                        reason="transport_unavailable",
                    )
                    summary["still_pending"] += 1
                    summary["errors"].append({"event_id": event_id, "reason": "transport_unavailable"})
                    continue

                try:
                    subject = str(envelope.get("channel") or self.subject)
                    await self.transport.publish(
                        subject,
                        json.dumps(envelope, separators=(",", ":"), sort_keys=True),
                    )
                    summary["published"] += 1
                    summary["published_event_ids"].append((subject, event_id))
                except Exception as exc:
                    self.record_outbox_event(
                        event_id=event_id,
                        status="pending_publish",
                        state_hash=str(entry.get("state_hash", "")),
                        state_delta=entry.get("state_delta") if isinstance(entry.get("state_delta"), dict) else None,
                        envelope=envelope,
                        reason=str(exc),
                    )
                    summary["still_pending"] += 1
                    summary["errors"].append({"event_id": event_id, "reason": str(exc)})
                    continue

                valid, reason = self.validate_envelope(envelope)
                if not valid:
                    self.record_outbox_event(
                        event_id=event_id,
                        status="invalid_envelope",
                        state_hash=str(entry.get("state_hash", "")),
                        state_delta=entry.get("state_delta") if isinstance(entry.get("state_delta"), dict) else None,
                        envelope=envelope,
                        reason=reason,
                    )
                    summary["errors"].append({"event_id": event_id, "reason": reason})
                    continue

                state_hash = str(envelope.get("state_hash", "")).strip() or str(entry.get("state_hash", "")).strip()
                if attestation_service is None or not bool(getattr(attestation_service, "enabled", False)):
                    self.record_outbox_event(
                        event_id=event_id,
                        status="published",
                        state_hash=state_hash,
                        state_delta=entry.get("state_delta") if isinstance(entry.get("state_delta"), dict) else None,
                        envelope=envelope,
                        reason="attestation_disabled",
                    )
                    continue

                commit_result = await attestation_service.commit_state_hash(
                    state_hash,
                    event_id=event_id,
                    node_pubkey=self.node_pubkey,
                    metadata={"source": "retry_pending_publish"},
                )
                if str(commit_result.get("status")) == "committed":
                    self.record_outbox_event(
                        event_id=event_id,
                        status="committed",
                        state_hash=state_hash,
                        state_delta=entry.get("state_delta") if isinstance(entry.get("state_delta"), dict) else None,
                        envelope=envelope,
                    )
                    summary["committed"] += 1
                else:
                    self.record_outbox_event(
                        event_id=event_id,
                        status="pending_commit",
                        state_hash=state_hash,
                        state_delta=entry.get("state_delta") if isinstance(entry.get("state_delta"), dict) else None,
                        envelope=envelope,
                        reason=str(commit_result.get("error") or commit_result.get("reason") or "commit_failed"),
                    )
                    summary["still_pending"] += 1
                continue

            if status == "pending_commit":
                state_hash = str(entry.get("state_hash", "")).strip()
                if not state_hash:
                    summary["errors"].append({"event_id": event_id, "reason": "missing_state_hash"})
                    continue
                if attestation_service is None or not bool(getattr(attestation_service, "enabled", False)):
                    summary["still_pending"] += 1
                    self.record_outbox_event(
                        event_id=event_id,
                        status="pending_commit",
                        state_hash=state_hash,
                        state_delta=entry.get("state_delta") if isinstance(entry.get("state_delta"), dict) else None,
                        reason="attestation_disabled",
                    )
                    continue

                commit_result = await attestation_service.commit_state_hash(
                    state_hash,
                    event_id=event_id,
                    node_pubkey=self.node_pubkey,
                    metadata={"source": "retry_pending_commit"},
                )
                if str(commit_result.get("status")) == "committed":
                    summary["committed"] += 1
                    self.record_outbox_event(
                        event_id=event_id,
                        status="committed",
                        state_hash=state_hash,
                        state_delta=entry.get("state_delta") if isinstance(entry.get("state_delta"), dict) else None,
                    )
                else:
                    summary["still_pending"] += 1
                    reason = str(commit_result.get("error") or commit_result.get("reason") or "commit_failed")
                    self.record_outbox_event(
                        event_id=event_id,
                        status="pending_commit",
                        state_hash=state_hash,
                        state_delta=entry.get("state_delta") if isinstance(entry.get("state_delta"), dict) else None,
                        reason=reason,
                    )
                    summary["errors"].append({"event_id": event_id, "reason": reason})

        return summary

    async def stop(self) -> None:
        self._listening = False
        if self.transport is not None:
            await self.transport.close()

    def get_status(self) -> Dict[str, Any]:
        pending_count = 0
        try:
            latest_by_event: Dict[str, Dict[str, Any]] = {}
            for entry in self._read_outbox_entries():
                event_id = str(entry.get("event_id", "")).strip()
                if not event_id:
                    continue
                latest_by_event[event_id] = entry
            pending_count = sum(
                1
                for entry in latest_by_event.values()
                if str(entry.get("status")) in {"pending_publish", "pending_commit"}
            )
        except Exception:
            pending_count = 0

        return {
            "enabled": self.enabled,
            "configured": self._is_configured(),
            "subject": self.subject,
            "listening": self._listening,
            "last_state_hash": self._last_state_hash,
            "last_error": self._last_error,
            "last_validation": dict(self._last_validation or {}),
            "pending_events": pending_count,
            "outbox_path": str(self.outbox_path),
            "metrics": dict(self._metrics),
            "transport": self.transport.__class__.__name__ if self.transport is not None else None,
        }


_mesh_sync_service: Optional[MeshSyncService] = None


def get_mesh_sync_service() -> MeshSyncService:
    global _mesh_sync_service
    if _mesh_sync_service is None:
        _mesh_sync_service = MeshSyncService()
    return _mesh_sync_service


__all__ = [
    "DEFAULT_MESH_SUBJECT",
    "MeshSyncService",
    "MeshTransport",
    "NatsJetStreamMeshTransport",
    "get_mesh_sync_service",
]
