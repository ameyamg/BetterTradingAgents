<!-- Branch off `dev` (see CONTRIBUTING.md). PRs to `main` need green CI. -->

## Summary

<!-- What changes and why. Two or three sentences. -->

## Test evidence

- [ ] `uv run test` green (fast offline suite)
- [ ] `uv run test all` green (full gate, including browser smoke)
- [ ] Wiki/docs updated when behavior or config changed

## House rules

- [ ] No secrets in commits, `.env` untouched, keys stay in the OS keychain
- [ ] Paper trading only (Alpaca client stays `paper=True`)
- [ ] Loopback guards intact (127.0.0.1 bind, Host/Origin checks)
