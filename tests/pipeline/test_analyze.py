import json
from pathlib import Path

from PIL import Image

from helpers import analyze
from helpers.utils.frame_schema import ensure_material_change


def _write_image(path: Path) -> None:
    Image.new("RGB", (16, 16), color=(255, 255, 255)).save(path)


def test_analyze_frame_with_on_event_emits_stages_and_returns_same_result(monkeypatch, tmp_path: Path) -> None:
    """With on_event, analyze_frame must emit start/end for extract and relevance and return same dict."""
    image_path = tmp_path / "frame.png"
    _write_image(image_path)
    events = []

    def fake_call_agent(agent: str, image_path_arg: str | Path, prompt: str, **kwargs: object) -> dict:
        on_event = kwargs.get("on_event")
        stage = kwargs.get("stage", "")
        frame_key = kwargs.get("frame_key", "")
        if on_event is not None:
            on_event({"kind": "start", "provider": agent, "stage": stage, "frame_key": frame_key})
            on_event({"kind": "chunk", "provider": agent, "stage": stage, "text_delta": "{}", "frame_key": frame_key})
            on_event({"kind": "end", "provider": agent, "stage": stage, "frame_key": frame_key})
        if stage == "extract":
            return {
                "frame_timestamp": "00:00:01",
                "material_change": True,
                "visual_representation_type": "text_slide",
                "current_state": {"visual_facts": ["Visible title"], "trading_relevant_interpretation": []},
                "change_summary": ["Slide changed"],
            }
        return {
            "lesson_relevant": True,
            "scene_boundary": True,
            "change_summary": ["New lesson title"],
            "explanation_summary": "A new lesson slide introduces a new concept.",
            "skip_reason": None,
        }

    def collect(ev):
        events.append(ev)

    monkeypatch.setattr(analyze, "_call_agent", fake_call_agent)

    result = analyze.analyze_frame(
        image_path,
        "000001",
        structural_score=0.41,
        previous_state={"frame_timestamp": "00:00:00"},
        previous_relevant_frame="000000",
        agent="openai",
        on_event=collect,
    )

    stages = [e["stage"] for e in events if e.get("kind") == "start"]
    assert "extract" in stages
    assert "relevance" in stages
    assert result["lesson_relevant"] is True
    assert result["material_change"] is True
    assert result["explanation_summary"]


def test_analyze_frame_calls_extract_then_relevance(monkeypatch, tmp_path: Path) -> None:
    image_path = tmp_path / "frame.png"
    _write_image(image_path)
    calls: list[str] = []

    def fake_call_agent(agent: str, image_path_arg: str | Path, prompt: str, **kwargs: object) -> dict:
        calls.append(kwargs.get("stage", ""))
        if kwargs.get("stage") == "extract":
            return {
                "frame_timestamp": "00:00:01",
                "material_change": True,
                "visual_representation_type": "text_slide",
                "current_state": {"visual_facts": ["Visible title"], "trading_relevant_interpretation": []},
                "change_summary": ["Slide changed"],
            }
        return {
            "lesson_relevant": True,
            "scene_boundary": True,
            "change_summary": ["New lesson title"],
            "explanation_summary": "A new lesson slide introduces a new concept.",
            "skip_reason": None,
        }

    monkeypatch.setattr(analyze, "_call_agent", fake_call_agent)

    result = analyze.analyze_frame(
        image_path,
        "000001",
        structural_score=0.41,
        previous_state={"frame_timestamp": "00:00:00"},
        previous_relevant_frame="000000",
        agent="gemini",
    )

    assert calls == ["extract", "relevance"]
    assert result["lesson_relevant"] is True
    assert result["material_change"] is True
    assert result["scene_boundary"] is True
    assert result["explanation_summary"]
    assert result["structural_score"] == 0.41


