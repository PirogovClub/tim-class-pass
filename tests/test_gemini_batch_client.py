from __future__ import annotations

from pathlib import Path

from helpers.clients.gemini_batch_client import (
    build_generate_content_batch_line,
    download_result_file,
    extract_result_text,
    iter_result_jsonl,
    upload_jsonl,
)


def test_build_generate_content_batch_line_omits_optional_fields() -> None:
    line = build_generate_content_batch_line(
        request_key="req1",
        contents=[{"role": "user", "parts": [{"text": "hello"}]}],
    )
    assert line == {
        "key": "req1",
        "request": {
            "contents": [{"role": "user", "parts": [{"text": "hello"}]}],
        },
    }


def test_build_generate_content_batch_line_includes_system_instruction() -> None:
    line = build_generate_content_batch_line(
        request_key="req2",
        contents=[{"role": "user", "parts": [{"text": "hello"}]}],
        system_instruction="be strict",
    )
    assert line["request"]["systemInstruction"] == {"parts": [{"text": "be strict"}]}


def test_extract_result_text_joins_multiple_parts() -> None:
    text = extract_result_text(
        {
            "response": {
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": "foo"}, {"text": "bar"}],
                        }
                    }
                ]
            }
        }
    )
    assert text == "foo\nbar"


def test_iter_result_jsonl_skips_blank_lines() -> None:
    rows = list(iter_result_jsonl('{"key":"a"}\n\n{"key":"b"}\n'))
    assert rows == [{"key": "a"}, {"key": "b"}]


def test_upload_jsonl_sets_plain_text_mime_type(monkeypatch, tmp_path: Path) -> None:
    upload_calls: list[dict] = []

    class _FilesApi:
        def upload(self, *, file: str, config: dict) -> dict:
            upload_calls.append({"file": file, "config": config})
            return {"name": "uploaded"}

    class _Client:
        files = _FilesApi()

    monkeypatch.setattr("helpers.clients.gemini_batch_client.get_client", lambda: _Client())
    payload = tmp_path / "requests.jsonl"
    payload.write_text('{"key":"req1"}\n', encoding="utf-8")

    result = upload_jsonl(payload, display_name="lesson2-batch")

    assert result == {"name": "uploaded"}
    assert upload_calls == [
        {
            "file": str(payload),
            "config": {
                "display_name": "lesson2-batch",
                "mime_type": "text/plain",
            },
        }
    ]


def test_download_result_file_uses_file_keyword(monkeypatch) -> None:
    download_calls: list[dict] = []

    class _FilesApi:
        def download(self, *, file: str, config=None) -> bytes:
            download_calls.append({"file": file, "config": config})
            return b'{"key":"req1"}\n'

    class _Client:
        files = _FilesApi()

    monkeypatch.setattr("helpers.clients.gemini_batch_client.get_client", lambda: _Client())

    result = download_result_file("files/result-123")

    assert result == b'{"key":"req1"}\n'
    assert download_calls == [{"file": "files/result-123", "config": None}]
