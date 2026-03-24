from __future__ import annotations


STAGE_LABELS = {
    "download": "Step 0 download",
    "prepare_dense_capture": "Step 1 dense capture",
    "prepare_structural_compare": "Step 1.5 structural compare",
    "prepare_llm_queue": "Step 1.6 queue build",
    "prepare_llm_prompts": "Step 1.7 prompt build",
    "vision_sync": "Step 2 vision sync",
    "vision_submit": "Step 2 vision batch submit",
    "vision_remote": "Step 2 vision batch wait",
    "knowledge_submit": "Step 3 knowledge batch submit",
    "knowledge_remote": "Step 3 knowledge batch wait",
    "component2": "Step 3 component 2",
    "postprocess": "Step 3 post-process",
    "corpus": "Corpus",
}


STAGE_FOCUS_LABELS = {
    "vision_sync": "Image analysis",
    "vision_submit": "Image analysis",
    "vision_remote": "Image analysis",
    "knowledge_submit": "Knowledge extraction",
    "knowledge_remote": "Knowledge extraction",
    "component2": "Knowledge post-processing and exports",
    "postprocess": "Knowledge post-processing and exports",
}


def get_stage_label(stage: str | None) -> str | None:
    if not stage:
        return None
    return STAGE_LABELS.get(stage, stage.replace("_", " "))


def get_stage_focus_label(stage: str | None) -> str | None:
    if not stage:
        return None
    return STAGE_FOCUS_LABELS.get(stage)
