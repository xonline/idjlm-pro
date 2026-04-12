"""Tests for the AI classifier service."""
import pytest


class TestClassifier:
    """Test classifier service."""

    def test_parse_classification_response_valid(self):
        from app.services.classifier import _parse_classification_response
        result = _parse_classification_response(
            '[{"index": 0, "genre": "Salsa", "subgenre": "Romántica", "confidence": 85, "reasoning": "test"}]',
            1
        )
        assert len(result) == 1
        assert result[0]["genre"] == "Salsa"

    def test_parse_classification_response_markdown(self):
        from app.services.classifier import _parse_classification_response
        result = _parse_classification_response(
            '```json\n[{"index": 0, "genre": "Bachata", "subgenre": "Sensual", "confidence": 90, "reasoning": "test"}]\n```',
            1
        )
        assert len(result) == 1
        assert result[0]["genre"] == "Bachata"

    def test_parse_classification_response_malformed(self):
        from app.services.classifier import _parse_classification_response
        result = _parse_classification_response("not json at all", 1)
        assert result == []

    def test_parse_classification_response_empty(self):
        from app.services.classifier import _parse_classification_response
        result = _parse_classification_response("", 1)
        assert result == []

    def test_model_chain_includes_all_providers(self):
        """Verify the classifier supports all 6 providers."""
        from app.services.classifier import _classify_with_claude, _classify_with_gemini
        from app.services.classifier import _classify_with_openai, _classify_with_qwen
        from app.services.classifier import _classify_with_openrouter, _classify_with_ollama
        assert callable(_classify_with_claude)
        assert callable(_classify_with_gemini)
        assert callable(_classify_with_openai)
        assert callable(_classify_with_qwen)
        assert callable(_classify_with_openrouter)
        assert callable(_classify_with_ollama)

    def test_backoff_retries_on_rate_limit(self):
        """Verify backoff logic handles rate limit errors."""
        from app.services.classifier import _call_with_backoff
        call_count = 0

        def flaky_fn():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("429 rate limit exceeded")
            return "ok"

        result = _call_with_backoff(flaky_fn, max_retries=3)
        assert result == "ok"
        assert call_count == 3
