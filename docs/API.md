API Reference — Looni Commerce (Alpha v0.1.0)
=================================================

All endpoints are exposed by the FastAPI application in `app.main`.

Unversioned endpoints

Health
- GET / -> 200 OK
- GET /health -> 200 OK

API v1 (/api/v1)

Users
- POST /api/v1/users
  - Request JSON: {"display_name": "Alice", "email": "alice@example.com"}
  - Response (201): User DTO

- GET /api/v1/users/{id}
  - Response (200): User DTO

- POST /api/v1/users/{id}/activate
  - Response (200): User DTO (activated)

Listings
- POST /api/v1/listings
  - Request JSON: {
      "seller_id": "<uuid>", "title":"...", "description":"...",
      "price":"12.50","currency":"USD","category":"Books",
      "condition":"GOOD","location":"Online"
    }
  - Response (201): Listing DTO

- GET /api/v1/listings/{id}
  - Response (200): Listing DTO

- POST /api/v1/listings/{id}/publish
  - Response (200): Listing DTO (PUBLISHED)

Search
- GET /api/v1/search
  - Query params: `q` (keyword), `category`, `seller_id`, `published_only` (default true)
  - Response (200): {"count": N, "items": [ListingResponse,...]}

Reservations
- POST /api/v1/reservations
  - Request JSON: {"buyer_id":"<uuid>", "listing_id":"<uuid>"}
  - Response (201): Reservation DTO (PENDING)

- GET /api/v1/reservations/{id}
  - Response (200): Reservation DTO

- POST /api/v1/reservations/{id}/accept
  - Request JSON: {"seller_id":"<uuid>"}
  - Response (200): Reservation DTO (ACCEPTED)

- POST /api/v1/reservations/{id}/cancel
  - Response (200): Reservation DTO (CANCELLED)

Authentication
- POST /api/v1/auth/register
  - Request JSON: {"display_name": "Alice", "email": "alice@example.com", "password": "SecurePassword123!"}
  - Response (201): User DTO (status: PENDING)

- POST /api/v1/auth/login
  - Request JSON: {"email": "alice@example.com", "password": "SecurePassword123!"}
  - Response (200): {"access_token": "<jwt>", "token_type": "bearer", "expires_in": <seconds>}

- GET /api/v1/auth/me
  - Headers: {"Authorization": "Bearer <jwt>"}
  - Response (200): User DTO (authenticated user)

DTO examples (abbreviated)

User DTO
{
  "id": "<uuid>",
  "display_name": "Alice",
  "email": "alice@example.com",
  "status": "PENDING|ACTIVE",
  "created_at": "2026-07-14T...",
  "updated_at": "2026-07-14T..."
}

Listing DTO
{
  "id":"<uuid>", "seller_id":"<uuid>", "title":"...",
  "description":"...", "category":"Books", "price":"12.50",
  "currency":"USD", "status":"DRAFT|PUBLISHED|RESERVED|SOLD",
  "created_at": "...","updated_at":"..."
}

Reservation DTO
{
  "id":"<uuid>", "listing_id":"<uuid>", "buyer_id":"<uuid>", "seller_id":"<uuid>",
  "status":"PENDING|ACCEPTED|CANCELLED", "created_at":"...","updated_at":"..."
}
