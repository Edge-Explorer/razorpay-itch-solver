# BatchProcure AI Aggregator

**Problem Statement (Razorpay Fix My Itch)**: Small restaurants and food businesses cannot access wholesale ingredient pricing because suppliers impose minimum order quantities (MOQs) that exceed what any single small operator can afford or store. The result is a forced dependency on retail distributors, who charge significantly higher per-unit costs, systematically compressing the margins of every small food business in the country.

---

## The Problem

### The Wholesale Wall

Wholesale pricing in India operates on a hard threshold: a supplier will sell Basmati rice at ₹60 per kilogram, but only if you purchase a minimum of 1,000 kilograms in one transaction. A small restaurant needs 50 kilograms a week. The arithmetic does not work, and the supplier will not negotiate.

The result is that the restaurant is forced to buy through a local retail distributor, who absorbs the 1,000 kilogram purchase, stores it in a physical warehouse, and sells it back to the restaurant at ₹95 per kilogram. The ₹35 gap is not just the distributor's profit margin — it also covers rent, storage losses, spoilage, and the cost of breaking bulk. The small restaurant pays for all of this, every week, on every ingredient.

This is not a pricing problem. It is a coordination problem. If ten restaurants in the same neighbourhood each need 50 kilograms of the same rice, their combined demand is 500 kilograms — halfway to the MOQ already. If twenty of them coordinate, the deal is executable. The wholesale price becomes accessible. The distributor becomes unnecessary.

The reason this coordination does not happen spontaneously is threefold:

**First, the data is fragmented.** Restaurant A writes "Atta." Restaurant B writes "Wheat Flour." Restaurant C writes "Chakki Whole Wheat 25kg." These are the same commodity. A basic system cannot group them. The coordination breaks down at the data layer before it even reaches the financial layer.

**Second, the trust is missing.** If twenty restaurants agree to pool a purchase and three of them cancel at the last minute, the group falls below the MOQ and the deal collapses. The remaining seventeen restaurants are left with nothing. No operator will join a pooled order without a guarantee that the deal will execute even if some participants defect.

**Third, logistics are unclear.** Even if the deal locks at 1,000 kilograms, the wholesaler delivers to a single commercial address. Twenty small restaurants do not share an address. The last-mile problem — who receives the delivery, who stores it, and how each participant gets their allocated portion — is never solved at the agreement stage, which means deals fall apart after they lock.

### Why the Existing "Solution" is the Problem

The retail distributor solves all three of these problems using brute force: they have a physical warehouse, they take the risk, and they handle delivery. But they charge for it by marking up the price. They are structurally incentivised to keep small restaurants small and dependent. Their business model requires the wholesale gap to remain wide.

An aggregation engine replaces the distributor's physical infrastructure with a software layer. It solves the data problem with AI, the trust problem with a financial state machine, and the logistics problem with an automated booking system. The cost of running software is orders of magnitude smaller than the cost of running a warehouse, which means the "platform fee" charged for this coordination can be a fraction of the distributor's markup while still being sustainable.

---

## The Engineering Approach

### What We Decided Not to Do

The obvious first approach would be to build a marketplace: a website where restaurants list what they want, and suppliers list what they have, and the two sides negotiate. This would not solve the problem. It recreates the same friction that already exists. A restaurant owner does not want to spend time browsing a marketplace, comparing prices, and coordinating with strangers. They want to order flour and get back to running their kitchen.

The second obvious approach would be to act as a retailer: buy stock in bulk, warehouse it, and sell it to small operators. This is the distributor model. It requires capital, physical infrastructure, spoilage management, and working capital for unsold inventory. It is not a software problem.

The approach we chose is to build an **aggregation engine**: a backend system that passively collects "intent signals" from restaurants, normalises those signals into canonical product categories using AI, groups them in real time across geographic proximity, and triggers a bulk order to a wholesaler only when the combined demand crosses the MOQ threshold. The restaurants pay for exactly what they ordered, at approximately the wholesale price, plus a small coordination fee.

