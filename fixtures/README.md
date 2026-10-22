# Cairn fixture applications

The four applications are deliberately tiny, local-only standard-library HTTP
fixtures for testing CWE-78 (OS command injection): Pattern A uses `host` in
`/diagnose`, and Pattern B uses `filename` in `/convert`. Each pattern has a
vulnerable and patched variant. They use no guest dependencies, so they can run
with Celesto outbound networking disabled. They must only run inside a
disposable Celesto sandbox or a local test process; they are not production
applications.
