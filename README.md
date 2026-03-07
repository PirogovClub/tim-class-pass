# Multimodal YouTube Video Transcript Enrichment Pipeline

This tool automates the process of identifying when a teacher makes ambiguous visual references (e.g., "look at this bar") in a trading video, extracts the exact video frame at that timestamp, uses a Vision-Language Model (VLM) to describe the visual context, and stitches that description back into the transcript.

## Setup Instructions

This project requires **uv** and **FFmpeg**.

### 1. Environment Configuration

Copy the `.env.template` to `.env` and configure your settings:
```bash
cp .env.template .env
```

Set your desired LLM Provider (`openai`, `gemini`, or `antigravity`).
Set the corresponding API keys for OpenAI or Google Gemini.

### 2. Execution

To run the pipeline on a YouTube URL, use `uv run`:
```bash
uv run main.py "https://www.youtube.com/watch?v=YOUR_VIDEO_ID"
```

You can optionally override the configured provider:
```bash
uv run main.py "https://www.youtube.com/watch?v=YOUR_VIDEO_ID" --provider gemini
```

### Pipeline Architecture

1. **Ingestion Engine (`downloader.py`)**: Downloads the `.mp4` video and `.vtt` subtitles using `yt-dlp`.
2. **Gap Detector (`gap_detector.py`)**: Identifies non-descriptive visual references and extracts strict HH:MM:SS timestamps using an LLM.
3. **Frame Extractor (`frame_extractor.py`)**: Translates timestamps and seeks within the video to extract `.jpg` frames via `ffmpeg-python`.
4. **VLM Translator (`vlm_translator.py`)**: Sends the extracted frames and context snippet to a multimodal-LLM to generate rich descriptions.
5. **Transcript Stitcher (`stitcher.py`)**: Modifies the original `.vtt` file with the generated descriptions to create a fully self-contained text file.

Output transcripts are saved to `output_transcripts/`.
