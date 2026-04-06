# Supplier Verification AI Engine

**Problem**: *"Why can't businesses verify new suppliers before purchasing?"*

**Our Answer**: A production-grade, async AI backend that verifies any supplier in the background — built to handle 1k–10k concurrent users without breaking a sweat.

---

## The Problem (Why This Exists)

When a business wants to onboard a new supplier, they face a critical trust gap:
- No central registry for supplier credibility.
- Manual verification takes days — by which time a fraud could already have happened.
- Existing solutions are either too expensive, too slow, or not scalable.

**Our solution**: An AI-powered background engine that researches suppliers instantly, assigns a risk score, and stores a full audit trail — all while keeping the API response time under **0.1 seconds** even at 10,000 concurrent users.

---

## Architecture Philosophy: "Infrastructure Strong"

> We are not building something beautiful from the outside but weak from the inside.
> We are building something that works perfectly at scale, even if no one sees it.

### Why NOT a simple script?
A basic script would:
- Process one supplier at a time (single-threaded).
- Block the server for 30–60 seconds per request.
- Crash when 100+ users hit it simultaneously.

### Why this distributed architecture?
```
User Request
     |
     v
+----------------+     +-----------------+     +------------------+
|  FastAPI API   |---->|  Redis (Queue)  |---->|  Celery Workers  |
|  Gateway       |     |  Task Broker    |     |  AI Fleet        |
|  (0.1s resp.)  |     |  + Result Cache |     |  (30-60s work)   |
+----------------+     +-----------------+     +------------------+
                                                        |
                                                        v
                                               +----------------+
                                               | Neon Postgres  |
                                               | (Audit Trail)  |
                                               +----------------+
```

The API **never** does the AI work itself. It drops a "Job Ticket" into Redis and immediately returns a `task_id`. The user can poll for results. This is the only way to handle 10,000 concurrent users.

---

## Tech Stack and Decisions

### Backend: FastAPI (not Flask, not Django)
- **Why FastAPI?**: It is the only Python web framework built from the ground up for `async/await`. At 10k users, every microsecond of blocking matters.
- **Why NOT Flask?**: Flask is synchronous. It processes one request at a time unless you add complex middleware.
- **Why NOT Django?**: Django carries a massive ORM and admin overhead. We do not need it. We need speed.

### Task Queue: Celery + Redis (not RQ, not threading)
- **Why Celery?**: The industry standard for distributed Python task queues. Used by Instagram, Mozilla, and thousands of production systems.
- **Why NOT Python `threading`?**: Threads share memory and are limited by Python's GIL (Global Interpreter Lock). At 10k users, they deadlock.
- **Why NOT RQ (Redis Queue)?**: RQ is simpler but lacks Celery's retry logic, task routing, and monitoring ecosystem.
- **Redis as Broker**: Redis `Lists` act as the "Post Office." The API pushes job tickets; Workers pull them.
- **Redis as Backend**: Once the AI finishes, the results are cached in Redis `Key-Value` store so users can retrieve them in milliseconds.

### Database: Neon Serverless Postgres (not MySQL, not SQLite)
- **Why Postgres?**: The most advanced open-source relational DB. Supports JSON columns, full-text search, and ACID transactions.
- **Why NOT MySQL?**: MySQL lacks native JSON column indexing and has weaker support for complex queries.
- **Why NOT SQLite?**: SQLite is file-based and single-writer. It would become a bottleneck instantly at 100+ concurrent writes.
- **Why Neon (Serverless)?**:
  - Free tier with 0.5GB storage.
  - Scales to zero when idle (saves cost).
  - Pooler URL allows thousands of connections without crashing the DB.
  - Singapore region for lowest latency from India.

### ORM: SQLAlchemy Async (not raw SQL, not Tortoise ORM)
- **Why SQLAlchemy?**: The most mature Python ORM with first-class `asyncio` support via `asyncpg`.
- **Why NOT raw SQL?**: Raw SQL is error-prone and hard to migrate. We use Alembic to version-control schema changes.
- **Why NOT Tortoise ORM?**: Tortoise is newer and less battle-tested. SQLAlchemy has a far richer ecosystem.

