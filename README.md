# CleanDesk AI: Multi-Tenant Merchant Inventory & Real-Time Operations Platform

A full-stack, backend-heavy merchant inventory and order-approval application engineered for strict tenant isolation, Redis cache-aside optimization, atomic sliding-window rate limiting, and real-time multi-user WebSocket broadcasting.

---

## 1. System Architecture & Tech Stack

```
                     +---------------------------------------+
                     |        React / Vite Frontend          |
                     |  (Live Dashboard, Catalog, Approvals) |
                     +-------------------+-------------------+
                                         |
                       HTTP REST / WS    | JWT Authenticated
                                         v
                     +---------------------------------------+
                     |           FastAPI Gateway             |
                     |  - Multi-Tenant Scoping Dependency    |
                     |  - Sliding-Window Rate Limiter (ZSET) |
                     |  - WebSocket Room Broadcaster         |
                     +---------+-------------------+---------+
                               |                   |
            Cache-Aside / TTL  |                   | Atomic Transactions / Asyncpg
                               v                   v
                     +-------------------+   +-----------------------+
                     |    Redis 7.x      |   |    PostgreSQL 15      |
                     |  - Scoped Caching |   |  - Normalized Schema  |
                     |  - Sliding Window |   |  - Composite Indexes  |
                     |  - Invalidation   |   |  - Row-Level Locking  |
                     +-------------------+   +-----------------------+
```

### Architectural Choices & Justifications
* **FastAPI + SQLAlchemy 2.0 (`asyncpg`)**: Native Python asynchronous I/O enables high-concurrency database queries, non-blocking WebSocket connections, and streaming CSV responses without the complexity or bridge overhead of Django Channels.
* **PostgreSQL 15**: Normalized relational schemas with explicit foreign-key tenant scoping, check constraints, composite indexing, and row-level locks (`SELECT ... FOR UPDATE`).
* **Redis 7.x**: Atomic sorted sets (`ZSET`) for sliding-window rate limiting, tenant-scoped cache-aside queries, and explicit cache invalidation.
* **React 18 + Vite + Tailwind CSS**: Responsive, stateful frontend featuring live KPI metrics, instant WebSocket notifications, inline editing, and atomic CSV bulk updates.

---

## 2. Database Design & Indexing Rationale

### Schema Entities
1. **`merchants`**: `id` (PK), `name`, `slug` (Unique), `status`, `created_at`
2. **`users`**: `id` (PK), `merchant_id` (FK -> `merchants.id`), `name`, `email` (Unique), `password_hash`, `role` (`OWNER`, `STAFF`), `created_at`
3. **`products`**: `id` (PK), `merchant_id` (FK -> `merchants.id`), `sku`, `name`, `category`, `unit_price`, `stock_quantity`, `low_stock_threshold`, `updated_at`
4. **`stock_approval_requests`**: `id` (PK), `merchant_id` (FK -> `merchants.id`), `product_id` (FK -> `products.id`), `requested_by` (FK -> `users.id`), `approved_by` (FK -> `users.id`), `quantity_delta`, `reason`, `status` (`PENDING`, `APPROVED`, `REJECTED`), `created_at`, `resolved_at`

### Indexing Choices & Rationale (CleanDesk AI Requirement)

| Table | Index Columns | Index Type | Architectural Justification |
| :--- | :--- | :--- | :--- |
| **`products`** | `(merchant_id, sku)` | `UniqueConstraint` & Composite B-Tree Index | Enforces **tenant-scoped SKU uniqueness** (different merchants may use identical SKUs, but a single merchant cannot). Accelerates $O(\log N)$ point lookups during single and bulk SKU updates. |
| **`products`** | `(merchant_id, category)` | Composite B-Tree Index | Eliminates full table scans when paginating and filtering catalog queries by category for a specific merchant. |
| **`products`** | `(merchant_id, stock_quantity, low_stock_threshold)` | Composite B-Tree Index | Speeds up low-stock filtering (`WHERE merchant_id = ? AND stock_quantity <= low_stock_threshold`) and real-time dashboard calculations. |
| **`stock_approval_requests`** | `(merchant_id, status)` | Composite B-Tree Index | **Explicitly required by CleanDesk AI**. Enables instant retrieval of `PENDING` approval queues and pending counters without scanning historical resolved requests. |