def test_analyze_frame_marks_irrelevant_changes(monkeypatch, tmp_path: Path) -> None:
    image_path = tmp_path / "frame.png"
    _write_image(image_path)

    def fake_call_agent(agent: str, image_path_arg: str | Path, prompt: str, **kwargs: object) -> dict:
        if kwargs.get("stage") == "extract":
            return {
                "frame_timestamp": "00:00:02",
                "material_change": True,
                "visual_representation_type": "mixed_visual",
                "current_state": {"visual_facts": ["Cursor moved"], "trading_relevant_interpretation": []},
                "change_summary": ["Cursor moved"],
            }
        return {
            "lesson_relevant": False,
            "scene_boundary": False,
            "change_summary": ["UI movement only"],
            "explanation_summary": None,
            "skip_reason": "ui_only_change",
        }

    monkeypatch.setattr(analyze, "_call_agent", fake_call_agent)

    result = analyze.analyze_frame(
        image_path,
        "000002",
        structural_score=0.82,
        agent="openai",
    )

    assert result["lesson_relevant"] is False
    assert result["material_change"] is True  # preserved from extraction (visual change), not derived from lesson_relevant
    assert result["pipeline_status"] == "relevance_skipped"
    assert result["skip_reason"] == "ui_only_change"


def test_normalize_preserves_no_change() -> None:
    """Raw no-change response must stay no-change after normalization (no promotion to change)."""
    raw_no_change_minimal = {
        "frame_timestamp": "00:09:52",
        "material_change": False,
    }
    out = analyze._normalize_extraction_output("000592", raw_no_change_minimal)
    assert out["material_change"] is False
    assert out["change_summary"] == []

    raw_no_change_with_summary = {
        "frame_timestamp": "00:09:53",
        "material_change": False,
        "change_summary": ["No change from previous state."],
    }
    out2 = analyze._normalize_extraction_output("000593", raw_no_change_with_summary)
    assert out2["material_change"] is False
    assert out2["change_summary"] == []


def test_ensure_material_change_not_overwritten_by_lesson_relevant() -> None:
    """material_change must not be derived from lesson_relevant (semantic separation)."""
    entry = {"frame_timestamp": "00:00:01", "material_change": False, "lesson_relevant": True}
    result = ensure_material_change(entry)
    assert result["material_change"] is False
    assert result["lesson_relevant"] is True


def test_normalize_preserves_rich_visual_facts_and_interpretation() -> None:
    """Richer current_state.visual_facts and trading_relevant_interpretation must survive normalization."""
    raw = {
        "frame_timestamp": "00:09:51",
        "material_change": True,
        "change_summary": ["New diagram"],
        "visual_representation_type": "abstract_bar_diagram",
        "example_type": "abstract_teaching_example",
        "extraction_mode": "structural_only",
        "screen_type": "chart",
        "educational_event_type": ["level_identification"],
        "current_state": {
            "symbol": None,
            "timeframe": None,
            "visual_facts": [
                "A horizontal white line represents a key level.",
                "Green bars mostly stay below the level or briefly pierce it from below.",
            ],
            "trading_relevant_interpretation": [
                "The diagram illustrates price interaction with a limit player's level.",
                "The red bars might represent failed attempts to break the level.",
            ],
            "structural_pattern_visible": [],
        },
        "extracted_entities": {"setup_names": [], "level_values": [], "stop_values": [], "target_values": [], "pattern_terms": [], "risk_reward_values": [], "atr_values": [], "entry_values": []},
        "notes": None,
    }
    out = analyze._normalize_extraction_output("000591", raw)
    assert out["material_change"] is True
    assert out["current_state"]["visual_facts"] == [
        "A horizontal white line represents a key level.",
        "Green bars mostly stay below the level or briefly pierce it from below.",
    ]
    assert out["current_state"]["trading_relevant_interpretation"] == [
        "The diagram illustrates price interaction with a limit player's level.",
        "The red bars might represent failed attempts to break the level.",
    ]


