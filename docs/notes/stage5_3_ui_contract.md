# Stage 5.3 — Review workstation UI contract

Maps the minimal workstation (explorer SPA) to Stage 5.2 adjudication HTTP APIs.

## Routes (URL state)

| Path | Purpose | Query / params |
|------|---------|------------------|
| `/review/queue` | Unresolved queue, filter, refresh, open item, next | `?targetType=` optional filter (`all` or enum) |
| `/review/item/:targetType/:targetId` | Single-item review (bundle-driven) | Path: `targetType`, `targetId` (URL-encoded) |
| `/review/compare` | Side-by-side two targets | `?aType=&aId=&bType=&bId=` |

**Local-only state:** reviewer id (`localStorage`), form fields (note, reason, related id), submit loading, toast text, panel open/close.

**Reload-safe:** queue filter and item identity are in the URL; compare participants in query string.

## API dependencies

| Screen | Endpoints |
|--------|-----------|
| Queue | `GET /adjudication/queues/unresolved`, `GET /adjudication/queues/by-target?target_type=`, `GET /adjudication/queues/next?queue=unresolved&target_type=` |
| Item | `GET /adjudication/review-bundle?target_type=&target_id=` (primary); after submit `POST /adjudication/decision` then refetch bundle |
| Compare | Two parallel `GET /adjudication/review-bundle` calls |

Optional later: `GET /adjudication/families/{id}` if bundle family slice is insufficient (not required for 5.3 minimum; bundle includes family summary + member preview).

## Dev proxy

Vite proxies `/adjudication` to `VITE_BROWSER_API_BASE` (same origin as `/browser`), matching the RAG app that mounts the adjudication router.

## Reviewer identity

Workstation stores `adjudication_reviewer_id` in `localStorage` (default `workstation-reviewer`). Required for `POST /adjudication/decision`. Operators should set a stable id before submitting.

## Decision mapping

UI decision options are filtered **per `ReviewTargetType`** to match `pipeline/adjudication/policy.py`. `duplicate_of` and `merge_into` require `related_target_id` in the form.
