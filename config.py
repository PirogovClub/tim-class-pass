"""
Load pipeline.yml — one config per project. Folder is chosen at run time via --video_id.
Precedence: CLI > pipeline.yml default > env > hardcoded default.
"""
import os
from pathlib import Path

CONFIG_FILENAME = "pipeline.yml"
DEFAULT_AGENT = "ide"
DEFAULT_BATCH_SIZE = 10


def _find_project_root() -> Path | None:
    """Find directory containing pipeline.yml, walking up from cwd."""
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / CONFIG_FILENAME).is_file():
            return parent
    return None


def load_pipeline_config() -> dict | None:
    """Load pipeline.yml if present. Returns raw dict or None."""
    root = _find_project_root()
    if root is None:
        return None
    path = root / CONFIG_FILENAME
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception:
        return None


def get_config_for_video(video_id: str) -> dict:
    """
    Return effective config. video_id picks the folder at run time (--video_id).
    Optional video_file and vtt_file: filenames relative to data/<video_id>/.
    Per-video overrides in videos:<video_id> for video_file/vtt_file only.
    Precedence: default (YAML) > env > hardcoded; then videos[video_id] overrides for file names.
    """
    raw = load_pipeline_config()
    yaml_default = {}
    video_overrides = {}
    if raw:
        yaml_default = dict(raw.get("default") or {})
        videos = raw.get("videos") or {}
        if video_id in videos:
            video_overrides = dict(videos[video_id]) or {}
    result = {
        "agent_images": os.getenv("AGENT_IMAGES") or os.getenv("AGENT") or DEFAULT_AGENT,
        "agent_dedup": os.getenv("AGENT_DEDUP") or os.getenv("AGENT") or DEFAULT_AGENT,
        "batch_size": DEFAULT_BATCH_SIZE,
        "parallel_batches": False,
        "video_file": None,
        "vtt_file": None,
        "model_name": os.getenv("MODEL_NAME"),
        "model_images": os.getenv("MODEL_IMAGES") or os.getenv("MODEL_NAME"),
        "model_dedup": os.getenv("MODEL_DEDUP") or os.getenv("MODEL_NAME"),
        "model_gaps": os.getenv("MODEL_GAPS") or os.getenv("MODEL_NAME"),
        "model_vlm": os.getenv("MODEL_VLM") or os.getenv("MODEL_NAME"),
    }
    batch_env = os.getenv("BATCH_SIZE")
    if batch_env is not None:
        try:
            result["batch_size"] = int(batch_env)
        except ValueError:
            pass
    _model_keys = ("model_name", "model_images", "model_dedup", "model_gaps", "model_vlm")
    _override_keys = ("video_file", "vtt_file", "agent_images", "agent_dedup", "batch_size", "parallel_batches", *_model_keys)
    for key, value in yaml_default.items():
        if value is not None:
            if key == "batch_size" and isinstance(value, str):
                try:
                    value = int(value)
                except ValueError:
                    value = result["batch_size"]
            result[key] = value
    for key, value in video_overrides.items():
        if value is not None and key in _override_keys:
            if key == "batch_size" and isinstance(value, str):
                try:
                    value = int(value)
                except ValueError:
                    value = result["batch_size"]
            result[key] = value
    if isinstance(result["batch_size"], str):
        try:
            result["batch_size"] = int(result["batch_size"])
        except ValueError:
            result["batch_size"] = DEFAULT_BATCH_SIZE
    return result
