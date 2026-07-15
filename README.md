Looni Commerce — Alpha v0.1.0
=================================

Lightweight marketplace reference implementation used for LICOS experimentation and integration.

This repository implements a small domain-driven marketplace with in-memory repositories, a simple event store (LICOS), and a FastAPI HTTP surface for exercising workflows.

Key capabilities
- Create and activate users
- Create, publish and manage listings
- Search published listings
- Create, accept and cancel reservations
- In-memory repositories for testing and local development
- Event recording via LICOS EventStore/EventRecorder

Getting started
- See `docs/QUICKSTART.md` for a short, hands-on guide to run the app locally and exercise the HTTP API.

Running tests
- Tests are executed with pytest. From the repository root run:

```bash
python -m pytest -q
```

Running the FastAPI app
- The application factory is `app.main:app`. You can run with Uvicorn:

```bash
uvicorn app.main:app --reload
```

Open the interactive API docs at `http://127.0.0.1:8000/docs`.

Repository structure (top-level)
- `app/` — FastAPI application, routes and dependency wiring
- `application/` — application services (MarketplaceService)
- `domain/` — domain models, services and repositories protocols
- `infrastructure/` — memory-backed repository implementations
- `kernel/` — LICOS event types, store and recorder integration
- `tests/` — unit, integration and acceptance tests
- `docs/` — higher-level documentation (architecture, API, quickstart, release notes)

License & contribution
- This project is a minimal example for demonstration; check project owner policies for licensing and contribution notes.
# Looni Commerce

Mission:
Modern trusted AI-assisted local marketplace.

Status:
Pre-Alpha

Repository purpose:
This repository contains the business application.

Shared capabilities belong in licos-core.
