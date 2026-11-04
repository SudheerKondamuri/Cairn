# Cairn web application

Next.js public evidence pages and an account-based investigation workspace. Google/GitHub sign-in, three investigations per account, 50 globally, public GitHub import, live worker events, cancellation, private report history, exports, revocable sharing, and administrator controls.

Local mode (`CAIRN_ACCESS_MODE=local`) opens the workspace directly without sign-in. Hosted deployments require Google/GitHub OAuth credentials. Operator keys are no longer used. The public pages work without provider credentials.

For frontend development, copy `.env.example` to `.env.local` without overwriting an existing file, configure the server-only values, then run `npm ci` and `npm run dev`. Backend and worker setup is in the deployment guide. `npm run build` creates the standalone production server; `npm run start` starts it.

Checks: `npm run typecheck`, `npm run lint`, `npm run build`. Account integration tests use isolated PostgreSQL; no live Celesto calls are required for these tests. Production OAuth and a fresh Celesto job require real configured providers.

Design: the existing basalt/red Cairn identity, self-hosted Manrope/Schibsted Grotesk, authored CSS, light/dark workspace themes, and responsive keyboard-accessible controls. Taste and Impeccable informed the interface. AI coding assistance: OpenAI Codex.
