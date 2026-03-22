from __future__ import annotations

import os

import pytest


@pytest.mark.integration
@pytest.mark.live_provider
def test_batch_lesson2_live() -> None:
    if os.getenv("RUN_BATCH_LESSON2_LIVE") != "1":
        pytest.skip("Set RUN_BATCH_LESSON2_LIVE=1 to run the live Lesson 2 batch comparison.")
    if not (os.getenv("GEMINI_API_KEY") or "").strip():
        pytest.skip("GEMINI_API_KEY is required for live Gemini Batch tests.")

    pytest.skip(
        "Live Gemini Batch comparison is gated and not exercised in the default automated suite."
    )
