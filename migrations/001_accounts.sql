-- Apply transactionally before enabling public account access.
CREATE TABLE IF NOT EXISTS cairn_accounts (
    account_id TEXT PRIMARY KEY,
    suspended BOOLEAN NOT NULL DEFAULT FALSE,
    run_limit INTEGER NOT NULL DEFAULT 3 CHECK (run_limit >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
INSERT INTO cairn_accounts(account_id, run_limit) VALUES ('acct-local', 999999) ON CONFLICT (account_id) DO UPDATE SET run_limit = 999999, suspended = FALSE;
CREATE TABLE IF NOT EXISTS cairn_identities (
    provider TEXT NOT NULL CHECK (provider IN ('google', 'github')),
    subject TEXT NOT NULL,
    account_id TEXT NOT NULL REFERENCES cairn_accounts(account_id),
    PRIMARY KEY (provider, subject)
);
CREATE TABLE IF NOT EXISTS cairn_trial (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    run_limit INTEGER NOT NULL DEFAULT 50 CHECK (run_limit >= 0),
    paused BOOLEAN NOT NULL DEFAULT FALSE
);
INSERT INTO cairn_trial(singleton) VALUES (TRUE) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS cairn_reservations (
    reservation_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES cairn_accounts(account_id),
    idempotency_key TEXT NOT NULL,
    request_digest TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'reserved' CHECK (state IN ('reserved', 'started', 'finished', 'released')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (account_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS cairn_reservations_account ON cairn_reservations(account_id, state);
CREATE TABLE IF NOT EXISTS cairn_sessions (
    token_hash TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES cairn_accounts(account_id),
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS cairn_web_jobs (
    investigation_id TEXT PRIMARY KEY REFERENCES cairn_reservations(reservation_id),
    account_id TEXT NOT NULL REFERENCES cairn_accounts(account_id),
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','completed','failed','cancelled')),
    report TEXT NOT NULL,
    manifest JSONB NOT NULL,
    source_path TEXT NOT NULL,
    result JSONB,
    error TEXT,
    cancel_requested BOOLEAN NOT NULL DEFAULT FALSE,
    deleted BOOLEAN NOT NULL DEFAULT FALSE,
    share_hash TEXT UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT now() + interval '30 days'
);
CREATE INDEX IF NOT EXISTS cairn_web_jobs_owner ON cairn_web_jobs(account_id, created_at DESC);
CREATE TABLE IF NOT EXISTS cairn_job_events (
    event_id BIGSERIAL PRIMARY KEY,
    investigation_id TEXT NOT NULL REFERENCES cairn_web_jobs(investigation_id),
    message TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS cairn_allowance_requests (
    account_id TEXT PRIMARY KEY REFERENCES cairn_accounts(account_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS cairn_admin_audit (
    event_id BIGSERIAL PRIMARY KEY,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    details JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
