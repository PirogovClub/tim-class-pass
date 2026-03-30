# MDRT 08 — Configuration & Secrets

> **Revision note (req-review-01):** Full IB configuration block added.
>
> **Revision note (req-review-02):** (1) `IB_PACING_DELAY_SEC` default corrected from 10.0 → **15.0**
> to match the IB "identical request within 15 seconds" minimum. Earlier specs incorrectly stated 10s.
> (2) `IB_TWS_LOGIN_TIMEZONE` (formerly `IB_HOST_TIMEZONE`): comes from config/env ONLY — NOT derived
> from any TWS API call. Must match the timezone selected on the TWS/Gateway login screen.

## Overview

Configuration is managed through **environment variables** and a `.env` file.
No secrets are ever hardcoded. No secret is ever logged.

---

## 8.1 Settings Model

**File:** `src/market_data/config/settings.py`

```python
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    """
    All runtime configuration for MDRT.
    Values are read from environment variables (case-insensitive).
    .env file in working directory is loaded automatically.
    """

    # ── IB connection ─────────────────────────────────────────────────
    ib_host: str  = "127.0.0.1"
    ib_port: int  = 7497          # 7497=TWS paper / 7496=TWS live / 4001=Gateway paper / 4002=Gateway live
    ib_client_id: int = 1         # Must be unique per simultaneous connection
    ib_host_type: str = "tws"     # "tws" | "gateway"
    ib_connect_timeout_sec: int = 30     # Max wait for nextValidId after connect()
    ib_resolve_timeout_sec: int = 15     # Max wait for reqContractDetails callback
    ib_pacing_delay_sec: float = 15.0    # MDRT conservative inter-chunk delay
                                         # Must be >= 15s (IB identical-request minimum)
                                         # Phase 1 default: 15.0s
    ib_tws_login_timezone: str = "America/New_York"  # TWS/Gateway login timezone
                                                      # IMPORTANT: this is NOT the machine/OS timezone.
                                                      # It is the timezone the user selected on the
                                                      # TWS/Gateway login screen. IB historical bars
                                                      # are returned relative to this session timezone.
                                                      # Used to interpret daily bar timestamps.

    # ── Alpaca credentials ────────────────────────────────────────────
    alpaca_api_key:    str = ""
    alpaca_api_secret: str = ""
    alpaca_feed:       str = "iex"   # "iex" (free) | "sip" (paid)

    # ── Databento credentials ─────────────────────────────────────────
    databento_api_key: str = ""

    # ── Storage paths ─────────────────────────────────────────────────
    data_dir:   Path = Path("./data")
    output_dir: Path = Path("./outputs")

    # ── Logging ───────────────────────────────────────────────────────
    log_level: str = "INFO"

    # ── Validation tuning ─────────────────────────────────────────────
    gap_tolerance: float = 1.5

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
```

---

## 8.2 Environment Variables

### IB Connection

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `IB_HOST` | No | `127.0.0.1` | TWS/Gateway host address |
| `IB_PORT` | No | `7497` | Socket port; see port guide below |
| `IB_CLIENT_ID` | No | `1` | Client ID; must be unique per simultaneous session |
| `IB_HOST_TYPE` | No | `tws` | `tws` or `gateway` |
| `IB_CONNECT_TIMEOUT_SEC` | No | `30` | Seconds to wait for `nextValidId` |
| `IB_RESOLVE_TIMEOUT_SEC` | No | `15` | Seconds to wait for contract details |
| `IB_PACING_DELAY_SEC` | No | `15.0` | MDRT conservative inter-chunk delay (seconds). Must be ≥ 15 (IB identical-request minimum) |
| `IB_TWS_LOGIN_TIMEZONE` | **Yes (for IB)** | `America/New_York` | Timezone selected on the TWS/Gateway login screen. **Config-only — never derived from API.** This is NOT the machine/OS timezone. IB returns historical bars relative to this session timezone |

**IB Port Reference:**

| Host | Mode | Default Port |
|------|------|-------------|
| TWS | Paper trading | 7497 |
| TWS | Live trading | 7496 |
| IB Gateway | Paper trading | 4001 |
| IB Gateway | Live trading | 4002 |

### Alpaca

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ALPACA_API_KEY` | Yes (Alpaca) | — | API key ID |
| `ALPACA_API_SECRET` | Yes (Alpaca) | — | API secret key |
| `ALPACA_FEED` | No | `iex` | `iex` or `sip` |

### Databento

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABENTO_API_KEY` | Yes (Databento) | — | Databento API key |

### Paths

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATA_DIR` | No | `./data` | Archive and catalog root |
| `OUTPUT_DIR` | No | `./outputs` | Export outputs root |

### Logging / Tuning

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LOG_LEVEL` | No | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `GAP_TOLERANCE` | No | `1.5` | Gap detection tolerance multiplier |