### Driver: asyncpg (not psycopg2)
- **Why asyncpg?**: The fastest Python PostgreSQL driver. Built entirely in C, non-blocking, and designed for async contexts.
- **Why NOT psycopg2?**: psycopg2 is synchronous. Using it in an async app creates blocking calls that freeze the entire event loop.

### Configuration: Pydantic Settings (not python-dotenv alone)
- **Why Pydantic?**: It validates your environment variables **before** the app starts. If `GOOGLE_API_KEY` is missing, the app refuses to boot. This is called "Fail Fast" — the most important principle in production infrastructure.
- **Why NOT just `os.getenv()`?**: `os.getenv()` returns `None` silently. Your app would start, serve users, and crash during an AI call hours later in production.

### Migrations: Alembic (not manual SQL, not `create_all()`)
- **Why Alembic?**: Database schema changes are version-controlled, just like your code. If you add a column tomorrow, Alembic generates the SQL automatically.
- **Why NOT `Base.metadata.create_all()`?**: `create_all()` is a one-shot tool. It cannot handle upgrades, rollbacks, or column changes without deleting all your data.
- **Why NOT manual SQL in PgAdmin?**: Manual SQL is not reproducible. Your deployment server will not know what schema to create.
- **The async bridge**: Standard Alembic is synchronous, but our DB driver (`asyncpg`) is async. We solved this using `async_engine_from_config` and `connection.run_sync()`.

### AI: Gemini 2.0 Flash (not GPT-4, not a fine-tuned model)
- **Why Gemini 2.0 Flash?**: Fastest Gemini model with the best cost-to-performance ratio. The Flash series is designed for high-throughput applications.
- **Why NOT GPT-4?**: Higher cost per token, no free tier for production.
- **Why NOT a fine-tuned model?**: Fine-tuned models need labeled training data. Gemini is pre-trained for research and reasoning tasks out of the box.

---

## Project Structure

```
problem-supplier-verification-ai-engine/
|
+-- src/
|   +-- api/
|   |   +-- main.py              # FastAPI Gateway (Entry Point)
|   |
|   +-- workers/
|   |   +-- celery_app.py        # Celery Brain (Worker Configuration)
|   |   +-- tasks.py             # Background Task (AI Orchestration)
|   |
|   +-- services/
|   |   +-- db.py                # Async Neon DB Connection Factory
|   |   +-- redis.py             # Async Redis Caching Layer
|   |
|   +-- models/
|   |   +-- supplier.py          # Supplier Database Schema
|   |
|   +-- config/
|   |   +-- settings.py          # Hardened Pydantic Config Engine
|   |
|   +-- agents/                  # [Next] Gemini AI Research Agent
|
+-- migrations/
|   +-- env.py                   # Async Alembic Bridge to Neon
|   +-- versions/
|       +-- 189da615cfc6_*.py    # Initial Supplier Table Migration
|
+-- tests/                       # [Next] Unit and Load Tests
+-- infra/                       # [Next] Docker and Kubernetes manifests
|
+-- .env                         # Never committed (local secrets)
+-- .env.example                 # Template for team members
+-- .gitignore                   # Protects credentials and cache
+-- alembic.ini                  # Alembic configuration
+-- pyproject.toml               # uv dependency management
```

---

## Current Progress

