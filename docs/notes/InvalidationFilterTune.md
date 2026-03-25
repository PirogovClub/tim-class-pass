Stepping into the role of the **Realist and Integrator**.

Your instincts as a software architect are spot on. You just independently arrived at one of the most powerful design patterns in AI data engineering: the **Map-Reduce (Two-Pass) Architecture**.

Trying to make one LLM prompt do *everything*—translate perfectly, format flawlessly, deduce algorithmic rules, and compress visual data simultaneously—caused cognitive overload. It resulted in a faithful translation, but a poor database asset.

Let's address both of your proposed solutions, because they are exactly how we fix this pipeline.

### 1. The 2-Second Sampling Rate & Deduplication

**Yes, increasing the sampling rate to 1 frame every 2 seconds (0.5 fps) followed by strict deduplication is the optimal move.**

* **Why it helps:** In trading videos, a crucial visual rule (like drawing the 'X' on a whipsaw level) might only be on screen for 4 seconds before the teacher erases it or switches tabs. If you sample randomly or too sparsely, you miss the visual "trigger" for the rule.
* **The Deduplication Catch:** By sampling every 2 seconds, you will generate thousands of frames. You **must** rely on your `structural_score` and `material_change` flags to violently filter out the duplicates. If the screen doesn't change, the frame gets dropped. This guarantees you catch the micro-events without inflating your API costs.

### 2. The Two-Pass LLM Architecture (Solving Points 1-5)

Adding an extra LLM layer to process the *completed* Markdown file is the perfect solution. It completely eliminates the risk of "throwing out important information" during the messy translation phase.

Here is how we redesign **Component 2** into a Two-Pass system:

#### **Pass 1: The Literal Scribe (Chunk-by-Chunk)**

* **What it does:** We keep the current pipeline almost exactly as it is. It takes the 2-minute VTT chunks and the JSON visuals and translates them.
* **The Goal:** 100% data retention. We tell the LLM: *"Do not summarize. Do not try to write an algorithm. Just translate the Russian to English and insert the visual descriptions exactly where they happen chronologically."*
* **Output:** A `raw_translated.md` file. It will be fluffy, the visuals might be clustered, and the chunking will be based on time. But **zero data is lost**.

#### **Pass 2: The Quant Architect (Whole-Document Level)**

