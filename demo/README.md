# Demo recording

`walkthrough.mp4` contains the recorded demo. Check that the final submission
recording is three minutes or less and shows
the self-owned Northstar diagnostics application, the Celesto guest, the
independent recheck, and guest cleanup. Record it after Gate 0 and the one-case
live smoke run pass.

For a repeatable recording, keep credentials in an uncommitted file outside the
repository and run this from a terminal while capturing the screen:

```bash
CAIRN_ENV_FILE=/var/tmp/cairn.env demo/run-demo.sh
```

The script prints only the investigation result and cleanup state; never show
the environment file or an API key.

For the full Docker/API/worker version, use the same external credentials file:

```bash
CAIRN_ENV_FILE=/var/tmp/cairn.env demo/run-docker-demo.sh
```

That starts the trusted API and Postgres ledger, queues the Northstar source
through the multipart API, and lets the worker create the Celesto guest. It
leaves the Docker services running so their health and logs can be shown; stop
them after recording with
`docker compose --env-file /var/tmp/cairn.env --profile worker down`.
