"""
Load pipeline.yml from the project folder (data/<video_id>/). All config and work for a run lives there.
Precedence: CLI > data/<video_id>/pipeline.yml (default section) > env > hardcoded default.
"""
import os
from pathlib import Path

CONFIG_FILENAME = "pipeline.yml"
DATA_DIR = "data"
DEFAULT_AGENT = "ide"
DEFAULT_BATCH_SIZE = 10


def _parse_int(raw: str | None, default: int | None = None) -> int | None:
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _parse_float(raw: str | None, default: float | None = None) -> float | None:
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _parse_bool(raw: str | None, default: bool = False) -> bool:
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def load_pipeline_config_for_video(video_id: str) -> dict | None:
    """Load pipeline.yml from project folder data/<video_id>/pipeline.yml. Returns raw dict or None."""
    path = Path(DATA_DIR) / video_id / CONFIG_FILENAME
    if not path.is_file():
        return None
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception:
        return None


def get_config_for_video(video_id: str) -> dict:
    """
    Return effective config from the project folder (data/<video_id>/).
    Config file: data/<video_id>/pipeline.yml, section "default".
    Optional video_file and vtt_file: filenames relative to data/<video_id>/.
    Precedence: CLI > project pipeline.yml default > env > hardcoded.
    """
    raw = load_pipeline_config_for_video(video_id)
    yaml_default = {}
    if raw:
        yaml_default = dict(raw.get("default") or raw if isinstance(raw, dict) else {})
    result = {
        "agent_images": os.getenv("AGENT_IMAGES") or os.getenv("AGENT") or DEFAULT_AGENT,
        "batch_size": DEFAULT_BATCH_SIZE,
        "parallel_batches": False,
        "workers": _parse_int(os.getenv("WORKERS") or os.getenv("MAX_WORKERS"), None),
        "video_file": None,
        "vtt_file": None,
        "model_name": os.getenv("MODEL_NAME"),
        "model_images": os.getenv("MODEL_IMAGES") or os.getenv("MODEL_NAME"),
        "model_component2": os.getenv("MODEL_COMPONENT2") or os.getenv("MODEL_VLM") or os.getenv("MODEL_NAME"),
        "model_gaps": os.getenv("MODEL_GAPS") or os.getenv("MODEL_NAME"),
        "model_vlm": os.getenv("MODEL_VLM") or os.getenv("MODEL_NAME"),
        "ssim_threshold": _parse_float(os.getenv("SSIM_THRESHOLD"), 0.95),
        "telemetry_enabled": _parse_bool(os.getenv("TELEMETRY_ENABLED"), True),
    }
    batch_env = os.getenv("BATCH_SIZE")
    if batch_env is not None:
        try:
            result["batch_size"] = int(batch_env)
        except ValueError:
            pass
    _model_keys = (
        "model_name",
        "model_images",
        "model_component2",
        "model_gaps",
        "model_vlm",
    )
    _override_keys = (
        "video_file",
        "vtt_file",
        "agent_images",
        "batch_size",
        "parallel_batches",
        "workers",
        "ssim_threshold",
        "telemetry_enabled",
        *_model_keys,
    )
    for key, value in yaml_default.items():
        if value is not None and key in _override_keys:
            if key == "batch_size" and isinstance(value, str):
                try:
                    value = int(value)
                except ValueError:
                    value = result["batch_size"]
            if key == "ssim_threshold" and isinstance(value, str):
                value = _parse_float(value, result["ssim_threshold"])
            if key == "workers" and isinstance(value, str):
                value = _parse_int(value, result["workers"])
            result[key] = value
    if isinstance(result["batch_size"], str):
        try:
            result["batch_size"] = int(result["batch_size"])
        except ValueError:
            result["batch_size"] = DEFAULT_BATCH_SIZE
    return result
