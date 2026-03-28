# MDRT 08 — Configuration & Secrets

## Overview

Configuration is managed through **environment variables** and a `.env` file.
No secrets are ever hardcoded. No secret is ever logged.

---

## 8.1 Settings Model

**File:** `config/settings.py`

```python
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    """
    All runtime configuration for MDRT.
    Values are read from environment variables (case-insensitive).
    A .env file in the working directory is loaded automatically.
    """

    # ── Alpaca credentials ────────────────────────────────────────────
    alpaca_api_key:    str  = ""
    alpaca_api_secret: str  = ""
    alpaca_feed:       str  = "iex"   # "iex" (free) | "sip" (paid)

    # ── Databento credentials ─────────────────────────────────────────
    databento_api_key: str  = ""

    # ── Storage paths ─────────────────────────────────────────────────
    data_dir:   Path = Path("./data")      # archive root + catalog
    output_dir: Path = Path("./outputs")   # windows, manifests, reports

    # ── Logging ───────────────────────────────────────────────────────
    log_level: str = "INFO"   # DEBUG | INFO | WARNING | ERROR

    # ── Validation tuning ─────────────────────────────────────────────
    gap_tolerance: float = 1.5   # multiplier for acceptable bar interval gaps

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
```

**Usage in adapters:**
```python
from config.settings import Settings

settings = Settings()

if not settings.alpaca_api_key:
    raise ProviderAuthError("ALPACA_API_KEY is not set")
```

---

## 8.2 Environment Variables

### Alpaca

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ALPACA_API_KEY` | Yes (for Alpaca) | — | Alpaca API key ID |
| `ALPACA_API_SECRET` | Yes (for Alpaca) | — | Alpaca API secret key |
| `ALPACA_FEED` | No | `iex` | Data feed: `iex` (free) or `sip` (paid) |

### Databento

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABENTO_API_KEY` | Yes (for Databento) | — | Databento API key |

### Paths

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATA_DIR` | No | `./data` | Root directory for archive and catalog |
| `OUTPUT_DIR` | No | `./outputs` | Root directory for all exports |

### Logging

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LOG_LEVEL` | No | `INFO` | Python log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

### Tuning

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GAP_TOLERANCE` | No | `1.5` | Multiplier for acceptable gap size in Validator |

---

## 8.3 `.env.example`

**File:** `.env.example` (committed; `.env` is gitignored)

```env
# ── Alpaca ────────────────────────────────────────────────────────────
# Get keys at: https://app.alpaca.markets/
ALPACA_API_KEY=
ALPACA_API_SECRET=
ALPACA_FEED=iex

# ── Databento ─────────────────────────────────────────────────────────
# Get key at: https://databento.com/
DATABENTO_API_KEY=

# ── Paths (optional; defaults are relative to working dir) ────────────
# DATA_DIR=./data
# OUTPUT_DIR=./outputs

# ── Logging ───────────────────────────────────────────────────────────
# LOG_LEVEL=INFO
```

---

## 8.4 Secrets Management Rules

1. **Never hardcode a key** in any Python file, config file, or test fixture
2. **Never log a key** — log the provider name, not credentials. If `alpaca_api_key` appears in any log output, that is a defect
3. **Never accept a key as a CLI argument** — flags like `--api-key` are forbidden; this prevents keys appearing in shell history
4. **Credentials are per-provider** — `ALPACA_*` vars are never read by the Databento adapter and vice versa
5. **Test isolation** — adapter tests use cassette replay (no live keys needed in CI). The `Settings` model is mocked in unit tests

---

## 8.5 `.gitignore` Requirements

These entries MUST be present:

```gitignore
# MDRT runtime data
data/
outputs/
.env

# Python
__pycache__/
*.pyc
*.pyo
.pytest_cache/
.mypy_cache/
.ruff_cache/
*.egg-info/
dist/
```

---

## 8.6 Logging Setup

**File:** `src/market_data/__init__.py` or `src/market_data/cli/main.py`

```python
import logging
from config.settings import Settings

def setup_logging(verbose: bool = False) -> None:
    settings = Settings()
    level = logging.DEBUG if verbose else getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )
```

**Log what:**
- INFO: batch start, batch complete with row count, window exports
- DEBUG: page fetches, partition paths written, catalog operations
- WARNING: data quality warnings (gaps, low volume)
- ERROR: hard failures before raising

**Never log:**
- API keys or secrets
- Full raw response payloads (only metadata: row count, first/last ts)

---

## 8.7 Acceptance Criteria — Configuration

- [ ] Running with no `.env` file and no env vars set → `validate_credentials()` raises `ProviderAuthError` (not a generic `KeyError` or `AttributeError`)
- [ ] Setting `ALPACA_API_KEY` and `ALPACA_API_SECRET` in env → Alpaca adapter connects without code change
- [ ] Setting `DATA_DIR=/tmp/mdrt_test` via env → all files written to that path
- [ ] `log_level=DEBUG` in env → debug messages appear; no secrets in output
- [ ] `.env` is listed in `.gitignore` and not committed
- [ ] `.env.example` is committed with empty credential values
