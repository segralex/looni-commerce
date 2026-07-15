Architecture — Looni Commerce (Alpha v0.1.0)
=================================================

High level
- The project follows a domain-driven, hexagonal-style separation:
  - `domain/` contains entities, value objects, domain services and protocols for repositories.
  - `application/` contains orchestration logic — `MarketplaceService` implements workflows using repositories and domain services.
  - `infrastructure/` contains concrete adapters (in-memory repositories) that implement domain repository protocols.
  - `app/` contains the FastAPI HTTP surface and dependency wiring that composes singletons for runtime.
  - `kernel/` provides LICOS event primitives: `DomainEvent`, `EventStore` and `EventRecorder`.

Domain
- Entities: `User`, `Listing`, `Reservation` live in `domain/*/models.py`.
- Domain services encapsulate core rules (e.g. `ListingService`, `ReservationService`) and support an in-memory _store for local testing.

Application
- `application.marketplace.service.MarketplaceService` orchestrates cross-aggregate workflows (create/publish listing, create/accept/cancel reservation). It accepts optional repository adapters and an `EventRecorder` for LICOS integration.

Repositories
- The domain defines repository Protocols and expected behavior (add, get, save, all).
- `infrastructure.repositories.memory` implements simple in-memory repositories preserving insertion order and supporting basic CRUD semantics used by tests and local runs.

Infrastructure
- Memory repositories live in `infrastructure/` and are intentionally simple to make workflows deterministic for tests.

LICOS integration
- `kernel.events.store.EventStore` holds `DomainEvent` instances in-memory; `kernel.integration.recorder.EventRecorder` records events emitted by `MarketplaceService`.
- Services call `MarketplaceService._record_event(...)` to persist domain events; events can be inspected in tests via `EventStore.all_events()`.

Dependency flow
- `app.dependencies` wires singleton instances used at runtime:
  - `MemoryUserRepository`, `MemoryListingRepository`, `MemoryReservationRepository`
  - `EventStore`, `EventRecorder`
  - `MarketplaceService` composed with the above adapters
- Tests use the exported `reset_singletons()` helper to recreate fresh singleton instances between test cases for isolation.
