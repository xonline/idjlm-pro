"""Tests for the AI classifier service."""
import os

import pytest

from app.models.track import Track


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

    def test_backoff_retries_on_500(self):
        """500 is treated as transient and retried."""
        from app.services.classifier import _call_with_backoff
        call_count = 0

        def flaky_fn():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("OpenAI API error: 500 — Internal Server Error")
            return "ok"

        result = _call_with_backoff(flaky_fn, max_retries=3)
        assert result == "ok"
        assert call_count == 3

    def test_backoff_non_retryable_raises_immediately(self):
        """4xx errors other than 429 are not retried."""
        from app.services.classifier import _call_with_backoff

        def bad_fn():
            raise Exception("OpenAI API error: 400 — Bad Request")

        with pytest.raises(Exception, match="400"):
            _call_with_backoff(bad_fn, max_retries=3)

    def test_backoff_jitter_varies_wait_time(self):
        """Jitter (±25%) should produce different wait times across runs."""
        from app.services.classifier import _call_with_backoff
        import time as _time

        waits = []
        original_sleep = _time.sleep
        try:
            def tracking_sleep(secs):
                waits.append(secs)
                raise Exception("429 rate limit")

            _time.sleep = tracking_sleep

            for _ in range(5):
                try:
                    _call_with_backoff(lambda: (_ for _ in ()).throw(Exception("429 rate limit")), max_retries=2)
                except Exception:
                    pass

            # With jitter, should see varied wait times across runs
            assert len(waits) >= 5
            # Ensure not all waits are identical (jitter is working)
            distinct_waits = set(round(w, 1) for w in waits)
            assert len(distinct_waits) > 1, f"Expected jittered waits, got all same: {distinct_waits}"
        finally:
            _time.sleep = original_sleep

    def test_backoff_respects_env_max_retries(self):
        """IDJLM_BACKOFF_MAX_RETRIES env var controls retry count."""
        from app.services.classifier import _call_with_backoff
        call_count = [0]

        def flaky_fn():
            call_count[0] += 1
            raise Exception("503 service unavailable")

        os.environ["IDJLM_BACKOFF_MAX_RETRIES"] = "2"
        try:
            with pytest.raises(Exception):
                _call_with_backoff(flaky_fn)
            assert call_count[0] == 2
        finally:
            os.environ.pop("IDJLM_BACKOFF_MAX_RETRIES", None)

    def test_backoff_respects_env_base_sec(self):
        """IDJLM_BACKOFF_BASE_SEC changes the base wait time."""
        from app.services.classifier import _call_with_backoff
        import time as _time

        recorded = []

        original_sleep = _time.sleep
        try:
            def recording_sleep(secs):
                recorded.append(secs)
                raise Exception("502 bad gateway")

            _time.sleep = recording_sleep

            os.environ["IDJLM_BACKOFF_BASE_SEC"] = "5"
            try:
                with pytest.raises(Exception):
                    _call_with_backoff(lambda: (_ for _ in ()).throw(Exception("502 bad gateway")), max_retries=2)
            except Exception:
                pass

            assert len(recorded) >= 1
            # base=5, first wait should be ~5s ± jitter
            assert 3.0 <= recorded[0] <= 7.0, f"Expected ~5s with jitter, got {recorded[0]}"
        finally:
            _time.sleep = original_sleep
            os.environ.pop("IDJLM_BACKOFF_BASE_SEC", None)

    def test_classify_tracks_partial_batch_salvage(self, monkeypatch):
        """One malformed response must not kill the whole batch — remaining
        tracks continue through the model chain.
        Response indices are relative to the subset prompt, not the original batch."""
        from app.services.classifier import classify_tracks

        taxonomy = {"genres": {"Salsa": {"description": "", "subgenres": {"Romántica": {}}}}}

        tracks = [
            Track(file_path=f"/path/track{i}.mp3", filename=f"track{i}.mp3",
                  existing_title=f"Track {i}", existing_artist="Artist")
            for i in range(4)
        ]

        call_log = []

        def mock_claude(prompt, batch):
            call_log.append("claude")
            # Classifies first 2 of its 4-track prompt
            return True, '[{"index": 0, "genre": "Salsa", "subgenre": "Romántica", "confidence": 85, "reasoning": "a"}, {"index": 1, "genre": "Salsa", "subgenre": "Romántica", "confidence": 85, "reasoning": "b"}]'

        def mock_gemini(prompt, batch):
            call_log.append("gemini")
            # Gets remaining 2 tracks (indices 0,1 in its subset prompt)
            return True, '[{"index": 0, "genre": "Salsa", "subgenre": "Romántica", "confidence": 80, "reasoning": "c"}, {"index": 1, "genre": "Salsa", "subgenre": "Romántica", "confidence": 80, "reasoning": "d"}]'

        monkeypatch.setattr("app.services.classifier._classify_with_claude", mock_claude)
        monkeypatch.setattr("app.services.classifier._classify_with_gemini", mock_gemini)

        os.environ["AI_MODEL"] = "claude"
        os.environ["CLASSIFY_BATCH_SIZE"] = "10"
        try:
            result = classify_tracks(tracks, taxonomy, force=True)
        finally:
            os.environ.pop("AI_MODEL", None)
            os.environ.pop("CLASSIFY_BATCH_SIZE", None)

        assert call_log == ["claude", "gemini"], f"Expected both models to be called, got {call_log}"
        for t in result:
            assert t.classification_done, f"{t.filename} not classified"
            assert t.error is None, f"{t.filename} has error: {t.error}"
            assert t.proposed_genre == "Salsa"

    def test_classify_tracks_all_providers_exhausted(self, monkeypatch):
        """When all providers fail, every track gets the exhaustion error."""
        from app.services.classifier import classify_tracks

        taxonomy = {"genres": {"Salsa": {"description": "", "subgenres": {}}}}

        tracks = [
            Track(file_path=f"/path/track{i}.mp3", filename=f"track{i}.mp3",
                  existing_title=f"Track {i}", existing_artist="Artist")
            for i in range(2)
        ]

        def mock_fail(prompt, batch):
            return False, "API key not set"

        monkeypatch.setattr("app.services.classifier._classify_with_claude", mock_fail)
        monkeypatch.setattr("app.services.classifier._classify_with_gemini", mock_fail)
        monkeypatch.setattr("app.services.classifier._classify_with_openai", mock_fail)
        monkeypatch.setattr("app.services.classifier._classify_with_qwen", mock_fail)
        monkeypatch.setattr("app.services.classifier._classify_with_openrouter", mock_fail)
        monkeypatch.setattr("app.services.classifier._classify_with_ollama", mock_fail)

        os.environ["AI_MODEL"] = "claude"
        os.environ["CLASSIFY_BATCH_SIZE"] = "10"
        try:
            result = classify_tracks(tracks, taxonomy, force=True)
        finally:
            os.environ.pop("AI_MODEL", None)
            os.environ.pop("CLASSIFY_BATCH_SIZE", None)

        for t in result:
            assert t.error == "Classification failed: all providers exhausted"
            assert not t.classification_done

    def test_classify_tracks_partial_then_malformed_sets_correct_error(self, monkeypatch):
        """If one provider returns some results and the rest fail, missing
        tracks get 'Classification response malformed' not 'all providers exhausted'."""
        from app.services.classifier import classify_tracks

        taxonomy = {"genres": {"Salsa": {"description": "", "subgenres": {}}}}

        tracks = [
            Track(file_path=f"/path/track{i}.mp3", filename=f"track{i}.mp3",
                  existing_title=f"Track {i}", existing_artist="Artist")
            for i in range(3)
        ]

        def mock_claude(prompt, batch):
            return True, '[{"index": 0, "genre": "Salsa", "subgenre": "Unknown", "confidence": 60, "reasoning": "only one"}]'

        def mock_gemini(prompt, batch):
            return True, '[{"index": 0, "genre": "Salsa", "subgenre": "Unknown", "confidence": 70, "reasoning": "partial"}]'

        monkeypatch.setattr("app.services.classifier._classify_with_claude", mock_claude)
        monkeypatch.setattr("app.services.classifier._classify_with_gemini", mock_gemini)

        os.environ["AI_MODEL"] = "claude"
        os.environ["CLASSIFY_BATCH_SIZE"] = "10"
        try:
            result = classify_tracks(tracks, taxonomy, force=True)
        finally:
            os.environ.pop("AI_MODEL", None)
            os.environ.pop("CLASSIFY_BATCH_SIZE", None)

        assert result[0].classification_done
        assert result[0].error is None
        assert result[0].proposed_genre == "Salsa"

        # claude classified track 0. remaining_indices = [1, 2].
        # gemini's [{"index": 0, ...}] maps to remaining_indices[0] = batch[1].
        # So track 2 is the only one left malformed.
        assert result[1].classification_done
        assert result[1].error is None
        assert result[1].proposed_genre == "Salsa"

        assert not result[2].classification_done
        assert result[2].error == "Classification response malformed"

    def test_classify_tracks_first_model_classifies_all(self, monkeypatch):
        """When the first model classifies all tracks, no other model is called."""
        from app.services.classifier import classify_tracks

        taxonomy = {"genres": {"Salsa": {"description": "", "subgenres": {}}}}

        tracks = [
            Track(file_path="/path/track0.mp3", filename="track0.mp3",
                  existing_title="Track 0", existing_artist="Artist"),
            Track(file_path="/path/track1.mp3", filename="track1.mp3",
                  existing_title="Track 1", existing_artist="Artist"),
        ]

        call_log = []

        def mock_claude(prompt, batch):
            call_log.append("claude")
            return True, '[{"index": 0, "genre": "Salsa", "subgenre": "Unknown", "confidence": 90, "reasoning": "a"}, {"index": 1, "genre": "Salsa", "subgenre": "Unknown", "confidence": 90, "reasoning": "b"}]'

        def mock_gemini(prompt, batch):
            call_log.append("gemini")
            return True, '[]'

        monkeypatch.setattr("app.services.classifier._classify_with_claude", mock_claude)
        monkeypatch.setattr("app.services.classifier._classify_with_gemini", mock_gemini)

        os.environ["AI_MODEL"] = "claude"
        os.environ["CLASSIFY_BATCH_SIZE"] = "10"
        try:
            result = classify_tracks(tracks, taxonomy, force=True)
        finally:
            os.environ.pop("AI_MODEL", None)
            os.environ.pop("CLASSIFY_BATCH_SIZE", None)

        assert call_log == ["claude"], f"Gemini should not be called, got {call_log}"
        assert all(t.classification_done for t in result)
        assert all(t.error is None for t in result)

    def test_classify_tracks_empty_response_continues_chain(self, monkeypatch):
        """A model returning empty classifications does not kill the batch —
        the chain continues to the next model."""
        from app.services.classifier import classify_tracks

        taxonomy = {"genres": {"Bachata": {"description": "", "subgenres": {}}}}

        tracks = [
            Track(file_path="/path/track0.mp3", filename="track0.mp3",
                  existing_title="Track 0", existing_artist="Artist"),
        ]

        call_log = []

        def mock_claude(prompt, batch):
            call_log.append("claude")
            return True, 'not valid json at all'

        def mock_gemini(prompt, batch):
            call_log.append("gemini")
            return True, '[{"index": 0, "genre": "Bachata", "subgenre": "Unknown", "confidence": 75, "reasoning": "ok"}]'

        monkeypatch.setattr("app.services.classifier._classify_with_claude", mock_claude)
        monkeypatch.setattr("app.services.classifier._classify_with_gemini", mock_gemini)

        os.environ["AI_MODEL"] = "claude"
        os.environ["CLASSIFY_BATCH_SIZE"] = "10"
        try:
            result = classify_tracks(tracks, taxonomy, force=True)
        finally:
            os.environ.pop("AI_MODEL", None)
            os.environ.pop("CLASSIFY_BATCH_SIZE", None)

        assert call_log == ["claude", "gemini"], f"Expected both models, got {call_log}"
        assert result[0].classification_done
        assert result[0].proposed_genre == "Bachata"
        assert result[0].error is None