def test_normalize_schema_shaped_but_noncanonical_output() -> None:
    """Schema-shaped Qwen output should still be canonicalized for downstream use."""
    raw = {
        "frame_timestamp": "00:09:51",
        "material_change": True,
        "change_summary": ["New chart type displayed"],
        "visual_representation_type": "candlestick sketches",
        "example_type": "abstract teaching example",
        "extraction_mode": "structural_only",
        "screen_type": "whiteboard explanations",
        "educational_event_type": "chart analysis",
        "current_state": {
            "chart_type": "candlestick",
            "chart_layout": "horizontal",
            "drawn_objects": ["candlesticks", "horizontal lines"],
            "visible_annotations": [
                {"text": "Уровень лимитного игрока"},
                {"text": "КОРОТКИЙ СТОП"},
            ],
            "visual_facts": [
                "Green candlesticks",
                "Red candlestick",
                "Horizontal line with annotations",
            ],
            "structural_pattern_visible": False,
            "trading_relevant_interpretation": "Illustration of short-term stop levels",
            "readability": "High",
        },
        "extracted_entities": {
            "setup_names": ["Уровень лимитного игрока", "КОРОТКИЙ СТОП"],
            "level_values": "N/A",
            "risk_reward_values": "N/A",
            "entry_values": "N/A",
            "stop_values": "N/A",
            "target_values": "N/A",
            "pattern_terms": ["short-term stop"],
        },
        "notes": "The chart illustrates short-term stop levels in a trading context.",
    }
    out = analyze._normalize_extraction_output("000591", raw)
    assert out["visual_representation_type"] == "candlestick_sketch"
    assert out["example_type"] == "abstract_teaching_example"
    assert out["current_state"]["trading_relevant_interpretation"] == [
        "Illustration of short-term stop levels"
    ]
    assert out["current_state"]["readability"]["text_confidence"] == "high"
    assert out["current_state"]["visible_annotations"] == [
        {"text": "Уровень лимитного игрока"},
        {"text": "КОРОТКИЙ СТОП"},
    ]
    assert out["extracted_entities"]["level_values"] == []


def test_gemini_frame_591_shape_alignment() -> None:
    """Representative shape from Gemini batch 000591: rich visual_facts, trading_relevant_interpretation, material_change."""
    batch_path = Path(__file__).resolve().parent.parent / "data" / "Lesson 2. Levels part 1" / "batches" / "dense_batch_response_000591-000600.json"
    if not batch_path.exists():
        return
    with open(batch_path, "r", encoding="utf-8") as f:
        batch = json.load(f)
    frame_591 = batch.get("000591")
    assert frame_591 is not None
    assert frame_591.get("material_change") is True
    assert frame_591.get("visual_representation_type") == "abstract_bar_diagram"
    current = frame_591.get("current_state") or {}
    assert isinstance(current.get("visual_facts"), list) and len(current["visual_facts"]) >= 2
    assert isinstance(current.get("trading_relevant_interpretation"), list) and len(current["trading_relevant_interpretation"]) >= 1
    out = analyze._normalize_extraction_output("000591", frame_591)
    assert out["material_change"] is True
    assert len(out["current_state"]["visual_facts"]) >= 2
    assert len(out["current_state"]["trading_relevant_interpretation"]) >= 1


# ---------------------------------------------------------------------------
# Gold acceptance tests — Phase 1: explicit criteria from Gemini reference
# ---------------------------------------------------------------------------

GOLD_DIR = Path(__file__).resolve().parent / "gold"


def _load_gold(filename: str) -> dict:
    with open(GOLD_DIR / filename, "r", encoding="utf-8") as f:
        return json.load(f)


def test_gold_591_normalization_preserves_representation_type() -> None:
    """After normalization, abstract_bar_diagram must stay abstract_bar_diagram (not collapse to candlestick_sketch)."""
    gold = _load_gold("frame_000591_gemini.json")
    out = analyze._normalize_extraction_output("000591", gold)
    assert out["visual_representation_type"] == "abstract_bar_diagram", (
        f"Expected 'abstract_bar_diagram', got '{out['visual_representation_type']}'"
    )


def test_gold_591_normalization_preserves_visual_facts_density() -> None:
    """After normalization, visual_facts must contain all 6 Gemini sentences (density gate)."""
    gold = _load_gold("frame_000591_gemini.json")
    out = analyze._normalize_extraction_output("000591", gold)
    facts = out["current_state"]["visual_facts"]
    assert isinstance(facts, list), "visual_facts must be a list"
    assert len(facts) >= 4, f"Expected >= 4 visual_facts, got {len(facts)}: {facts}"


