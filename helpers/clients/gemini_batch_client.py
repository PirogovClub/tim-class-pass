from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Iterator

from pipeline.io_utils import atomic_write_text

from helpers.clients.gemini_client import get_client

_BATCH_JSONL_MIME_TYPE = "text/plain"


def _system_instruction_content(text: str) -> dict[str, Any]:
    return {"parts": [{"text": text}]}


def build_generate_content_batch_line(
    *,
    request_key: str,
    contents: list[Any],
    system_instruction: str | None = None,
    generation_config: dict[str, Any] | None = None,
    safety_settings: list[Any] | None = None,
) -> dict[str, Any]:
    request: dict[str, Any] = {"contents": contents}
    if system_instruction:
        request["systemInstruction"] = _system_instruction_content(system_instruction)
    if generation_config:
        request["generationConfig"] = generation_config
    if safety_settings:
        request["safetySettings"] = safety_settings
    return {"key": request_key, "request": request}


def write_jsonl_lines(path: str | Path, lines: Iterable[dict[str, Any]]) -> int:
    destination = Path(path)
    encoded_lines = [json.dumps(line, ensure_ascii=False) for line in lines]
    payload = "\n".join(encoded_lines)
    if payload:
        payload += "\n"
    atomic_write_text(destination, payload, encoding="utf-8")
    return len(encoded_lines)


def upload_jsonl(path: str | Path, display_name: str) -> Any:
    client = get_client()
    files_api = getattr(client, "files")
    return files_api.upload(
        file=str(Path(path)),
        config={
            "display_name": display_name,
            # The current google-genai upload path is unreliable for `.jsonl`.
            # `text/plain` avoids MIME detection failures for batch request files.
            "mime_type": _BATCH_JSONL_MIME_TYPE,
        },
    )


def create_batch_job(*, model: str, uploaded_file_name: str, display_name: str) -> Any:
    client = get_client()
    batches_api = getattr(client, "batches")
    return batches_api.create(
        model=model,
        src=uploaded_file_name,
        config={"display_name": display_name},
    )


def get_batch_job(name: str) -> Any:
    client = get_client()
    return getattr(client, "batches").get(name=name)


def download_result_file(file_name: str) -> bytes:
    client = get_client()
    downloaded = getattr(client, "files").download(file=file_name)
    if isinstance(downloaded, bytes):
        return downloaded
    data = getattr(downloaded, "data", None)
    if isinstance(data, bytes):
        return data
    if hasattr(downloaded, "read"):
        return downloaded.read()
    if isinstance(downloaded, str):
        return downloaded.encode("utf-8")
    raise TypeError(f"Unsupported Gemini download result type: {type(downloaded)!r}")


def extract_result_text(result_line: dict[str, Any]) -> str | None:
    response = result_line.get("response") or {}
    candidates = response.get("candidates") or []
    if not candidates:
        return None
    content = (candidates[0] or {}).get("content") or {}
    parts = content.get("parts") or []
    texts = [part.get("text") for part in parts if isinstance(part, dict) and part.get("text")]
    joined = "\n".join(str(text).strip() for text in texts if str(text).strip()).strip()
    return joined or None


def iter_result_jsonl(decoded_text: str) -> Iterator[dict[str, Any]]:
    for raw_line in str(decoded_text).splitlines():
        line = raw_line.strip()
        if not line:
            continue
        yield json.loads(line)
