# Stash — Working Memory for AI Developers and Agents

> Zero-Config Storage · Local-First · Ephemeral by Design

## What is Stash?

**Stash** is a fast, lightweight, ephemeral key-value store designed for AI developers and agents. It functions as "working memory" for your workflows—a place to park intermediate data, task states, or context blocks without the overhead of a persistent database.

**The Golden Rule:** This is a "Trash-First" database. If data isn't retrieved or extended within the TTL (Time-To-Live), it vanishes forever. That's not a bug—it's the point.

---

## Why Stash?

| Problem | Stash Solution |
| :--- | :--- |
| Need somewhere to park intermediate results | TTL-based storage that auto-cleans |
| Don't want to spin up infrastructure just to prototype | Zero-config local mode (no Docker required) |
| Worried about data leaking between users/agents | Namespace isolation by API key |
| Need to scale later without rewriting code | Same API from laptop to cloud |

---

## Quick Start

### Local Mode (Zero Dependencies)

```bash
pip install stash-memory

# Start the server
stash serve
```

That's it. No Docker. No Redis. Just works.

```python
# Or embed directly in your Python app
from stash_memory import Stash

stash = Stash()  # Uses SQLite, runs in-process
stash.set("my-key", {"task": "summarize", "progress": 0.5}, ttl=3600)
data = stash.get("my-key")
```

### Server Mode (Multi-Process/Multi-Agent)

```bash
# With Redis backend for production workloads
stash serve --backend redis --redis-url redis://localhost:6379
```

### Docker Mode (Team/Staging)

```bash
docker run -p 8000:8000 stashmemory/stash
```

### Hosted Mode (Production)

```bash
# Just an API key—we handle the infrastructure
curl -X POST https://api.stash.memory/stash \
  -H "X-API-KEY: sk_live_..." \
  -d '{"data": {"task": "summarize"}, "ttl": 3600}'
```

---

## The Stash Journey: Local to Cloud

Stash is designed to grow with you. Start local, scale when ready.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         YOUR STASH JOURNEY                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐          │
│  │ EMBEDDED │ -> │  LOCAL   │ -> │  DOCKER  │ -> │  HOSTED  │          │
│  │          │    │  SERVER  │    │          │    │          │          │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘          │
│                                                                         │
│  pip install    stash serve     docker-compose   api.stash.memory      │
│  + import                       up                                      │
│                                                                         │
│  Best for:      Best for:       Best for:        Best for:             │
│  - Prototyping  - Local dev     - Teams          - Production          │
│  - Single agent - Multi-agent   - CI/CD          - Scale               │
│  - Tutorials    - Testing       - Staging        - No ops              │
│                                                                         │
│  Zero config    Zero config     Redis included   Fully managed         │
│  SQLite backend SQLite/Redis    Persistent opts  SLA guaranteed        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**The same code works everywhere:**

```python
from stash_memory import Stash

# Local development (auto-detects best backend)
stash = Stash()

# Explicit local SQLite
stash = Stash(backend="sqlite")

# Local Redis
stash = Stash(backend="redis", redis_url="redis://localhost:6379")

# Hosted (just add API key)
stash = Stash(api_key="sk_live_...")
```

---

## API Reference

### `POST /stash`
Store a JSON block with automatic expiration.

**Request:**
```bash
curl -X POST http://localhost:8000/stash \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: your_key" \
  -d '{
    "data": {"task": "summarize", "context": "..."},
    "ttl": 3600
  }'
```

**Response:**
```json
{
  "memory_id": "xK9mP2nQ",
  "ttl": 3600,
  "expires_at": "2024-01-15T11:30:00Z"
}
```

### `GET /recall/{memory_id}`
Retrieve stored data.

**Response:**
```json
{
  "memory_id": "xK9mP2nQ",
  "data": {"task": "summarize", "context": "..."},
  "ttl_remaining": 3245
}
```

### `PATCH /update/{memory_id}`
Update stored data, extend TTL, or both.

**Replace entire data:**
```bash
curl -X PATCH http://localhost:8000/update/xK9mP2nQ \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: your_key" \
  -d '{"data": {"task": "summarize", "progress": 0.75}}'
```

**Extend TTL only:**
```bash
curl -X PATCH http://localhost:8000/update/xK9mP2nQ \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: your_key" \
  -d '{"extra_seconds": 1800}'
```

**Update data AND extend TTL:**
```bash
curl -X PATCH http://localhost:8000/update/xK9mP2nQ \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: your_key" \
  -d '{"data": {"task": "summarize", "progress": 1.0}, "extra_seconds": 3600}'
```

**Response:**
```json
{
  "memory_id": "xK9mP2nQ",
  "ttl_remaining": 5045,
  "expires_at": "2024-01-15T12:30:00Z"
}
```

**Rules:**
- Must provide at least one of: `data` or `extra_seconds`
- `data` can be any valid JSON (string, number, object, array, etc.)

**Typical workflow for modifying existing data:**
```python
# Fetch current data
current = requests.get(f"/recall/{memory_id}").json()["data"]

# Modify locally
current["new_field"] = "new value"

# Save back
requests.patch(f"/update/{memory_id}", json={"data": current})
```