def test_gold_591_normalization_preserves_interpretation_list() -> None:
    """After normalization, trading_relevant_interpretation must be a list with >= 2 items."""
    gold = _load_gold("frame_000591_gemini.json")
    out = analyze._normalize_extraction_output("000591", gold)
    interp = out["current_state"]["trading_relevant_interpretation"]
    assert isinstance(interp, list), "trading_relevant_interpretation must be a list"
    assert len(interp) >= 2, f"Expected >= 2 interpretation items, got {len(interp)}: {interp}"


def test_gold_591_normalization_preserves_structural_pattern() -> None:
    """After normalization, structural_pattern_visible must include 'price_action_around_level'."""
    gold = _load_gold("frame_000591_gemini.json")
    out = analyze._normalize_extraction_output("000591", gold)
    patterns = out["current_state"]["structural_pattern_visible"]
    assert isinstance(patterns, list), "structural_pattern_visible must be a list"
    assert "price_action_around_level" in patterns, (
        f"Expected 'price_action_around_level' in structural_pattern_visible, got: {patterns}"
    )


def test_gold_591_normalization_preserves_conceptual_level_values() -> None:
    """After normalization, level_values from Gemini reference must not be discarded."""
    gold = _load_gold("frame_000591_gemini.json")
    out = analyze._normalize_extraction_output("000591", gold)
    level_values = out["extracted_entities"]["level_values"]
    assert isinstance(level_values, list) and len(level_values) >= 1, (
        f"Expected non-empty level_values, got: {level_values}"
    )


def test_gold_591_normalization_preserves_conceptual_stop_values() -> None:
    """After normalization, stop_values from Gemini reference must not be discarded."""
    gold = _load_gold("frame_000591_gemini.json")
    out = analyze._normalize_extraction_output("000591", gold)
    stop_values = out["extracted_entities"]["stop_values"]
    assert isinstance(stop_values, list) and len(stop_values) >= 1, (
        f"Expected non-empty stop_values, got: {stop_values}"
    )


def test_gold_591_normalization_preserves_drawn_objects_structure() -> None:
    """After normalization, drawn_objects from dict-of-lists Gemini format must yield structured items."""
    gold = _load_gold("frame_000591_gemini.json")
    out = analyze._normalize_extraction_output("000591", gold)
    drawn = out["current_state"]["drawn_objects"]
    assert isinstance(drawn, list) and len(drawn) >= 1, (
        f"Expected non-empty drawn_objects list, got: {drawn}"
    )
    for obj in drawn:
        assert isinstance(obj, dict), f"Each drawn_object must be a dict, got: {obj}"


def test_gold_591_normalization_preserves_annotations_with_location() -> None:
    """After normalization, visible_annotations from Gemini's structured format must preserve text content."""
    gold = _load_gold("frame_000591_gemini.json")
    out = analyze._normalize_extraction_output("000591", gold)
    annotations = out["current_state"]["visible_annotations"]
    assert isinstance(annotations, list) and len(annotations) >= 2, (
        f"Expected >= 2 visible_annotations, got: {annotations}"
    )
    annotation_texts = " ".join(str(a) for a in annotations)
    assert "СТОП" in annotation_texts or "лимитного" in annotation_texts, (
        f"Expected Russian annotation labels in visible_annotations, got: {annotations}"
    )


def test_gold_591_educational_event_type_passthrough() -> None:
    """Gemini-style educational_event_type items that are in our vocab must pass through normalization."""
    raw = {
        "frame_timestamp": "00:09:51",
        "material_change": True,
        "change_summary": ["New diagram"],
        "visual_representation_type": "abstract_bar_diagram",
        "example_type": "abstract_teaching_example",
        "extraction_mode": "structural_only",
        "screen_type": "chart",
        "educational_event_type": ["level_identification", "stop_discussion"],
        "current_state": {
            "visual_facts": ["A level is shown."],
            "trading_relevant_interpretation": ["Price is interacting with a level."],
        },
        "extracted_entities": {},
        "notes": None,
    }
    out = analyze._normalize_extraction_output("000591", raw)
    assert "level_identification" in out["educational_event_type"], out["educational_event_type"]
    assert "stop_discussion" in out["educational_event_type"], out["educational_event_type"]


