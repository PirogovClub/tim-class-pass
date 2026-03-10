# Gemini API rate limits and quotas

This project uses the Gemini API for frame analysis, dedup, gap detection, and VLM translation. When you hit **429 RESOURCE_EXHAUSTED**, you've exceeded a quota. This doc summarizes where to find limits and what we've observed.

## Official sources (authoritative)

- **Rate limits:** https://ai.google.dev/gemini-api/docs/rate-limits  
- **Monitor usage:** https://ai.dev/rate-limit  
- **Pricing:** https://ai.google.dev/gemini-api/docs/pricing  

Limits are **per project** (not per API key). Free tier quotas can vary by region and over time.

## What the 429 error tells you

The API response includes which quota was exceeded, for example:

- `generate_content_free_tier_input_token_count` — input tokens (per minute or per day)
- `generate_content_free_tier_requests` — requests (per minute or per day)
- `quotaId`: e.g. `GenerateContentInputTokensPerModelPerDay-FreeTier`, `GenerateRequestsPerMinutePerProjectPerModel-FreeTier`

If you see **limit: 0** for a model (e.g. `gemini-2.5-pro`), that model has no free-tier quota allocated for your project (or it's fully exhausted). Use a different model (e.g. `gemini-2.5-flash`) or enable billing for higher limits.

## Typical free-tier limits (reference only; check official docs)

| Model              | RPM (requests/min) | RPD (requests/day) | TPM (tokens/min, shared) |
|--------------------|--------------------|--------------------|---------------------------|
| gemini-2.5-flash   | 10                 | 250                | 250,000                   |
| gemini-2.5-pro     | 5                  | 25 (or 0 in some regions) | 250,000              |

- **RPM** = requests per minute  
- **RPD** = requests per day  
- **TPM** = tokens per minute (often shared across free-tier models)  
- Quotas can change; December 2025 saw reductions for some models.  
- **gemini-2.5-pro** free tier may show **0** RPD/RPM in some cases — use Flash or paid tier for Pro.

## In this project

- **Retries:** [gemini_client.py](../gemini_client.py) retries on 429/503/500 with exponential backoff (1s, 2s, 4s). After retries, the error is raised.
- **Script:** [scripts/run_task_gemini.py](../scripts/run_task_gemini.py) runs one batch through Gemini and prints token usage; use `--model gemini-2.5-flash` if Pro returns 429.
- **Model choice:** Prefer **gemini-2.5-flash** for high-volume frame analysis (better free-tier headroom). Use **gemini-2.5-pro** when you need higher quality and have quota (paid or when Pro free tier is available).
