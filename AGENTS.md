# Agent context — cogrion-cli

## What this repo is

The developer-facing CLI for the Cogrion BYOC platform: authentication, cluster linking, and deploys. Intended to eventually absorb what `cogrion-bootstrap` does today, wrapped in a single cohesive `cogrion` command instead of a standalone bootstrap script.

## Layout

```
cogrion_cli/
  cli.py            # Typer root app, global --json flag, KeyboardInterrupt handling
  config.py         # app_dir()/config_file() — session state under typer.get_app_dir()
  state.py          # shared State dataclass (json_output flag, etc.)
  commands/
    auth.py         # `cogrion auth ...`
    cluster.py      # `cogrion cluster ...`
    deploy.py       # `cogrion deploy ...`
```

## Conventions

- No comments unless the WHY is non-obvious
- Sub-apps live under `commands/`, one file per top-level noun (`auth`, `cluster`, `deploy`) — do not put unrelated commands in an existing file
- Every command must respect the global `--json` flag once it has real output — no `rich` formatting when `state.json_output` is set
- Session/auth state goes through `config.py`'s `app_dir()`, never a hardcoded path
- Version bumps: `make bump-patch` / `make bump-minor` / `make bump-major` — never edit `VERSION` or `pyproject.toml` by hand