---

## 8.3 `.env.example`

```env
# ── IB (Interactive Brokers) ──────────────────────────────────────────
# TWS/Gateway must be manually started and logged in before running mdrt
# See: https://interactivebrokers.github.io/tws-api/initial_setup.html
IB_HOST=127.0.0.1
IB_PORT=7497
IB_CLIENT_ID=1
IB_HOST_TYPE=tws
IB_TWS_LOGIN_TIMEZONE=America/New_York
# IB_CONNECT_TIMEOUT_SEC=30
# IB_RESOLVE_TIMEOUT_SEC=15
# IB_PACING_DELAY_SEC=15.0   # Must be >= 15 to satisfy IB identical-request minimum

# ── Alpaca ────────────────────────────────────────────────────────────
ALPACA_API_KEY=
ALPACA_API_SECRET=
ALPACA_FEED=iex

# ── Databento ─────────────────────────────────────────────────────────
DATABENTO_API_KEY=

# ── Paths ─────────────────────────────────────────────────────────────
# DATA_DIR=./data
# OUTPUT_DIR=./outputs

# ── Logging ───────────────────────────────────────────────────────────
# LOG_LEVEL=INFO
```

---

## 8.4 Secrets Management Rules

1. **Never hardcode a key or host credential** in any Python file, config file, or test fixture
2. **Never log a key** — no credential string ever appears in any log line
3. **Never accept a key as a CLI argument** — `--api-key` style flags are forbidden
4. **IB uses host:port:client_id — not secrets in the traditional sense**, but `client_id` conflicts cause connection failures. Always read from env/config
5. **Credentials are per-provider** — `IB_*` vars are never read by Alpaca/Databento adapters
6. **Test isolation** — adapter unit/replay tests never read live credentials; integration tests use a local IB Gateway session documented in `tests/adapters/README_IB_LIVE.md`

---

## 8.5 IB Operational Prerequisites

These are **hard prerequisites** that must be documented and verified before running any IB ingest.

| Prerequisite | Check |
|-------------|-------|
| TWS or IB Gateway is running and logged in | `mdrt ingest-bars --dry-run` successfully connects |
| "Enable ActiveX and Socket Clients" is checked in TWS API settings | Session connects without being refused |
| Correct port configured (paper vs live) | Match `IB_PORT` to TWS/Gateway configuration |
| Unique `client_id` per MDRT process | No duplicate client ID error (IB errorCode 501) |
| Market data subscription covers the requested instrument | No "No market data permissions" error (IB errorCode 354) |
| Daily restart window avoided | TWS / IB Gateway restarts daily at a **user-configurable time** (default: near midnight ET). Do not schedule ingests during this window. Adjust in IB Gateway Global Configuration → Auto Restart |
| "Read-Only API" mode | Read-Only mode is **acceptable** for MDRT — MDRT is data-only and does not place orders. If future workflows are added that place orders, Read-Only must be unchecked. Verify in TWS Global Configuration → API → Settings |

> **Note:** TWS/IB Gateway is a desktop application. It requires a valid IB account login.
> Auto-launch is not supported. Headless server operation requires IB Gateway (not TWS).
> There is no MDRT code path that can start or log in TWS/Gateway automatically.

---

## 8.6 Logging Setup

```python
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
- INFO: session connect, session ready, contract resolved (conId only — not full contract), batch start, batch complete (row count)
- DEBUG: chunk requests, pacing delays, partition paths written, catalog operations
- WARNING: data quality warnings, pacing close calls, reconnect attempts
- ERROR: hard failures before raising

**Never log:**
- API keys, secrets
- IB account number
- Order IDs (even though MDRT does not place orders)
- Full raw contract details responses (log `conId` and `localSymbol` only)
- Full bar data (log counts only)

---

## 8.7 Acceptance Criteria — Configuration

- [ ] No `.env` + no env vars + `--provider ib` → `ProviderConnectError` (not `KeyError`)
- [ ] `IB_HOST=127.0.0.1 IB_PORT=7497` in env → IB adapter uses those values without code change
- [ ] `IB_PORT=4001` → adapter connects to Gateway port without code change
- [ ] `IB_TWS_LOGIN_TIMEZONE` is read from config only; changing it in `.env` changes how daily bar timestamps are interpreted without any code change
- [ ] IbSession.connect() never calls any API to determine tws_login_timezone; it reads `settings.ib_tws_login_timezone` only
- [ ] `IB_PACING_DELAY_SEC=20` in env → collector sleeps 20 seconds between chunks
- [ ] `DATA_DIR=/tmp/mdrt_test` in env → all files written to that path
- [ ] `LOG_LEVEL=DEBUG` → debug messages appear; no secrets in output
- [ ] `.env` is listed in `.gitignore` and not committed
- [ ] `.env.example` is committed with all keys empty
