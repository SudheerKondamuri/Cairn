"""Transactional trial admission. Call only with a verified server identity.

Each operation owns a connection; no connection is shared across request threads.
The global lock serializes admission across API replicas. A reservation must be
created in the same transaction as its queued job when integrated with submission.
"""
from __future__ import annotations

import secrets
from typing import Any


class AdmissionDenied(ValueError):
    """The trial cannot accept this request."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def reserve(cursor: Any, *, account_id: str, idempotency_key: str, request_digest: str) -> tuple[str, bool]:
    """Reserve once; return (id, created). Caller commits or rolls back the job too."""
    if not account_id or not 16 <= len(idempotency_key) <= 128 or len(request_digest) != 64:
        raise AdmissionDenied('invalid_request')
    try:
        int(request_digest, 16)
    except ValueError as exc:
        raise AdmissionDenied('invalid_digest') from exc
    cursor.execute('SELECT run_limit, paused FROM cairn_trial WHERE singleton = TRUE FOR UPDATE')
    trial = cursor.fetchone()
    if trial is None:
        raise AdmissionDenied('not_configured')
    cursor.execute('SELECT run_limit, suspended FROM cairn_accounts WHERE account_id = %s FOR UPDATE', (account_id,))
    account = cursor.fetchone()
    if account is None or account[1]:
        raise AdmissionDenied('account_unavailable')
    cursor.execute('SELECT reservation_id, request_digest FROM cairn_reservations WHERE account_id = %s AND idempotency_key = %s', (account_id, idempotency_key))
    existing = cursor.fetchone()
    if existing:
        if existing[1] != request_digest:
            raise AdmissionDenied('idempotency_conflict')
        return existing[0], False
    if trial[1]:
        raise AdmissionDenied('trial_paused')
    cursor.execute("SELECT count(*), count(*) FILTER (WHERE account_id = %s) FROM cairn_reservations WHERE state <> 'released'", (account_id,))
    total, owned = cursor.fetchone()
    if owned >= account[0]:
        raise AdmissionDenied('account_allowance_exhausted')
    if total >= trial[0]:
        raise AdmissionDenied('trial_allowance_exhausted')
    reservation_id = 'inv-' + secrets.token_hex(12)
    cursor.execute('INSERT INTO cairn_reservations (reservation_id, account_id, idempotency_key, request_digest) VALUES (%s, %s, %s, %s)', (reservation_id, account_id, idempotency_key, request_digest))
    return reservation_id, True


def transition(cursor: Any, reservation_id: str, event: str) -> bool:
    """Only pre-execution reservations can be refunded. Terminal state is immutable."""
    transitions = {
        'start': ('reserved', 'started'),
        'finish': ('started', 'finished'),
        'release_before_execution': ('reserved', 'released'),
    }
    if event not in transitions:
        raise ValueError('unknown reservation event')
    previous, following = transitions[event]
    cursor.execute('UPDATE cairn_reservations SET state = %s, updated_at = now() WHERE reservation_id = %s AND state = %s', (following, reservation_id, previous))
    return cursor.rowcount == 1
