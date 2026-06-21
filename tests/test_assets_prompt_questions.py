from __future__ import annotations

from prometheus_cli.assets.questions import ask_missing, build_prompt, QUESTIONS, AssetAnswers


def test_ask_missing_uses_defaults_non_interactive():
    result = ask_missing()
    assert result.answers["kind"] == "icon"
    assert result.answers["size"] == "512x512"
    assert result.answers["transparent"] == "no"


def test_ask_missing_skips_existing_answers():
    existing = {"kind": "hero", "size": "1024x1024", "transparent": "yes"}
    result = ask_missing(existing=existing)
    assert result.answers["kind"] == "hero"
    assert result.answers["size"] == "1024x1024"
    assert result.answers["transparent"] == "yes"


def test_ask_missing_warns_on_invalid_value():
    result = ask_missing(existing={"kind": "invalid-kind"})
    assert any("invalid-kind" in w for w in result.warnings)
    assert result.answers["kind"] == "icon"


def test_ask_missing_warns_when_text_included():
    result = ask_missing(existing={"text": "yes"})
    assert any("legible text" in w.lower() for w in result.warnings)


def test_ask_missing_warns_on_commercial():
    result = ask_missing(existing={"commercial": "yes"})
    assert any("commercial" in w.lower() for w in result.warnings)


def test_build_prompt_includes_kind_and_name():
    answers = AssetAnswers(answers={
        "kind": "hero", "style": "gradient", "colors": "blue, purple", "text": "no"
    })
    prompt, negative = build_prompt(answers, "landing-hero")
    assert "hero" in prompt
    assert "landing-hero" in prompt
    assert "gradient" in prompt
    assert "no text" in prompt
    assert "blurry" in negative
    assert "text" in negative


def test_build_prompt_without_style():
    answers = AssetAnswers(answers={"kind": "icon", "text": "no"})
    prompt, negative = build_prompt(answers, "test-icon")
    assert "icon" in prompt
    assert "test-icon" in prompt


def test_all_questions_have_required_fields():
    for q in QUESTIONS:
        assert "id" in q
        assert "text" in q
        assert "default" in q


def test_interactive_prompt_fn_called_for_missing():
    calls = []

    def mock_prompt(text, default):
        calls.append(text)
        return default

    ask_missing(prompt_fn=mock_prompt)
    assert len(calls) > 0