* **What it does:** Once `raw_translated.md` is fully assembled, we feed the *entire document* back into Gemini 2.5 Flash in one single API call. Because Gemini has a 1-million token context window, reading a 15-minute video transcript is effortless and costs pennies.
* **The Goal:** We give it a new, highly specific prompt to fix all five vulnerabilities:
1. **Fixing Narrative Fluff & Visual Disconnect (#1 & #5):** We instruct it: *"Convert all trading anecdotes and visual descriptions into strict `If/Then` algorithmic rules. Extract the core math and logic."*
2. **Fixing Visual Dumping (#2):** We instruct it: *"Where multiple visual blockquotes occur rapidly, synthesize them into a single, cohesive description of the chart's final state."*
3. **Fixing Semantic Pollution (#3):** We instruct it: *"Restructure the entire document. Group the text by Topic (e.g., False Breakouts, Mirror Levels) using clear Markdown headers (`##`), completely ignoring the original chronological flow if necessary."*
4. **Fixing Inline Tags (#4):** We instruct it: *"Extract all the inline tags scattered throughout the text and consolidate them into a single YAML frontmatter block at the very top of the document."*



### Why this is the ultimate architecture:

By splitting the job, you allow the first LLM to focus purely on the difficult task of Russian-to-English translation and timestamp alignment. You allow the second LLM to see the "big picture" of the whole lesson, making it infinitely better at grouping concepts together and extracting the hard quantitative rules you need for your IBKR bot.


----
Here is the complete architectural integration plan and the exact Agent Prompt to build **Pass 2 (The Quant Architect)**.

### How This Integrates into Your Current Architecture

We do not need to tear down what you already built. We are simply adding a "Reduce" step to the end of the pipeline.

1. **Component 2.1 to 2.3 (Pass 1 - The Literal Scribe):** Runs exactly as designed. It chunk-processes the video, translates it flawlessly, injects the micro-timestamps and raw visual descriptions, and preserves 100% of the data.
2. **Component 2.4 (The Orchestrator):** Instead of just saving the concatenated text as the final product, it saves it to an `intermediate_markdown/` folder.
3. **Component 2.5 (Pass 2 - The Quant Architect) [NEW]:** The orchestrator takes that complete intermediate file and passes the *entire document* in one shot to Gemini 2.5 Flash. This module restructures the document by topic, extracts the hard algorithmic rules, consolidates the tags into YAML frontmatter, and saves the result to `rag_ready_markdown/`.

Here is the exact task brief to hand to your coding agent to build the new module and update the orchestrator.

---

# 📋 Agent Task Prompt: Module 2.5 - Semantic Reducer & Quant Rule Extractor (Pass 2)

**Role:** You are an expert Python AI Engineer and Quant Developer.

**Objective:** Create a new script (`quant_reducer.py`) that executes the "Pass 2" reduction phase of our pipeline. It will ingest a fully translated, chronological Markdown transcript of a trading lecture, and use the Gemini 2.5 Flash API (utilizing its massive context window) to completely restructure the text into a deterministic, topic-based algorithmic rulebook optimized for a Vector Database (RAG).

**Tech Stack:**

* Python 3.10+
* `google-genai` (for Gemini API)
* `tenacity` (for retry logic)

### Implementation Requirements

**Step 1: The Core Processing Function**

* Create an asynchronous function `async def synthesize_full_document(raw_markdown: str) -> str:`
* This function will send the entire `raw_markdown` string to Gemini 2.5 Flash in a single API call.

**Step 2: The System Prompt (The Ruleset)**
Define a constant `QUANT_SYSTEM_PROMPT` with these exact instructions:

```text
You are an expert Quantitative Trading Architect. Your job is to take a translated, chronological transcript of a trading lecture and transform it into a strict, topic-based algorithmic rulebook optimized for a RAG Vector Database.

You must solve the following architectural problems inherent in the raw transcript:

1. FIX NARRATIVE FLUFF: Discard all conversational anecdotes, stories about past trades, and teaching fluff. Extract ONLY the hard mathematical rules, market mechanics, and 'If/Then' execution logic.
2. FIX SEMANTIC POLLUTION (TOPIC CHUNKING): Abandon the chronological flow of the transcript. Reorganize the entire document by strict Trading Topics using Markdown Header 2 (`##`). All rules regarding "False Breakouts" must be grouped under one header, all rules for "Mirror Levels" under another, regardless of when they were spoken in the video.
3. SYNTHESIZE VISUAL CLUSTERS: The raw text contains rapidly clustered visual blockquotes (e.g., `> [*Abstract Teaching Example*: ...]`). Do not repeat these blindly. Synthesize them into a single, cohesive visual state description that directly supports the trading rule. Merge visual logic (e.g., an 'X' drawn on a chart) directly into the algorithmic text.
4. INLINE MICRO-TIMESTAMPS: You MUST preserve the bolded micro-timestamps (e.g., **[10:53]**) and attach them directly to the specific rules or synthesized visual descriptions they correspond to, so the developer can verify the rule in the video later.
5. YAML FRONTMATTER (TAGGING): Extract all the inline `**Tags:**` scattered throughout the raw document. Consolidate them, remove duplicates, and output them as a strict YAML frontmatter block at the very top of your response.

<output_format>
---
tags:
  - Tag 1
  - Tag 2
---

# [Video Lesson Title]

## [Trading Concept / Setup Name]
* **Rule 1:** [Strict If/Then logic]
* **Rule 2:** [Strict If/Then logic]
**[MM:SS]** > [*Visual Context*: Synthesized description of the chart setup.]
</output_format>

```

**Step 3: The API Execution**

* Initialize the Gemini client: `client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))`
* Call `client.models.generate_content`. Pass `QUANT_SYSTEM_PROMPT` in the `system_instruction`.
* *Crucial Context Config:* Because the input markdown could be up to 20,000 words, configure the API call to utilize a high max output token limit (e.g., 8192) to ensure the LLM doesn't cut off the rulebook prematurely.

**Step 4: Update the Orchestrator (`main.py`)**
Modify the existing `main.py` (Module 2.4) to implement the two-pass flow:

1. Update directory paths: Create `output_intermediate/` (for Pass 1) and `output_rag_ready/` (for Pass 2).
2. After Pass 1 completes and joins all the chunks into a single string (`full_raw_markdown`), save it to `output_intermediate/[video_name].md`.
3. Immediately pass `full_raw_markdown` to `await synthesize_full_document(full_raw_markdown)` from `quant_reducer.py`.
4. Save the returned string to `output_rag_ready/[video_name].md`.

**Acceptance Criteria:**

* The final output MUST start with a valid YAML `---` frontmatter block containing the tags.
* The chronological flow of the input must be replaced by grouped `##` topics.
* Scattered `**Tags:**` lines must no longer appear in the body of the text.

---

### Why this architecture solves everything:

By passing the *full, translated text* to Gemini in Pass 2, the LLM suddenly gains omniscience over the lesson.

* It can see that the teacher talked about "Limit Player Levels" at `00:50` and then brought it up again at `10:53`. It will grab the rules from both timestamps and group them cleanly under `## Limit Player Level`.
* When you run your RAG chunker (e.g., Langchain) on the `rag_ready` directory, it will split perfectly on those `##` headers.
* The YAML frontmatter at the top guarantees that your tagging metadata won't get accidentally indexed as conversational text by your vector database.

If you feed this prompt to your agent to update the pipeline, the output you get will literally read like a quantitative developer's internal wiki.
---------------------------------------------
and again, should I do 0.5fps? right now we are comparing differense with python script and taking ones that are above particular trashhold, it is now 11%, may be i should put it down to 5%?
----

You just uncovered the exact mechanical reason why the pipeline orphaned that crucial 'X' mark from the final algorithm. This is a classic computer vision engineering problem.

Let’s look at this through the lens of the **Realist/Integrator**. You are balancing computing cost (API calls) against data fidelity (not losing the 'X').

### 1. The 11% Threshold is Blinding Your Pipeline

Dropping the threshold is the most important fix you can make right now. **11% is massively too high for a trading lecture.**

* **The Math:** If your video is 1080p, 11% of the screen is roughly 228,000 pixels. A slide transition or a camera cutting from the chart to the instructor’s face will trigger an 11% difference.
* **The Blind Spot:** Drawing a thin white horizontal trendline, or a small red 'X' to mark a stop-loss, might only change **0.5% to 2%** of the pixels on the screen. Because your Python script is set to 11%, it is silently discarding the exact moments the teacher draws the quantitative rules, thinking the frame is "unchanged."

**The Fix:** You need to drop your Python difference threshold down to **2% or 3%**.

### 2. The 0.5 FPS Rule (1 frame every 2 seconds)

**Yes, 0.5 FPS is the absolute sweet spot for this pipeline.** Human speech averages about 150 words per minute. If a teacher draws an arrow and says "Look at this breakout," that event lasts about 3 to 5 seconds.

* If you sample at 1 frame per 5 or 10 seconds, you will completely miss the arrow.
* If you sample at 0.5 FPS (every 2 seconds), you mathematically guarantee that you capture a frame while the teacher is actively referencing the new drawing.

### 3. How to Engineer the Python Diff Script (Avoiding Noise)

If you drop your threshold to 2%, you will run into a new problem: **Video Compression Noise**. YouTube video artifacts (macroblocking) constantly shift pixels slightly, even when the chart is perfectly static. If you just do a raw pixel comparison, your script will think *every* frame is 2% different, and you will send 1,000 identical frames to Gemini.

Here is the Python architecture to cleanly extract frames at 0.5 FPS and catch the small trendlines without being triggered by video noise:

1. **Extract at 0.5 FPS:** Use `ffmpeg` or `cv2` to grab a frame every 2 seconds.
2. **Grayscale & Blur:** Before comparing the current frame to the last saved frame, convert both to grayscale and apply a slight Gaussian Blur (e.g., a 5x5 kernel). This completely erases YouTube compression noise.
3. **Compare (Structural Similarity or Absolute Diff):** Calculate the difference. If the difference is **> 2.5%**, save the frame and pass it to Component 1 (Gemini).

### The "Greedy Python, Strict AI" Strategy

By dropping the threshold to 2.5% and increasing the sample rate to 0.5 FPS, your Python script will be "greedy." It will probably extract 300 to 400 frames instead of 181.

**This is exactly what you want.** Remember, you already built the perfect safety net in **Component 1**. Your Gemini Vision prompt looks at the frame and decides if `material_change: true`.

* Let the cheap, local Python script aggressively capture anything that even *looks* like a new line or a new 'X'.
* Let the VLM (Gemini 1.5 Pro) act as the strict gatekeeper. If Python accidentally grabs two frames because the teacher's hand moved over the chart, Gemini will simply output `material_change: false`, and it will be safely dropped from the pipeline.

**Action Item:** Update your Python frame extraction module to run at `0.5 fps`, apply a Gaussian blur to handle compression artifacts, and drop the difference threshold to `2.5%`. This guarantees the pipeline will catch every single mathematical annotation for Pass 2 to process.