### `DELETE /forget/{memory_id}`
Immediately delete a memory (don't wait for TTL).

---

## Architecture

### Namespace Isolation (Multi-Tenancy)

Every request requires an `X-API-KEY`. The backend maps keys to users, and all storage keys are prefixed:

```
user:{user_id}:{memory_id}
```

Even if someone guesses a `memory_id`, they can't access it without the matching API key.

### Storage Backends

| Backend | Best For | Persistence | Config Required |
| :--- | :--- | :--- | :--- |
| **Memory** | Testing, embedding | None (process lifetime) | None |
| **SQLite** | Local dev, single-node | File-based | None |
| **Redis** | Production, multi-node | Configurable | Redis URL |

### Tiered Limits (Hosted)

| Feature | Free | Pro | Enterprise |
| :--- | :--- | :--- | :--- |
| **Storage Limit** | 1MB per stash | 50MB per stash | 500MB per stash |
| **Default TTL** | 1 Hour | 24 Hours | Customizable |
| **Max TTL** | 1 Hour | 24 Hours | 7 Days |
| **Rate Limit** | 60/min | 300/min | Unlimited |
| **Persistence** | None | RDB Snapshots | AOF + Replication |

---

## Configuration

Stash uses environment variables for configuration:

```bash
# Backend selection
STASH_BACKEND=sqlite          # memory, sqlite, redis

# Redis settings (when using redis backend)
REDIS_URL=redis://localhost:6379

# Server settings
STASH_HOST=0.0.0.0
STASH_PORT=8000

# Limits
STASH_DEFAULT_TTL=3600        # 1 hour
STASH_MAX_TTL=86400           # 24 hours  
STASH_MAX_PAYLOAD_BYTES=1048576  # 1MB

# Logging
STASH_LOG_LEVEL=INFO
STASH_LOG_FORMAT=json         # json or console

# Hosted mode
STASH_API_KEY=sk_live_...     # Enables hosted backend
```

Or use a `.env` file in your project root.

---

## Design Considerations

### ID Generation & Collision Handling

The 8-character `memory_id` provides ~2.8 trillion possibilities (base62). The implementation uses retry logic for the rare collision case, falling back to UUID if collisions persist.

### Dual-Layer Size Validation

1. **Pre-read gate:** Check `Content-Length` header (fast rejection)
2. **Post-parse validation:** Verify actual payload size after JSON parsing

### Rate Limiting

Per-API-key rate limits prevent runaway agents from overwhelming the service:

| Tier | Requests/Minute | Burst Limit |
| :--- | :--- | :--- |
| Free | 60 | 10 |
| Pro | 300 | 50 |
| Enterprise | Customizable | Customizable |

### Structured Logging

All operations emit structured JSON logs for observability:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "event": "stash_created",
  "user_id": "usr_abc123",
  "memory_id": "xK9mP2nQ",
  "ttl_seconds": 3600,
  "payload_bytes": 2048
}
```

---

## Competitive Landscape

### Where Stash Fits

Stash occupies a specific niche: **ephemeral working memory**. The broader AI memory space includes:

| Product | Focus | Persistence | Self-Hostable |
| :--- | :--- | :--- | :--- |
| **Stash** | Ephemeral scratchpad | TTL-based eviction | Yes (local-first) |
| **Mem0** | Long-term personalization | Permanent | Limited |
| **Zep** | Temporal knowledge graphs | Permanent | Yes (Community) |
| **Letta** | Stateful agents | Archival + recall | Yes |

**Key insight:** Mem0/Zep/Letta solve "what does the agent remember about this user?" Stash solves "where do I park intermediate results during a task?" These are complementary—use both.

### Infrastructure Alternatives

If you want to swap the underlying store:

| Store | Local-Friendly | Zero-Config | Notes |
| :--- | :--- | :--- | :--- |
| **SQLite** | ✓ | ✓ | Stash default for local |
| **Redis** | Needs Docker | ✗ | Stash default for production |
| **Valkey** | Needs Docker | ✗ | Open-source Redis fork |
| **DuckDB** | ✓ | ✓ | Good for analytics |

---

## Development

### Run Locally

```bash
# Clone and setup
git clone https://github.com/yourusername/stash.git
cd stash
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

# Run server
stash serve --reload

# Run tests
pytest tests/ -v
```

### Project Structure

```
stash/
├── src/
│   └── stash_memory/
│       ├── __init__.py
│       ├── main.py           # FastAPI app
│       ├── cli.py            # CLI commands
│       ├── client.py         # Python client
│       ├── api/              # Route handlers
│       ├── core/             # Config, auth, middleware
│       ├── models/           # Pydantic schemas
│       └── backends/         # Storage implementations
│           ├── base.py       # Abstract interface
│           ├── memory.py     # In-memory (testing)
│           ├── sqlite.py     # SQLite (local)
│           └── redis.py      # Redis (production)
├── tests/
├── docker-compose.yml
├── Dockerfile
└── pyproject.toml
```

### Test Cases

| Test | Purpose |
| :--- | :--- |
| **The Wall Test** | User A cannot access User B's data |
| **The Expiry Test** | Data disappears after TTL |
| **The Bloat Test** | Oversized payloads rejected (413) |
| **The Liar Test** | Mismatched Content-Length rejected |
| **The Flood Test** | Rate limits enforced (429) |
| **The Update Test** | Data replacement works correctly |
| **The Extend Test** | TTL extension works correctly |

---

## Docker

### Quick Start

```bash
docker run -p 8000:8000 stashmemory/stash
```

### Docker Compose (with Redis)

```yaml
version: "3.8"

services:
  stash:
    image: stashmemory/stash
    ports:
      - "8000:8000"
    environment:
      - STASH_BACKEND=redis
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis

  redis:
    image: redis:alpine
    volumes:
      - redis_data:/data

volumes:
  redis_data:
```

```bash
docker compose up
```

---

## Roadmap

- [x] Core API (stash, recall, update)
- [x] Redis backend
- [x] API key authentication
- [x] Tiered limits
- [ ] SQLite backend with TTL
- [ ] Python client library
- [ ] CLI (`stash serve`, `stash get`, `stash set`)
- [ ] Single binary distribution
- [ ] Hosted service
- [ ] Dashboard UI

---

## License

MIT

---

## Contributing

Contributions welcome! Please read our contributing guidelines and submit PRs to the `main` branch.
