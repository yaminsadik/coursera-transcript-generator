# Contributing

Contributions should preserve the separation between Coursera transport,
hierarchy mapping, orchestration, reporting, presentation, and persistence.
Start with [the architecture guide](docs/architecture.md) before changing a
cross-cutting workflow.

## Local setup

```bash
git clone https://github.com/yaminsadik/coursera-transcript-generator.git
cd coursera-transcript-generator
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Required checks

```bash
ruff check src tests
ruff format --check src tests
python -m unittest discover -s tests -v
python -m build
```

Tests must not require a Coursera account or a live CAUTH cookie. Add or update
mocked response fixtures when changing hierarchy or API behavior. Never commit
real cookies, signed subtitle URLs, or private course content.

## Pull requests

- Keep each pull request focused on one coherent change.
- Describe user-visible output or manifest schema changes.
- Add tests for success, failure, and interruption paths where relevant.
- Update the README, architecture guide, and changelog when behavior changes.
- Treat manifest fields and output paths as public compatibility surfaces.