### Relational Integrity & Safeguards
* `CheckConstraint("stock_quantity >= 0", name="chk_stock_quantity_non_negative")`
* `CheckConstraint("unit_price >= 0", name="chk_unit_price_non_negative")`
* `ForeignKey(..., ondelete="CASCADE")` on tenant boundaries to prevent orphaned records.

---

## 3. Redis Cache-Aside & Invalidation Strategy

### 1. Tenant-Scoped Key Conventions
All Redis keys are strictly namespaced by tenant ID:
* **Dashboard KPIs**: `merchant:{merchant_id}:dashboard:metrics`
* **Default Catalog**: `merchant:{merchant_id}:products:default`

### 2. Cache-Aside Execution Flow
1. **Read Request** (`GET /dashboard/metrics` or `GET /products`):
   * Application queries Redis via `GET merchant:{merchant_id}:...`.
   * **Cache Hit**: Returns cached JSON payload immediately (`from_cache: true`).
   * **Cache Miss**: Queries PostgreSQL, computes aggregations, sets Redis key with a 300-second TTL (`SETEX`), and returns fresh data (`from_cache: false`).
2. **Explicit Invalidation**:
   * Any state-mutating operation immediately purges cached entries via `redis.delete(...)`:
     * Product created (`POST /products`)
     * Product updated (`PUT /products/{id}`)
     * Atomic bulk update committed (`POST /products/bulk-update`)
     * Approval decision resolved (`POST /approvals/{id}/decision`)
3. **Graceful Degradation**:
   * If Redis is temporarily down or unreachable, the `CacheService` catches all `RedisError` exceptions, logs an operational warning, and falls back directly to PostgreSQL queries. **The application never returns an HTTP 500 due to a cache failure.**

---

## 4. Sliding-Window Auth Rate Limiter

* **Target Route**: `POST /auth/login`
* **Limit**: Max 5 failed attempts per rolling 60-second window per `IP:Email` identifier.
* **Implementation**: Uses Redis Sorted Sets (`ZSET`) executed inside an atomic pipeline:
  ```
  1. ZREMRANGEBYSCORE key 0 (now - 60s)    # Prune expired attempts
  2. ZCARD key                             # Count attempts in rolling window
  3. If count >= 5 -> Raise 429 RATE_LIMIT_EXCEEDED
  4. On Failed Login -> ZADD key now now; EXPIRE key 65s
  5. On Successful Login -> DEL key        # Clear failed history
  ```
* **Status Code**: `429 Too Many Requests` returning structured JSON:
  ```json
  {
    "error_code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many failed login attempts. Please try again after 60 seconds.",
    "details": { "max_attempts": 5, "window_seconds": 60 }
  }
  ```

---

## 5. Real-Time WebSocket Room Architecture

* **Endpoint**: `/ws/merchant?token=<JWT_TOKEN>`
* **Authentication**: Token is extracted and verified during the WebSocket handshake. Handshake fails with code `1008 (Policy Violation)` if missing or invalid.
* **Room Isolation**:
  * Connected sockets are partitioned into tenant-specific rooms: `room:merchant_{merchant_id}`.
  * Merchant A's socket never receives events originating from Merchant B.
* **Supported Real-Time Events**:
  * `STOCK_UPDATED`: Emitted upon product creation, manual stock edit, or bulk update.
  * `APPROVAL_CREATED`: Emitted when staff/owner submits a stock adjustment request.
  * `APPROVAL_RESOLVED`: Emitted when an owner approves or rejects a request.
  * `LOW_STOCK_ALERT`: Emitted when stock drops below threshold.
* **Echo-Back Exclusion**: Broadcast messages accept an `exclude_connection_id` parameter to prevent the originating socket from receiving redundant self-notifications.

---

## 6. Atomic Bulk Update Rollback

* **Endpoint**: `POST /products/bulk-update` (Accepts JSON array or CSV multipart upload).
* **Transaction Guarantee**: Updates are wrapped in an atomic database transaction using row-level locking (`with_for_update()`).
* **All-or-Nothing Rollback**: If even 1 item in a batch contains invalid data (e.g., negative stock, negative price, or non-existent SKU), the entire batch rolls back immediately. Zero rows are updated.

---

## 7. Role-Based Access Control (RBAC) Matrix