### The Three Core Engineering Problems

Building this requires solving three distinct technical problems, each of which requires a different discipline:

**Problem 1: Semantic Normalisation.** "Atta," "Wheat Flour," "Maida," and "Chakki Whole Wheat" are four different strings that a basic system would treat as four different products. A group-buy engine that cannot recognise that "Atta" and "Whole Wheat Flour" refer to the same commodity will never be able to aggregate demand effectively. This is an AI problem, not a database problem.

**Problem 2: Concurrent State Management.** When a group-buy pool approaches its MOQ, hundreds of restaurants may attempt to join the pool simultaneously. In a naive implementation, this causes a race condition: the system might accept more orders than the MOQ can accommodate, or transition the pool to "locked" state multiple times, triggering duplicate purchase orders to the supplier. This is a distributed systems problem, not a web development problem.

**Problem 3: Cold-Start Prediction.** When a new geographic area comes online with no historical data, the system cannot tell a restaurant how long it will take for a deal to close. An empty pool with no timeline estimate is not useful. The system needs to make an informed estimate based on the density and type of food businesses in that area, using external data rather than internal history. This is an AI reasoning problem combined with a data sourcing problem.

---

## Architecture

```
Client (WebSocket / HTTP)
         |
         v
+-------------------+     Round-Robin     +-------------------+
|    Nginx Gateway  |-------------------->|  FastAPI Instance |
|   (Load Balancer) |                     |  FastAPI Instance |
|   SSL Termination |                     |  FastAPI Instance |
+-------------------+                     +-------------------+
                                                    |
                    +-----------+------------------+
                    |           |                  |
                    v           v                  v
            +----------+  +----------+    +---------------+
            |  Redis   |  |  Neon    |    |  Celery       |
            | (Pools + |  | Postgres |    |  Worker Fleet |
            |  Locks + |  | (Orders, |    |  (AI Tasks)   |
            |  Pub/Sub)|  |  History)|    +---------------+
            +----------+  +----------+           |
                                        +---------+---------+
                                        |                   |
                                        v                   v
                                  +-----------+    +------------------+
                                  |  Gemini   |    |  Tavily Search   |
                                  | Embedding |    |  (Area Density   |
                                  | + Reasoner|    |   Research)      |
                                  +-----------+    +------------------+
```

The system is divided into three logical tiers that operate independently and communicate through Redis.

**Tier 1 — Gateway**: Nginx sits in front of all FastAPI instances. It handles SSL termination, enforces rate limits, and distributes requests across the API replicas using round-robin load balancing. The API instances themselves are stateless. Nginx also handles WebSocket upgrade headers, forwarding long-lived connections to the appropriate API instance.

**Tier 2 — API Layer**: Multiple FastAPI instances run concurrently. Each instance is stateless — it holds no in-memory data about active pools or ongoing orders. All shared state lives in Redis. This is what makes horizontal scaling possible. When the Nginx load balancer adds a fourth API replica, it does not need to be "introduced" to the others. It simply reads and writes the same Redis keys.

**Tier 3 — Worker Layer**: Celery workers handle all AI work. This includes generating product embeddings, running semantic similarity searches, calling the Tavily API for area research, and reasoning with Gemini. These tasks are slow (2-30 seconds) and cannot run inside a web request without blocking the server. Celery isolates them entirely. A crashed worker does not affect the API layer.

---

## Technology Stack

### FastAPI

FastAPI is the API framework. It was chosen because it is built on Python's `asyncio` event loop and the ASGI (Asynchronous Server Gateway Interface) standard. Every I/O operation in the API layer — reading from Redis, writing to Postgres, sending a WebSocket message — is non-blocking. The event loop is never waiting; it switches to the next request while a database call is in flight.

Flask was not used because it is synchronous. A synchronous framework blocks the thread on every I/O operation. At high concurrency, this means you need one thread per active request, which is expensive and does not scale past a few hundred concurrent users.

