#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HEBOM Universal AI Buffer v4 — PASS / TAKE.

Public surface is intentionally tiny:
    room.pass_(data, ...)
    item = room.take(...)

The room is a transport buffer, not a ledger. Anything that needs durable
records can consume accepted events asynchronously through `after_sink`.
This reference implementation is process-local; production scale requires a
partitioned durable broker/backend while preserving this two-operation API.
"""
from __future__ import annotations
import hashlib, json, queue, threading, time, uuid
from dataclasses import dataclass, asdict
from typing import Any, Optional

VERSION = "4.0.0"


def _canon(x: Any) -> bytes:
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _hash(x: Any) -> str:
    return hashlib.sha256(_canon(x)).hexdigest()


@dataclass(frozen=True)
class Envelope:
    id: str
    intent: str
    sender: str
    recipient: str
    type: str
    version: int
    payload: Any
    refs: tuple[str, ...]
    created_at: float
    expires_at: Optional[float]
    payload_hash: str

    def public(self) -> dict:
        d = asdict(self)
        d["refs"] = list(self.refs)
        return d


class BufferFull(RuntimeError): pass
class InvalidEnvelope(ValueError): pass


class UniversalRoom:
    """A simple universal buffer facade for AI↔AI exchange.

    Design invariants:
    - External API: PASS / TAKE only.
    - Payload is opaque: text, JSON, bytes reference, multilingual content, etc.
    - Room validates transport metadata; it does not pretend to understand all languages.
    - Duplicate IDs are accepted once only.
    - Backpressure is explicit: overload returns BUSY instead of silent waiting.
    - Long-term recording is intentionally outside the hot path via optional after_sink.
    """
    def __init__(self, *, capacity: int = 100_000, after_sink=None):
        if capacity < 1: raise ValueError("capacity must be >= 1")
        self._q = queue.Queue(maxsize=capacity)
        self._seen: set[str] = set()
        self._seen_lock = threading.Lock()
        self._after_sink = after_sink
        self._accepted = 0
        self._taken = 0
        self._stats_lock = threading.Lock()

    def pass_(self, data: Any, *, intent: str="", sender: str="", recipient: str="*",
              type: str="DATA", version: int=1, refs=(), event_id: Optional[str]=None,
              ttl_s: Optional[float]=None) -> dict:
        """PASS: put one opaque payload into the room. Never blocks on overload."""
        eid = event_id or uuid.uuid4().hex
        if not isinstance(eid, str) or not eid: raise InvalidEnvelope("event_id required")
        if not isinstance(version, int) or version < 1: raise InvalidEnvelope("version must be positive integer")
        if ttl_s is not None and ttl_s <= 0: raise InvalidEnvelope("ttl_s must be > 0")
        now = time.time()
        env = Envelope(
            id=eid, intent=str(intent or ""), sender=str(sender or ""),
            recipient=str(recipient or "*"), type=str(type or "DATA"), version=version,
            payload=data, refs=tuple(str(x) for x in refs), created_at=now,
            expires_at=(now + ttl_s) if ttl_s is not None else None,
            payload_hash=_hash(data),
        )
        with self._seen_lock:
            if eid in self._seen:
                return {"ok": True, "code": "DUPLICATE", "accepted": False, "id": eid}
            # Reserve before queue insertion; roll back if admission fails.
            self._seen.add(eid)
        try:
            self._q.put_nowait(env)
        except queue.Full:
            with self._seen_lock: self._seen.discard(eid)
            return {"ok": False, "code": "BUSY", "accepted": False, "retry": True, "depth": self._q.qsize()}
        with self._stats_lock: self._accepted += 1
        return {"ok": True, "code": "ACCEPTED", "accepted": True, "id": eid, "depth": self._q.qsize()}

    def take(self, *, timeout_s: float=0.0, recipient: Optional[str]=None) -> Optional[dict]:
        """TAKE: receive the next valid item. Empty room returns None.

        recipient filtering is intentionally conservative in this reference kernel:
        unmatched items are put back; production uses recipient/intent partition routing.
        """
        deadline = time.monotonic() + max(0.0, timeout_s)
        skipped = []
        try:
            while True:
                remaining = max(0.0, deadline - time.monotonic()) if timeout_s else 0.0
                try:
                    env = self._q.get(timeout=remaining) if timeout_s else self._q.get_nowait()
                except queue.Empty:
                    return None
                if env.expires_at is not None and time.time() > env.expires_at:
                    self._q.task_done()
                    continue
                if recipient is not None and env.recipient not in ("*", recipient):
                    skipped.append(env); self._q.task_done()
                    if self._q.empty(): return None
                    continue
                self._q.task_done()
                with self._stats_lock: self._taken += 1
                item = env.public()
                if self._after_sink is not None:
                    # AFTER PATH: never changes PASS/TAKE semantics. Sink failure is isolated.
                    try: self._after_sink(item)
                    except Exception: pass
                return item
        finally:
            for env in skipped:
                try: self._q.put_nowait(env)
                except queue.Full: pass

    def stats(self) -> dict:
        """Operational visibility; not part of the universal interoperability contract."""
        with self._stats_lock:
            return {"version": VERSION, "accepted": self._accepted, "taken": self._taken,
                    "depth": self._q.qsize(), "capacity": self._q.maxsize}


# Friendly aliases. External contract remains PASS / TAKE.
Room = UniversalRoom