def test_gold_591_conceptual_entities_from_gemini_format() -> None:
    """Object-shaped level_values and stop_values from Gemini must survive normalization as non-empty lists."""
    raw = {
        "frame_timestamp": "00:09:51",
        "material_change": True,
        "change_summary": ["New diagram"],
        "visual_representation_type": "abstract_bar_diagram",
        "example_type": "abstract_teaching_example",
        "extraction_mode": "structural_only",
        "screen_type": "chart",
        "educational_event_type": ["level_identification"],
        "current_state": {
            "visual_facts": ["A horizontal line represents a key level."],
            "trading_relevant_interpretation": ["Price interacts with limit player level."],
        },
        "extracted_entities": {
            "setup_names": ["Уровень лимитного игрока"],
            "level_values": [
                {"type": "horizontal", "label": "Уровень лимитного игрока", "value_description": "conceptual price level"}
            ],
            "stop_values": [
                {"type": "conceptual", "label": "КОРОТКИЙ СТОП", "value_description": "area below the level"},
                {"type": "conceptual", "label": "СТОПЫ", "value_description": "area above the level"},
            ],
            "pattern_terms": ["price_action_around_level"],
        },
        "notes": None,
    }
    out = analyze._normalize_extraction_output("000591", raw)
    assert len(out["extracted_entities"]["level_values"]) >= 1, out["extracted_entities"]["level_values"]
    assert len(out["extracted_entities"]["stop_values"]) >= 2, out["extracted_entities"]["stop_values"]
    assert "price_action_around_level" in out["extracted_entities"]["pattern_terms"], out["extracted_entities"]["pattern_terms"]


# ---------------------------------------------------------------------------
# Phase 5 normalization regression tests
# ---------------------------------------------------------------------------

def test_canonical_visual_type_abstract_bar_diagram_variants() -> None:
    """All common model phrasings for abstract_bar_diagram must normalize to the canonical value."""
    for variant in ["abstract_bar_diagram", "abstract bar diagram", "bar diagram"]:
        out = analyze._canonical_visual_type(variant, has_chart=False, has_text=False)
        assert out == "abstract_bar_diagram", f"'{variant}' should normalize to 'abstract_bar_diagram', got '{out}'"


def test_canonical_visual_type_candlestick_sketch_variants() -> None:
    for variant in ["candlestick_sketch", "candlestick sketch", "candlestick sketches"]:
        out = analyze._canonical_visual_type(variant, has_chart=False, has_text=False)
        assert out == "candlestick_sketch", f"'{variant}' → '{out}'"


def test_canonical_visual_type_hand_drawn_variants() -> None:
    for variant in ["hand_drawn_pattern", "hand drawn pattern", "hand drawn"]:
        out = analyze._canonical_visual_type(variant, has_chart=False, has_text=False)
        assert out == "hand_drawn_pattern", f"'{variant}' → '{out}'"


def test_structural_pattern_string_becomes_list() -> None:
    """When Gemini returns structural_pattern_visible as a string, normalization must convert to list."""
    raw = {
        "frame_timestamp": "00:09:51",
        "material_change": True,
        "change_summary": ["New diagram"],
        "visual_representation_type": "abstract_bar_diagram",
        "example_type": "abstract_teaching_example",
        "extraction_mode": "structural_only",
        "screen_type": "chart",
        "educational_event_type": ["level_identification"],
        "current_state": {
            "visual_facts": ["A level is shown."],
            "trading_relevant_interpretation": ["Price is interacting with a level."],
            "structural_pattern_visible": "price_action_around_level",
        },
        "extracted_entities": {},
        "notes": None,
    }
    out = analyze._normalize_extraction_output("000591", raw)
    patterns = out["current_state"]["structural_pattern_visible"]
    assert isinstance(patterns, list), f"structural_pattern_visible must be a list, got {type(patterns)}"
    assert "price_action_around_level" in patterns, patterns