Django was not used because its ORM and middleware stack are designed for a different architecture. The overhead of Django's request processing pipeline is unnecessary for a system that is fundamentally a message router between Redis and Celery.

### Uvicorn

Uvicorn is the ASGI server that runs the FastAPI application. It is based on `uvloop` (a high-performance reimplementation of the asyncio event loop using Cython) and `httptools` (a fast HTTP parser based on the Node.js http-parser). The combination makes Uvicorn one of the fastest Python web servers available. In the Docker deployment, Uvicorn runs with `--workers 4` to utilise all available CPU cores, since the GIL is released on I/O and each worker can handle concurrent requests independently.

### WebSockets

WebSockets are used for real-time pool progress updates. When a restaurant joins an aggregation pool, the server upgrades the HTTP connection to a persistent WebSocket. As other restaurants join the same pool, the server pushes updates through that connection: the current quantity, the percentage to MOQ, and a predicted time-to-lock estimate.

The reason REST polling is not used here is latency and server load. If each of 500 restaurants connected to the same pool is polling `GET /pool/status/{id}` every 2 seconds, the server is handling 250 requests per second just to serve status updates. WebSockets convert this from 500 outbound HTTP requests per minute per restaurant to one persistent connection per restaurant, with updates pushed only when the state changes.

Redis Pub/Sub is used as the underlying broadcast mechanism. When a Celery worker or an API instance updates a pool's quantity in Redis, it also publishes a message to a `pool:{pool_id}:updates` channel. The FastAPI WebSocket handler is subscribed to that channel and immediately pushes the update to the connected client. This decouples the update producers (workers and API instances) from the update consumers (WebSocket connections).

### Nginx

Nginx is the reverse proxy and load balancer. It sits in front of the FastAPI instances and serves two functions.

First, it handles SSL termination. HTTPS connections are decrypted at the Nginx layer, and plain HTTP is forwarded to the API instances. This keeps the API instances simple — they speak only HTTP — while the public endpoint is secure.

Second, it distributes incoming requests across the available API instances using round-robin load balancing. The `upstream` block in the Nginx configuration defines the pool of API addresses. Nginx tracks the health of each upstream server and automatically stops sending traffic to any instance that stops responding.

Nginx also handles the `Upgrade` header forwarding required for WebSocket connections. Without this configuration, the WebSocket handshake fails because the load balancer strips the upgrade headers before forwarding the request.

### Redis

Redis serves three distinct roles in this system.

**Active Pool State**: The live aggregation pools are stored entirely in Redis as hash structures. The key `pool:{product_canonical_id}:{zip_code}` holds the current quantity, the list of participant IDs, the pool status, and the lock expiry. Redis is used here instead of Postgres because Redis operations are in-memory and take microseconds. The aggregation increment (`HINCRBY`) is atomic, which means it is safe to call from multiple API instances simultaneously without a separate locking mechanism for the increment itself.

**Distributed Locking (Redlock)**: When a pool's quantity crosses the MOQ threshold, a state transition must occur: the pool moves from `AGGREGATING` to `LOCKED`, and a Celery task is dispatched to place the wholesale order. This transition must happen exactly once. If two API instances detect the threshold breach simultaneously, both might attempt the transition, resulting in two wholesale orders being placed for the same pool.

Redlock is the algorithm used to prevent this. Before transitioning a pool's state, an API instance attempts to acquire a distributed lock using three independent Redis key operations. The lock is only considered acquired if the majority of the operations succeed within a timeout. If another instance has already acquired the lock (and performed the transition), the attempt fails and the second instance does nothing. This guarantees exactly-once state transitions even under concurrent load.

**Pub/Sub for WebSocket Broadcasts**: As described in the WebSocket section, Redis Pub/Sub channels are the broadcast bus for real-time updates. This allows any API instance to receive pool state changes published by any other instance or worker, and forward them to the correct WebSocket connections.

### Celery

Celery is the distributed task queue. It manages all AI work and any operation that takes longer than a few hundred milliseconds.

