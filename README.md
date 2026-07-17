# Cogrion CLI

Developer CLI for the Cogrion BYOC platform — authentication, cluster linking, and deploys, in one tool.

## Install

```bash
pipx install --editable .
```

Editable install picks up local code changes without reinstalling — restart your shell (or `hash -r`) if `cogrion` doesn't reflect a change.

## Usage

```bash
cogrion auth login
cogrion cluster connect --provider aws
cogrion deploy run --env prod
```

## Development

```bash
make install
make test
make lint
```

See [AGENTS.md](AGENTS.md) for repo conventions.
