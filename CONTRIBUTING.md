# Contributing to foundry-apim-token-metering-reference-architecture

Thank you for your interest in contributing! This document explains how to
get involved.

## Code of Conduct

Please read [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) before contributing.

## Ways to Contribute

- **Bug reports** – Open a GitHub Issue with reproduction steps.
- **Feature requests** – Open a GitHub Issue describing the use case.
- **Pull Requests** – Implement a fix or feature; see process below.
- **Documentation** – Improvements to docs/ are very welcome.

## Development Setup

### Python agent app

```bash
cd src/agent-app
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install ruff mypy pytest pytest-cov pytest-asyncio httpx
```

### Bicep / IaC

```bash
az bicep install                # install Bicep CLI
az bicep build --file infra/bicep/main.bicep   # validate
```

## Pull Request Process

1. Fork the repository and create a feature branch from `main`:
   ```bash
   git checkout -b feat/your-feature-name
   ```
2. Make your changes. Keep commits small and focused.
3. Run all checks locally before pushing:
   ```bash
   # From src/agent-app/
   ruff check app/ tests/
   mypy app/
   pytest tests/ -v --cov=app
   # From repo root
   az bicep build --file infra/bicep/main.bicep
   ```
4. Push and open a Pull Request targeting `main`.
5. Fill in the PR template. Link any related Issues.
6. A maintainer will review and provide feedback.

## Coding Standards

| Area | Standard |
|---|---|
| Python | PEP 8; ruff enforced in CI |
| Type hints | Required in public functions; mypy strict |
| Bicep | Follow [Azure Bicep best practices](https://learn.microsoft.com/azure/azure-resource-manager/bicep/best-practices) |
| APIM policies | Comment non-obvious policy expressions |
| Secrets | Never hardcode credentials; use Managed Identity or Key Vault references |
| Tests | New features need new/updated tests |

## Commit Message Format

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short summary>

[optional body]

[optional footer]
```

Types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `ci`.

## Questions

Open a GitHub Discussion or issue — we're happy to help.