The two most important Celery configuration decisions are `task_acks_late=True` and `worker_prefetch_multiplier=1`. With `task_acks_late`, a task is not removed from the Redis queue until the worker sends an acknowledgment after successful completion. If a worker crashes mid-execution — for example, during a Gemini API call that takes 15 seconds — the task is returned to the queue and picked up by another worker. Without this, the task is deleted from the queue the moment a worker picks it up, so a crash means the task is silently lost.

With `worker_prefetch_multiplier=1`, each worker requests exactly one task at a time. AI inference tasks consume significant memory. Allowing a worker to hold multiple tasks simultaneously risks memory exhaustion under high load.

### Neon Serverless PostgreSQL

Postgres is the persistent store. It holds the canonical product catalog, the historical order record, the restaurant profiles, and the settled ledger of completed group buys.

The specific deployment is Neon: a serverless Postgres service that provides a built-in connection pooler. Standard Postgres has a hard limit on the number of simultaneous connections (typically 100-200 on a small instance). At high concurrency, a naive application that opens one connection per request will exhaust this limit immediately. Neon's pooler sits between the application and the database, multiplexing thousands of application connections onto a small number of real database connections.

SQLite was not used because it is single-writer. Multiple Celery workers writing simultaneously would cause lock contention that makes the system effectively single-threaded for writes.

### SQLAlchemy with asyncpg

SQLAlchemy is the ORM and query builder. The async variant is used with the `asyncpg` driver. `asyncpg` is the only Python PostgreSQL driver that is fully asynchronous at the protocol level — it does not use threads to simulate async behaviour. This is important because the FastAPI event loop must never block, and a synchronous database driver would block the loop on every query.

`expire_on_commit=False` is set on the session factory. In standard SQLAlchemy, after a commit, all ORM objects are expired and re-fetched on next access. In an async context, this silent re-fetch triggers a new database round-trip that can fail if the session has already been closed. Disabling expiry on commit keeps the objects in memory and avoids this class of bugs.

### Alembic

Alembic manages database schema migrations. Every change to the database schema — adding a column, creating an index, renaming a table — is encoded as a migration file with an `upgrade()` and a `downgrade()` function. Migrations are applied in sequence and tracked in the database itself. This means the schema can be reproduced exactly on any environment, and any change can be rolled back deterministically.

The standard Alembic runner is synchronous. Because the asyncpg driver does not support synchronous operations, the Alembic `env.py` is configured to run migrations inside an explicit asyncio event loop using `connection.run_sync(do_run_migrations)`.

### Gemini 2.0 Flash

Gemini 2.0 Flash is used for two tasks: generating text embeddings for semantic product normalisation, and reasoning about area density for cold-start prediction.

For embedding generation, the Gemini API converts a raw product description ("Sona Masuri Raw Rice 25kg") into a high-dimensional vector that encodes its semantic meaning. Similar products produce vectors that are close together in the embedding space, which allows the system to perform nearest-neighbour search across the product catalog to find the canonical category.

For cold-start prediction, the system constructs a prompt that includes the Tavily search results about a ZIP code (number of restaurants found, types of cuisine, density of food businesses) and asks Gemini to reason about the expected aggregation speed. Gemini is not making a "prediction" in a machine learning sense — it is applying general reasoning to structured evidence. The output is a confidence-annotated estimate of how long a pool in that area is likely to take to fill.

The `google-genai` SDK is used rather than the deprecated `google-generativeai` package.

### Tavily Search API

Tavily is used for the cold-start area research. When a new ZIP code appears in the system for the first time, a Celery task calls the Tavily API with a structured query: "restaurants and food businesses in [zip code area name] India." Tavily returns structured results including titles, URLs, and content snippets, without requiring any scraping infrastructure.

The results are passed to Gemini, which counts the density of food businesses and classifies the area (high-density commercial, residential, mixed) to produce the aggregation speed estimate.

### pgvector

