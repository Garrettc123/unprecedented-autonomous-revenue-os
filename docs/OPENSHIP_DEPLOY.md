# Openship deploy plane (GAR-534)

Product: [openship.io](https://openship.io) — self-hostable deploy platform.
Not [openship.org](https://openship.org) (order router). Not OpenRig.

This file is the host runbook. Values for secrets are never committed.

## What this repo ships on Openship

`contract/` FastAPI sidecar (`Dockerfile` already exposes `:8080`).

| Probe | Expect |
|---|---|
| `GET /health` | `status=healthy` |
| `GET /meta` | `event_bus_connected` true only after `REDIS_URL` is set on the project |

## Install control plane (once, on your machine or VPS)

```bash
curl -fsSL https://get.openship.io | sh
# Node 22+ alternative: npm i -g openship

openship up
# Linux + Docker → Postgres, Redis, API :4000, dashboard :3001, edge :80/:443
```

Dashboard login is created on first `openship up`. Connect GitHub under **Settings → Git**.

Targets: **Local** (try), **Your server** (SSH + Docker), or **Openship Cloud**.

## Create and ship this project

```bash
openship project create --name revenue-os \
  --git-owner Garrettc123 \
  --git-repo unprecedented-autonomous-revenue-os

# Gate 1 — set on the host, never in chat
openship project env set revenue-os --set REDIS_URL="$REDIS_URL" --secret
openship project env set revenue-os --set GARCAR_TENANT_ID=garcar-enterprise

openship deploy
openship project git auto-deploy revenue-os --enable
```

If Openship Compose already runs Redis on the same box:

```text
REDIS_URL=redis://redis:6379/0
```

Use the URL Openship prints for that Redis service. Do not invent it.

## Fleet that still needs the same host secrets

Set these on each client project. Do not put them in `openship.json`.

| Project | Repo | Secrets |
|---|---|---|
| revenue-os | `Garrettc123/unprecedented-autonomous-revenue-os` | `REDIS_URL`, `GARCAR_TENANT_ID` |
| ai-orchestrator | `Garrettc123/ai-orchestrator` | `MARS_REASON_URL`, `MARS_API_KEY`, Stripe keys already live |
| mars-production | host service | reason API key (issuer) |
| mars-api | host service | `MARS_REASON_URL`, `MARS_API_KEY` |
| garcar-base | host service | `MARS_REASON_URL`, `MARS_API_KEY` |

```bash
openship project env set ai-orchestrator --set MARS_REASON_URL="$MARS_REASON_URL" --secret
openship project env set ai-orchestrator --set MARS_API_KEY="$MARS_API_KEY" --secret
openship deploy --refresh
```

`--refresh` restarts with new env and does not rebuild.

## Done checks

```bash
curl -s "$REVENUE_OS_URL/health"
curl -s "$REVENUE_OS_URL/meta"   # event_bus_connected must be true
```

Then GAR-533 (outbox publisher) can talk to Redis without the Railway Variables UI.

## Safety

- Never commit `REDIS_URL`, `MARS_API_KEY`, or Stripe secrets.
- Never charge livemode with card 4242.
- Openship Cloud vs own VPS is your call; cash path (LLA-47) stays Stripe livemode `acct_1SS3dpFKGbk21LK5` either way.