| Phase | What Was Built | Status |
|-------|---------------|--------|
| 1 | Pydantic Settings — Hardened config, Fail Fast validation | Done |
| 2 | Async DB Service — SQLAlchemy + asyncpg + connection pooling (pool_size=20) | Done |
| 3 | Async Redis Service — Singleton caching layer with decode_responses | Done |
| 4 | Supplier Model — Indexed schema with JSON audit trail and risk score | Done |
| 5 | Alembic Migrations — Async bridge, `suppliers` table live in Neon | Done |
| 6 | FastAPI Gateway — Startup/shutdown lifecycle, `/health` endpoint | Done |
| 7 | Celery Worker Brain — `task_acks_late`, `prefetch_multiplier=1` tuned | Done |
| 8 | Background Task — Upsert logic, async DB write, retry mechanism | Done |
| 9 | POST `/verify` endpoint — Returns `task_id` in 0.1s, dispatches to Celery | Done |
| 10 | Gemini 2.0 Flash AI Agent and Web Search Tools | Next |
| 11 | GET `/status/{task_id}` — Real Redis result polling | Next |
| 12 | Docker Compose — Containerize API, Worker, and Redis | Next |
| 13 | Load Testing — Simulate 1k, 5k, 10k concurrent users | Next |
| 14 | Kubernetes Manifests — Horizontal Pod Autoscaling | Next |

---

## How the Scalability Works

### At 1 User
```
POST /verify -> FastAPI -> Redis Queue -> 1 Celery Worker -> Neon DB
```

### At 10,000 Users
```
10,000 x POST /verify -> FastAPI (async, handles all) -> Redis Queue
                                                              |
                                       +----------------------+
                                       v                      v
                               Celery Worker 1  ...   Celery Worker N
                               (reads from queue)     (reads from queue)
                                       |
                                       v
                               Neon DB (with pooler, handles thousands of connections)
```

- The API never blocks. It writes to Redis and returns immediately.
- Workers scale horizontally. Spin up more Docker containers or Kubernetes pods under load.
- Neon's connection pooler prevents DB connection exhaustion.

---

## Running Locally

### Prerequisites
- Python 3.12+
- `uv` package manager
- Redis running locally or via Docker

### Setup
```bash
# 1. Clone the repo
git clone https://github.com/Edge-Explorer/razorpay-itch-solver
cd problem-supplier-verification-ai-engine

# 2. Install dependencies
uv sync

# 3. Configure environment
cp .env.example .env
# Fill in your GOOGLE_API_KEY, DATABASE_URL, REDIS_URL

# 4. Run database migrations
uv run alembic upgrade head

# 5. Start the API
uv run uvicorn src.api.main:app --reload

# 6. Start the Celery Worker (in a separate terminal)
uv run celery -A src.workers.celery_app.worker_app worker --loglevel=info
```

---

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GOOGLE_API_KEY` | Gemini 2.0 Flash API Key | Yes |
| `DATABASE_URL` | Neon PostgreSQL connection string (with `+asyncpg` prefix) | Yes |
| `REDIS_URL` | Redis connection string | Yes |
| `ENVIRONMENT` | `development` / `staging` / `production` | Optional |
| `LOG_LEVEL` | `INFO` / `DEBUG` / `WARNING` | Optional |

---

## Key Engineering Decisions

### `task_acks_late=True` in Celery
If a Worker crashes mid-task (for example, internet drops during a Gemini API call), the task is not lost. It goes back into the queue and another worker picks it up. Without this setting, you would silently lose verification jobs under failure conditions.

### `worker_prefetch_multiplier=1` in Celery
Each worker only takes one task at a time. Since AI research is memory-heavy (loading Gemini context), this prevents out-of-memory crashes under high load.

### `pool_size=20, max_overflow=10` in SQLAlchemy
We maintain 20 persistent connections to Neon. When burst traffic hits (10k users), up to 10 extra connections are created temporarily. This keeps response times predictable and avoids connection timeout errors.

### `expire_on_commit=False` in AsyncSessionLocal
In async contexts, after a `commit()`, SQLAlchemy normally expires all objects and forces a DB re-read on next access. Since our workers process data asynchronously, this would cause unnecessary round-trips to the database. Disabling it keeps our AI result objects in memory without re-fetching.

---

*Built with an infrastructure-first mindset — scalable from day one.*