pgvector is a Postgres extension that adds a native vector column type and approximate nearest-neighbour search operators. When a restaurant submits a product name, the system generates its embedding via Gemini and runs a cosine similarity search against the `products` table using pgvector. The result is the closest canonical product in the catalog.

This keeps the semantic search inside the database, avoiding a separate vector store service. For the scale of this system (thousands of canonical products, not billions), pgvector's HNSW (Hierarchical Navigable Small World) index provides sub-millisecond search times.

### Pydantic Settings

All environment variables are declared as typed fields in a `Settings` class derived from Pydantic's `BaseSettings`. When the application starts, Pydantic reads the `.env` file, validates every field against its declared type, and raises a descriptive error if any required variable is missing or malformed. The application refuses to start.

Using `os.getenv()` directly returns `None` silently for missing variables. The application starts successfully, serves traffic, and then crashes inside a Gemini API call three hours later in a deployed environment with no clear error message pointing to the missing key. Fail-fast environment validation prevents this class of operational incident.

### Docker Compose

Docker Compose orchestrates the local simulation of the full infrastructure. The `docker-compose.yml` defines five services: Nginx, three FastAPI API instances, the Celery worker, and Redis.

The three API instances share a Docker network and are referenced by name in the Nginx upstream configuration. `docker-compose up --scale api=3` brings up the full load-balanced stack with a single command.

The Dockerfile uses a two-stage build. The first stage installs all dependencies into a virtual environment using `uv`. The second stage copies only the virtual environment and the application source into a clean `python:3.12-slim` base image, discarding build tools and cache files. This keeps the final image small and free of unnecessary binaries.

---

## The Adapter Pattern for External Services

