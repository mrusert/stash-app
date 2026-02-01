# FlashMemory — Ephemeral Agent RAM

## 1. Project Vision
**FlashMemory** is a high-speed, zero-config, ephemeral key-value store designed for AI agents. It functions as "Short-Term RAM" for agentic workflows, allowing agents to stash intermediate data, task states, or large context blocks without the overhead of a persistent database.

**The Golden Rule:** This is a "Trash-First" database. If data isn't retrieved or extended within the TTL (Time-To-Live), it vanishes forever.

---

## 2. Tech Stack & Infrastructure
* **Backend:** FastAPI (Python 3.11+)
* **Primary Store:** Redis (In-memory, native TTL support)
* **Schema/Validation:** Pydantic v2
* **Containerization:** Docker & Docker Compose
* **Environment:** Redis-py for async connection handling

---

## 3. Architecture & Security Decisions

### Isolated Namespaces (Multi-tenancy)
To prevent data leakage, the service implements **Namespace Isolation**. 
* Every request must include an `X-API-KEY`.
* The backend maps the API Key to a `user_id`.
* All Redis keys are stored with a prefix: `user:{user_id}:{memory_id}`.
* **Pro:** Even if a `memory_id` is guessed, it cannot be accessed without the matching API Key.

### Tiered Feature Logic
The service is designed to support three tiers of service:

| Feature | Free Tier | Pro Tier | Enterprise Tier |
| :--- | :--- | :--- | :--- |
| **Storage Limit** | 1MB per stash | 50MB per stash | 500MB per stash |
| **Default TTL** | 1 Hour | 24 Hours | Customizable |
| **Persistence** | None (RAM only) | RDB Snapshots | AOF (Append Only) |
| **Redundancy** | None | Basic | High (Replicated) |

---

## 4. API Specification

### `POST /stash`
**Purpose:** Save a JSON block.
* **Header:** `X-API-KEY: <your_key>`
* **Input Body:**
    ```json
    {
      "data": { "any": "valid_json" },
      "ttl": 3600
    }
    ```
* **Logic:** 
    1. Validate JSON size against user tier limit.
    2. Generate unique 8-char `memory_id`.
    3. Save to Redis with key `user:{id}:{mem_id}` and `EXPIRE` set to `ttl`.

### `GET /recall/{memory_id}`
**Purpose:** Retrieve a stored block.
* **Logic:** Authenticate user -> Check Redis for `user:{id}:{memory_id}` -> Return 404 if not found or expired.

### `PATCH /extend/{memory_id}`
**Purpose:** Add time to an existing memory.
* **Input:** `{ "extra_seconds": 1800 }`

---

## 5. Additional Design Considerations

### ID Generation & Collision Handling
The 8-character `memory_id` provides approximately 2.8 trillion possibilities (base62), which is sufficient for ephemeral data. However, the implementation should handle the rare collision case:
* **Option A:** Check-before-write pattern with retry logic
* **Option B:** Use UUIDs internally, expose shortened IDs externally
* **Recommendation:** Implement a simple retry loop (max 3 attempts) when generating IDs, falling back to UUID if collisions persist.

### Dual-Layer Size Validation
Relying solely on `Content-Length` headers is insufficient since clients can provide incorrect values. Implement two validation layers:
1. **Pre-read gate:** Check `Content-Length` header against tier limit (fast rejection)
2. **Post-deserialization validation:** Verify actual payload size after JSON parsing before writing to Redis

```python
# Example middleware pattern
if content_length > tier_limit:
    raise HTTPException(413, "Payload Too Large")
    
payload = await request.json()
actual_size = len(json.dumps(payload).encode('utf-8'))
if actual_size > tier_limit:
    raise HTTPException(413, "Payload Too Large")
```

### Rate Limiting
AI agents can loop aggressively, making rate limiting essential for cost control and noisy-neighbor prevention. Implement per-API-key rate limits:

| Tier | Requests/Minute | Burst Limit |
| :--- | :--- | :--- |
| Free | 60 | 10 |
| Pro | 300 | 50 |
| Enterprise | Customizable | Customizable |

**Implementation options:**
* Redis-based sliding window counter (recommended for consistency)
* FastAPI middleware with `slowapi` library
* Token bucket algorithm for burst handling

### Logging Strategy
Structured logging is critical for debugging ephemeral systems where data disappears by design. Implement comprehensive logging across all operations.

**Log Levels & Events:**

| Level | Events |
| :--- | :--- |
| **INFO** | Stash created, Recall successful, TTL extended, User authenticated |
| **WARNING** | Rate limit approached (80% threshold), Large payload received, TTL extension on near-expiry key |
| **ERROR** | Authentication failed, Redis connection error, Rate limit exceeded, Size validation failed |
| **DEBUG** | Full request/response payloads, Redis command timing, ID generation attempts |

