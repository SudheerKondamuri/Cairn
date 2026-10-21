CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    sandbox_name TEXT UNIQUE NOT NULL,
    problem_id TEXT NOT NULL,
    state TEXT NOT NULL CHECK (
        state IN ('created', 'ready', 'running', 'succeeded', 'failed', 'deleted')
    ),
    outcome TEXT,
    execution_target TEXT NOT NULL DEFAULT 'celesto_sandbox'
        CHECK (execution_target = 'celesto_sandbox'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO runs (run_id, sandbox_name, problem_id, state, outcome, execution_target)
VALUES ('seed-demo-1', 'sbx-seeddemo1', 'seed', 'deleted', 'succeeded', 'celesto_sandbox')
ON CONFLICT (sandbox_name) DO NOTHING;

CREATE TABLE IF NOT EXISTS investigations (
    investigation_id TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'completed', 'failed')),
    report TEXT NOT NULL,
    manifest JSONB NOT NULL,
    source_path TEXT NOT NULL,
    result JSONB,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