The logistics component (booking a Porter pickup from the wholesaler to the host restaurant) and the payment component (capturing a payment from a restaurant's wallet) are implemented behind abstract base class interfaces. The `LogisticsProvider` ABC defines the contract: `get_quote(origin, destination, weight)` and `book_pickup(quote_id)`. The `PaymentProvider` ABC defines `capture(amount, restaurant_id)` and `refund(transaction_id, reason)`.

The implementations used in this project are high-fidelity mocks. The `PorterMockProvider` returns a realistic quote object with a fake tracking ID, a randomised price estimate within market range, and a simulated pickup window. The `WalletMockProvider` simulates a payment capture and returns a transaction record.

This architecture means the system demonstrates the complete order lifecycle — intent, aggregation, lock, logistics booking, payment capture — without incurring API costs during development. Swapping in the real Porter or Razorpay implementation requires changing one line in the dependency injection setup, because the interface contract is identical.

---

## The Order State Machine

Each aggregation pool moves through a strict set of states. No state transition is permitted outside of the defined sequence.

| State | Meaning |
|---|---|
| `OPEN` | Pool is accepting intents. No money is held. |
| `SOFT_LOCK` | Pool has reached 90% of MOQ. System pings nearby restaurants with "urgent join" signals. |
| `HARD_LOCK` | MOQ reached. Redlock acquired. No new intents accepted. Payments are captured. |
| `ORDER_PLACED` | Celery worker has submitted the bulk order to the wholesaler. |
| `LOGISTICS_BOOKED` | Porter pickup has been confirmed. |
| `ARRIVED` | Host restaurant has confirmed the delivery. |
| `DISBURSED` | All participants have scanned their QR codes and received their portion. |
| `FAILED` | An unrecoverable error occurred. All captured payments are refunded automatically. |

The `FAILED` state triggers a compensation workflow: the Celery task iterates through every participant's transaction record and issues a refund through the `PaymentProvider`. This is a simplified implementation of the Saga pattern — a sequence of local transactions with compensating actions for rollback — applied to the distributed nature of the payment captures.

---

## Project Structure

```
problem-wholesale-aggregator-ai-engine/
|
+-- src/
|   +-- api/
|   |   +-- main.py              # FastAPI application, lifecycle hooks, WebSocket manager
|   |   +-- router.py            # Route definitions: POST /intent, GET /pool, WS /pool/stream
|   |
|   +-- workers/
|   |   +-- celery_app.py        # Celery application, broker/backend config, task routing
|   |   +-- tasks.py             # Background tasks: normalise, predict, place_order, disburse
|   |
|   +-- services/
|   |   +-- db.py                # Async SQLAlchemy engine, session factory, connection pool
|   |   +-- redis.py             # Async Redis client singleton, Pub/Sub helpers
|   |   +-- embeddings.py        # Gemini embedding generation, pgvector similarity search
|   |
|   +-- models/
|   |   +-- base.py              # SQLAlchemy declarative base, TimestampMixin
|   |   +-- orders.py            # OrderPool, Intent models, PoolStatus state enum
|   |   +-- suppliers.py         # Supplier, Product, CatalogEntry models
|   |   +-- disputes.py          # Dispute model, DisputeStatus, DisputeSeverity enums
|   |
|   +-- agents/
|   |   +-- normalizer.py        # Gemini agent for semantic product matching
|   |   +-- predictor.py         # Gemini agent for cold-start area density prediction
|   |   +-- tools.py             # Tavily search tool, async httpx implementation
|   |   +-- qa_analyzer.py       # QA AI Agent: three-way dispute triage (Buyer/Supplier/Logistics)
|   |
|   +-- config/
|   |   +-- settings.py          # Pydantic Settings, fail-fast environment validation
|   |
|   +-- utils/
|       +-- concurrency.py       # Redlock implementation, distributed lock helpers
|       +-- adapters.py          # LogisticsProvider ABC, PaymentProvider ABC, Mock implementations
|
+-- infra/
|   +-- docker/
|   |   +-- Dockerfile           # Two-stage build: uv dependency install, slim runtime image
|   |   +-- docker-compose.yml   # Nginx + 3x API + Worker + Redis orchestration
|   |   +-- nginx.conf           # Round-robin upstream, WebSocket upgrade headers, SSL termination
|
+-- migrations/
|   +-- env.py                   # Async Alembic bridge via run_sync
|   +-- versions/                # Versioned migration files
|
+-- data/
|   +-- reports/                 # Per-pool JSON settlement records (gitignored)
|
+-- tests/
|   +-- test_concurrency.py      # Simulates 100 concurrent MOQ-breach attempts, verifies Redlock
|   +-- test_normalizer.py       # Verifies "Atta" and "Wheat Flour" resolve to same canonical ID
|
+-- .env.example
+-- .gitignore
+-- alembic.ini
+-- pyproject.toml
+-- README.md
```

---

## Running Locally

### Prerequisites

- Python 3.12 or higher
- `uv` package manager
- Docker Desktop (for the Redis and Nginx services)
- A Gemini API key, a Tavily API key, and a Neon PostgreSQL connection string

### Setup

```bash
git clone https://github.com/Edge-Explorer/razorpay-itch-solver
cd problem-wholesale-aggregator-ai-engine

uv sync
cp .env.example .env
# Edit .env with your API keys

uv run alembic upgrade head
```

### Running the Full Stack

```bash
docker-compose -f infra/docker/docker-compose.yml up --build --scale api=3
```

This brings up Nginx on port 80 with three FastAPI replicas behind it, the Celery worker, and Redis.

### Running in Development (without Docker)

```bash
# Terminal 1 — Redis
docker run -d -p 6379:6379 redis:7-alpine

# Terminal 2 — API
uv run uvicorn src.api.main:app --reload

# Terminal 3 — Celery Worker
uv run celery -A src.workers.celery_app.worker_app worker --loglevel=info -P solo
```

---

## Environment Variables

| Variable | Description | Required |
|---|---|---|
| `GEMINI_API_KEY` | Gemini 2.0 Flash API key | Yes |
| `TAVILY_API_KEY` | Tavily search API key | Yes |
| `DATABASE_URL` | Neon Postgres connection string with `+asyncpg` dialect prefix | Yes |
| `REDIS_URL` | Redis connection string | Yes |
| `CELERY_BROKER_URL` | Celery broker URL (defaults to Redis) | No |
| `CELERY_RESULT_BACKEND` | Celery result backend URL (defaults to Redis) | No |

---

## Implementation Status

| Phase | Component | Status |
|---|---|---|
| 1 | Pydantic Settings — fail-fast environment validation | Complete |
| 2 | Async DB Service — SQLAlchemy, asyncpg, connection pooling | Complete |
| 3 | Async Redis Service — singleton, atomic float increment, Pub/Sub helpers | Complete |
| 4 | Product, Order, and Dispute Models | Complete |
| 5 | Alembic Migrations — async bridge, schema on Neon | Planned |
| 6 | Gemini Embedding Service + pgvector similarity search | Complete |
| 7 | Semantic Normaliser Agent | Complete |
| 8 | Cold-Start Predictor Agent | Complete |
| 9 | Celery Worker Configuration — late acks, prefetch control | Complete |
| 10 | Background Tasks — pool dispatch, payment capture, logistics booking | Complete |
| 11 | Redlock Distributed Locking — wired into intent submission endpoint | Complete |
| 12 | FastAPI Routes — POST /intents, POST /disputes | Complete |
| 13 | Dispute QA System — AI three-way triage, automated refund events | Complete |
| 14 | WebSocket broadcast via Redis Pub/Sub | Planned |
| 15 | Order State Machine — OPEN → SOFT_LOCK → FULFILLED | Complete |
| 16 | Adapter Layer — LogisticsProvider ABC, PaymentProvider ABC, Mock implementations | Complete |
| 17 | Nginx Config — round-robin, WebSocket headers, health checks | Planned |
| 18 | Docker Compose — multi-replica stack | Planned |
| 19 | Mock Unit Test Suite — Normalizer and QA Agent | Complete |
| 20 | Concurrency Load Tests — Redlock under concurrent MOQ breach | Planned |

---

## Quality Assurance & Dispute Resolution System

This system implements a **Three-Way Liability Arbitration** model to handle product quality disputes after delivery. This solves the "last-mile contamination" problem, where a supplier ships clean goods but the transporter damages them in transit, causing an unfair penalty to the supplier's trust rating.

### The Chain of Custody

Every delivery has three evidence checkpoints:

1. **Pickup Handshake (Supplier → Transporter)**: The driver photographs the goods at the warehouse. The supplier signs off. Liability shifts to the transporter.
2. **Dropoff Handshake (Transporter → Restaurant)**: The restaurant inspects and photographs the goods upon arrival. If damage is visible, the transporter is flagged before the restaurant accepts.
3. **Post-Delivery Dispute (Restaurant)**: If internal spoilage (mold, contamination) is found after opening the bags, the restaurant files a dispute with a description and photo evidence.

### The AI Triage Logic

When a dispute is filed at `POST /api/v1/disputes`, the **QA AI Agent** (`src/agents/qa_analyzer.py`) receives all three evidence notes and classifies the liability:

| Scenario | Classification | Outcome |
|---|---|---|
| Goods sealed at pickup, damaged at dropoff | `LOGISTICS_FAULT` | Full refund to restaurant, supplier trust unchanged |
| Packaging intact but product internally spoiled | `RESOLVED_IN_FAVOR_OF_BUYER` | Refund issued, supplier trust rating decays |
| Restaurant claims damage, both notes verify perfect delivery | `RESOLVED_IN_FAVOR_OF_SUPPLIER` | No refund, buyer trust rating flagged |

### Supplier Trust Recovery

A supplier's trust score decays on verified faults but recovers automatically:
- Each successfully fulfilled pool with zero disputes increments the trust score by `+0.02`.
- A manual audit submission (new quality certificate, warehouse photos) allows platform admins to restore a suspended supplier to probation status (`0.80`).

---

*Each decision in this system — from choosing asyncpg over psycopg2 to using Redlock for state transitions to implementing the adapter pattern for logistics — was made to solve a specific, named problem. The technology follows the architecture, and the architecture follows the problem.*
