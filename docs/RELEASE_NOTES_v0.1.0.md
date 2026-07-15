Release Notes — Looni Commerce v0.1.0 (Alpha)
=================================================

This release consolidates the initial series of development objectives (EOs) implementing core marketplace workflows, in-memory repositories, HTTP API surface and test harnesses.

Implemented items (high-level)
- EO-LC-000008B: In-memory repository implementations for `User`, `Listing`, and `Reservation` with tests.
- EO-LC-000009: `MarketplaceService` refactored to use repository injection and optionally an `EventRecorder`.
- EO-LC-000010: FastAPI application bootstrapped with singleton wiring in `app.dependencies`.
- EO-LC-000011 / 000012: User and Listing HTTP endpoints implemented and tested.
- EO-LC-000013: Search API implemented using `SearchService`; route returns count + listing responses.
- EO-LC-000013A: Pydantic v2 migration updates (`ConfigDict(from_attributes=True)`) applied to schemas.
- EO-LC-000013B: Test isolation helper `reset_singletons()` added and tests updated to use it.
- EO-LC-000014 / 000014A: Reservation HTTP endpoints and cancel orchestration moved into `MarketplaceService`.
- EO-LC-000015: End-to-end HTTP acceptance test added to exercise the full marketplace through the public API.

Current limitations
- Persistence: all repositories are in-memory only — no external database backing.
- Scalability: single-process in-memory stores are for local development and tests only.
- Security: no authentication/authorization implemented.
- Validation: input validation is intentionally minimal to keep the example compact.

Future roadmap
- Add pluggable persistent repository implementations (SQL/NoSQL adapters).
- Add authentication and multi-tenant support.
- Improve event semantics (explicit event types for restore/unreserve) and durable event storage.
- Add API pagination and richer search capabilities.

Known exclusions
- No UI is provided — API-only reference implementation.
- No background workers or async job processing; workflows are synchronous for clarity.
