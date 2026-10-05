# NOW: fx-service

**Updated:** 2026-03-12 16:40 by Claude Code (laptop)

## State
- `main` is deployed to staging (v0.8.2). Production is on v0.8.1.
- Rounding bug reported by finance: EUR→JPY conversions are off by one yen on some amounts. Not investigated yet.

## Where things live
- Service code: `app/rates.py`, tests in `tests/test_rates.py`
- Staging: https://fx-staging.example.internal (port 8443)
- Bug report: ticket FIN-212

## Next
1. Investigate the rounding bug (FIN-212).
2. Rotate the staging database password. Priya asked for this by 2026-03-20; steps are in `docs/runbook.md` section 4.
3. Bump production to v0.8.2 once FIN-212 is closed.

## Gotchas
- Staging uses a self-signed cert; pass `--insecure` to the smoke test script.