| Endpoint | Action | Allowed Role | Non-Permitted Response |
| :--- | :--- | :---: | :---: |
| `POST /auth/register` | Create merchant workspace & owner | Public | - |
| `POST /auth/login` | Authenticate and obtain JWT | Public | 429 if rate-limited / 401 if invalid |
| `GET /products` | View catalog | `OWNER`, `STAFF` | 403 on cross-tenant |
| `POST /products` | Create product | `OWNER` | 403 `UNAUTHORIZED_ROLE` |
| `PUT /products/{id}` | Edit product / stock | `OWNER`, `STAFF` | 403 `CROSS_TENANT_ACCESS_DENIED` |
| `POST /products/bulk-update` | Bulk update SKU prices/stock | `OWNER` | 403 `UNAUTHORIZED_ROLE` |
| `POST /approvals` | Request stock adjustment | `OWNER`, `STAFF` | 403 on cross-tenant product |
| `GET /approvals` | View approval requests | `OWNER`, `STAFF` | Scoped to merchant |
| `POST /approvals/{id}/decision` | Approve / Reject stock request | **`OWNER` Only** | **403 `UNAUTHORIZED_ROLE`** |
| `GET /reports/inventory-export` | Stream CSV inventory export | `OWNER`, `STAFF` | Scoped to merchant |

---

## 8. Sample CSV Bulk Test Datasets

### A. Valid Bulk Update (`sample_bulk_valid.csv`)
```csv
sku,unit_price,stock_quantity
ALPHA-001,45.00,120
BULK-1,115.00,45
BULK-2,125.00,55
```

### B. Invalid Batch Demonstrating Atomic Rollback (`sample_bulk_rollback.csv`)
```csv
sku,unit_price,stock_quantity
BULK-1,115.00,45
BULK-2,125.00,55
BULK-3,135.00,65
BULK-4,145.00,-99
BULK-5,155.00,75
```
*Notice: Row 4 contains `-99` stock. Processing this file fails with `INVALID_BULK_PAYLOAD`, and rows 1, 2, 3, and 5 are completely rolled back without modification.*

---

## 9. Quickstart: Running with Docker Compose

Ensure Docker Desktop is running, then run from the project root:

```bash
# 1. Clone & Enter project
cd cleandesk_ai_assesment

# 2. Start all containers (Postgres, Redis, Backend, Frontend)
docker-compose up --build
```

### Service Endpoints
* **Frontend Application**: `http://localhost:5173`
* **FastAPI Backend Swagger Docs**: `http://localhost:8000/docs`
* **FastAPI Health Check**: `http://localhost:8000/health`
* **PostgreSQL Database**: `localhost:5432` (`cleandesk_db`)
* **Redis In-Memory Store**: `localhost:6379`

---

## 10. Local Development Setup (Without Docker)

### Backend
```powershell
# 1. Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r backend/requirements.txt

# 3. Start PostgreSQL and Redis locally, then start Uvicorn
uvicorn app.main:app --reload --port 8000
```

### Frontend
```powershell
cd frontend
npm install
npm run dev
```

---

## 11. Automated Pytest Test Suite

The test suite covers the 5 mandatory scenarios requested by CleanDesk AI:

```powershell
pytest backend/tests -v
```

### Verified Test Scenarios
```text
backend/tests/test_approvals_rbac.py::test_staff_user_blocked_from_approving PASSED      [20%]
backend/tests/test_bulk_rollback.py::test_atomic_bulk_update_rollback PASSED            [40%]
backend/tests/test_cache_aside.py::test_cache_aside_and_explicit_invalidation PASSED     [60%]
backend/tests/test_rate_limiter.py::test_auth_rate_limiting_exceeded PASSED             [80%]
backend/tests/test_tenant_isolation.py::test_tenant_isolation_products_and_approvals PASSED [100%]

================================= 5 passed in 12.04s =================================
```

1. **`test_tenant_isolation.py`**: Verifies that Merchant A cannot view, mutate, or approve Merchant B's products or approval requests (returns HTTP 403 `CROSS_TENANT_ACCESS_DENIED`).
2. **`test_bulk_rollback.py`**: Verifies that when 1 product in a 5-product bulk update has negative values, the transaction is rolled back and zero records are modified.
3. **`test_cache_aside.py`**: Verifies cache misses on initial dashboard reads, cache hits on subsequent reads, and explicit invalidation when an approval decision updates inventory.
4. **`test_rate_limiter.py`**: Verifies that exceeding 5 failed login attempts in 60 seconds triggers HTTP 429 `RATE_LIMIT_EXCEEDED`.
5. **`test_approvals_rbac.py`**: Verifies that a `STAFF` user is forbidden (HTTP 403 `UNAUTHORIZED_ROLE`) from approving their own stock request, while an `OWNER` succeeds.