**Structured Log Format (JSON):**
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "event": "stash_created",
  "user_id": "usr_abc123",
  "memory_id": "xK9mP2nQ",
  "ttl_seconds": 3600,
  "payload_bytes": 2048,
  "tier": "pro",
  "request_id": "req_xyz789"
}
```

**Implementation recommendations:**
* Use `structlog` or `python-json-logger` for structured JSON output
* Generate a unique `request_id` per request via middleware for tracing
* Log Redis operation latency for performance monitoring
* Mask or omit sensitive payload contents in production logs
* Configure log rotation and retention policies (7 days recommended for ephemeral service)

**Key metrics to track:**
* Stash/recall operations per minute (by tier)
* Average payload size (by tier)
* TTL distribution histogram
* Cache hit/miss ratio for recalls
* P95/P99 Redis latency

### Deployment Modes (Local vs. Remote)
FlashMemory is designed to run identically in local development and production environments, catering to the growing "local-first" AI movement (Ollama, LM Studio, privacy-conscious tooling).

**Why this matters:**
* Vibe coders running local LLMs want their entire stack offline
* "Ephemeral by design" + "local deployment" = strong privacy story
* Developers start local for experimentation, graduate to hosted for scale
* Zero friction between environments accelerates adoption

**Configuration-driven deployment:**
```bash
# Environment variables control behavior
FLASHMEMORY_MODE=local|dev|production
REDIS_URL=redis://localhost:6379  # or remote endpoint
PERSISTENCE_MODE=none|rdb|aof
RATE_LIMIT_ENABLED=true|false
```

**Local Mode (Laptop-friendly):**
| Setting | Value |
| :--- | :--- |
| Default TTL | 15 minutes |
| Max payload | 512KB |
| Rate limiting | Disabled |
| Persistence | None |
| Memory ceiling | 256MB |

**Embedded Option (Zero-dependency local):**
For users who don't want to run a separate Redis container, support an embedded alternative:
* **`fakeredis`**: Pure Python Redis implementation, perfect for testing and lightweight local use
* **SQLite + TTL logic**: Single-file persistence with background expiry thread
* Auto-detect: If `REDIS_URL` is unset, fall back to embedded mode

**Docker Compose Profiles:**
```yaml
# docker-compose.yml
services:
  web:
    build: .
    profiles: ["local", "production"]
    
  redis:
    image: redis:alpine
    profiles: ["local", "production"]
    
  redis-persistent:
    image: redis:alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    profiles: ["production"]
```

```bash
# Usage
docker compose --profile local up      # RAM-only, single container
docker compose --profile production up # AOF persistence, volumes
```

---

## 6. Competitive Landscape

### Direct Competitors (AI Agent Memory)
FlashMemory occupies a specific niche: **ephemeral, short-term agent RAM**. The broader AI memory space includes:

| Product | Focus | Persistence | Self-Hostable | Key Differentiator |
| :--- | :--- | :--- | :--- | :--- |
| **FlashMemory** | Ephemeral scratchpad | TTL-based eviction | Yes | Trash-first philosophy, zero-config |
| **Mem0** | Long-term personalization | Permanent | Limited | User preference storage, managed SaaS |
| **Zep** | Temporal knowledge graphs | Permanent | Yes (Community) | Graph-based relationships, enterprise focus |
| **Letta (MemGPT)** | Stateful agents | Archival + recall | Yes | Agent Development Environment, open source |
| **AgentFS** | Agent filesystem | SQLite-backed | Yes | Single-file portability, audit trails |

**Where FlashMemory fits:**
* Mem0/Zep/Letta solve **long-term memory** (what does the agent remember about this user?)
* FlashMemory solves **working memory** (where does the agent stash intermediate results during a task?)
* These are complementary, not competitive—an agent might use Mem0 for user preferences AND FlashMemory for mid-task state

### Infrastructure Alternatives (Key-Value Stores)
If users want to swap the underlying store:

| Store | Local-Friendly | Redis-Compatible | Notes |
| :--- | :--- | :--- | :--- |
| **Redis** | Docker required | ✓ | The standard, battle-tested |
| **Valkey** | Docker required | ✓ | Open-source Redis fork (Linux Foundation) |
| **Dragonfly** | Docker required | ✓ | 25x throughput, drop-in replacement |
| **KeyDB** | Docker required | ✓ | Multithreaded Redis alternative |
| **fakeredis** | Native Python | ✓ | Perfect for testing/embedded use |

---

## 7. Development & Testing Instructions (For AI Agents)

### Implementation Roadmap
1.  **Auth Layer:** Create a mock user database (dictionary) mapping keys to tiers. Use a FastAPI Dependency to protect all routes.
2.  **Logging Setup:** Configure `structlog` with JSON formatting and request ID middleware early—this makes debugging all subsequent steps easier.
3.  **Size Guardrail:** Implement dual-layer validation (header check + post-deserialization) as middleware.
4.  **Rate Limiter:** Add per-key rate limiting using Redis counters or `slowapi`.
5.  **Redis Integration:** Use `redis-py`'s `setex` command to handle the key and expiry in a single atomic operation.
6.  **ID Generation:** Implement collision-safe ID generation with retry logic.

### Test Cases
* **The Wall Test:** Verify `User_A` cannot GET `User_B`'s data even if they know the `memory_id`.
* **The Expiry Test:** Stash with `ttl: 2`, wait 3 seconds, verify 404.
* **The Bloat Test:** Attempt to POST a 5MB JSON on a 1MB limit account. Verify `413 Payload Too Large`.
* **The Liar Test:** Send a request with `Content-Length: 100` but actual payload of 5MB. Verify rejection.
* **The Collision Test:** Force ID collisions and verify graceful handling/retry.
* **The Flood Test:** Send requests exceeding rate limit, verify `429 Too Many Requests`.
* **The Audit Test:** Verify all operations emit structured logs with correct `request_id`, `user_id`, and `memory_id` fields.

---

## 8. Containerization (docker-compose.yml)
The project must include a `docker-compose.yml` defining:
* `web`: The FastAPI application.
* `redis`: The Redis instance (using `redis:alpine`).
* **Volumes:** Setup a volume for `/data` to support the "Paid Tier" AOF persistence mode.