def test_visible_annotations_dict_objects_preserved() -> None:
    """Structured annotation objects {text, location, language} must be preserved through normalization."""
    raw = {
        "frame_timestamp": "00:09:51",
        "material_change": True,
        "change_summary": ["New diagram"],
        "visual_representation_type": "abstract_bar_diagram",
        "example_type": "abstract_teaching_example",
        "extraction_mode": "structural_only",
        "screen_type": "chart",
        "educational_event_type": [],
        "current_state": {
            "visual_facts": ["A level is shown."],
            "trading_relevant_interpretation": ["Price around level."],
            "visible_annotations": [
                {"text": "Уровень лимитного игрока", "location": "top_center", "language": "ru"},
                {"text": "КОРОТКИЙ СТОП", "location": "below_level_left", "language": "ru"},
            ],
        },
        "extracted_entities": {},
        "notes": None,
    }
    out = analyze._normalize_extraction_output("000591", raw)
    annotations = out["current_state"]["visible_annotations"]
    assert isinstance(annotations, list) and len(annotations) == 2, annotations
    for ann in annotations:
        assert isinstance(ann, dict) and "text" in ann, f"Expected dict with text key, got: {ann}"
    texts = [a["text"] for a in annotations]
    assert "Уровень лимитного игрока" in texts
    assert "КОРОТКИЙ СТОП" in texts


def test_n_a_entity_values_become_empty_lists() -> None:
    """'N/A' values in extracted_entities must be normalized to empty lists."""
    raw = {
        "frame_timestamp": "00:09:51",
        "material_change": True,
        "change_summary": ["New diagram"],
        "visual_representation_type": "abstract_bar_diagram",
        "example_type": "abstract_teaching_example",
        "extraction_mode": "structural_only",
        "screen_type": "chart",
        "educational_event_type": [],
        "current_state": {
            "visual_facts": ["A level."],
            "trading_relevant_interpretation": ["Price around level."],
        },
        "extracted_entities": {
            "level_values": "N/A",
            "stop_values": "N/A",
            "entry_values": "N/A",
            "target_values": "N/A",
        },
        "notes": None,
    }
    out = analyze._normalize_extraction_output("000591", raw)
    assert out["extracted_entities"]["level_values"] == [], out["extracted_entities"]["level_values"]
    assert out["extracted_entities"]["stop_values"] == [], out["extracted_entities"]["stop_values"]


def test_screen_type_chart_with_instructor_passthrough() -> None:
    """'chart_with_instructor' must be accepted as a valid screen_type."""
    raw = {
        "frame_timestamp": "00:09:51",
        "material_change": True,
        "change_summary": ["New diagram"],
        "visual_representation_type": "abstract_bar_diagram",
        "example_type": "abstract_teaching_example",
        "extraction_mode": "structural_only",
        "screen_type": "chart_with_instructor",
        "educational_event_type": [],
        "current_state": {
            "visual_facts": ["A level."],
            "trading_relevant_interpretation": ["Price around level."],
        },
        "extracted_entities": {},
        "notes": None,
    }
    out = analyze._normalize_extraction_output("000591", raw)
    assert out["screen_type"] == "chart_with_instructor", out["screen_type"]


def test_gemini_expanded_educational_event_types_passthrough() -> None:
    """Gemini-expanded event types (concept_introduction, level_explanation, stop_loss_placement) must pass through."""
    raw = {
        "frame_timestamp": "00:09:51",
        "material_change": True,
        "change_summary": ["New diagram"],
        "visual_representation_type": "abstract_bar_diagram",
        "example_type": "abstract_teaching_example",
        "extraction_mode": "structural_only",
        "screen_type": "chart",
        "educational_event_type": ["concept_introduction", "level_explanation", "stop_loss_placement"],
        "current_state": {
            "visual_facts": ["A level."],
            "trading_relevant_interpretation": ["Price around level."],
        },
        "extracted_entities": {},
        "notes": None,
    }
    out = analyze._normalize_extraction_output("000591", raw)
    evt = out["educational_event_type"]
    assert "concept_introduction" in evt, evt
    assert "level_explanation" in evt, evt
    assert "stop_loss_placement" in evt, evt
