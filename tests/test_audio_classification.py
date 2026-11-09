"""Focused contract tests for the local audio-only classification worker."""
from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
import wave
from dataclasses import replace
from pathlib import Path

import pytest

from app.services.audio_classification import (
    AudioClassificationEngine,
    AudioDecodeError,
    AudioWindow,
    BoundedAudioDecoder,
    DecodedAudio,
    ModelInstaller,
    ModelIntegrityError,
    ModelRegistry,
)


def _wav(path: Path, sample_rate: int = 8_000, seconds: float = 1.2) -> None:
    values = [int(12_000 * math.sin(2 * math.pi * 440 * index / sample_rate))
              for index in range(int(sample_rate * seconds))]
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(b"".join(value.to_bytes(2, "little", signed=True) for value in values))


class _VerifiedInstaller:
    def __init__(self, directory: Path):
        self.directory = directory

    def verify_installed(self, _model_id: str) -> Path:
        return self.directory


class _FakeRunner:
    audio_calls = 0
    text_calls = 0

    def __init__(self, _directory: Path):
        pass

    def embed_audio(self, windows, _sample_rate):
        type(self).audio_calls += 1
        return [[1.0, 0.0] for _ in windows]

    def embed_text(self, prompts):
        type(self).text_calls += 1
        return [[1.0, 0.0] if "salsa" in prompt.lower() else [0.0, 1.0] for prompt in prompts]


def _decoded() -> DecodedAudio:
    from app.services.audio_classification import AudioIdentity
    return DecodedAudio(
        identity=AudioIdentity("source", "pcm", 48_000, 1, 480_000, 10.0, "test"),
        windows=(AudioWindow("w000000000000", 0.0, 10.0, samples=[0.0, 0.1]),),
    )


class _FakeDecoder:
    def decode(self, _path, _spec):
        return _decoded()


class _TwoWindowDecoder:
    def decode(self, _path, _spec):
        decoded = _decoded()
        return DecodedAudio(identity=decoded.identity, windows=(
            AudioWindow("w0", 0.0, 10.0, samples=[0.0]),
            AudioWindow("w1", 10.0, 10.0, samples=[0.0]),
        ))


class _SourceChangingDecoder:
    def decode(self, path, _spec):
        decoded = _decoded()
        from app.services.audio_classification import AudioIdentity
        return DecodedAudio(
            identity=AudioIdentity(str(path), decoded.identity.decoded_pcm_sha256, 48_000, 1, 480_000, 10.0, "test"),
            windows=decoded.windows,
        )


class _FeatureCache:
    def __init__(self):
        self.records = {}

    def get_feature(self, cache_key):
        return self.records.get(cache_key)

    def put_feature(self, record):
        self.records[record["cache_key"]] = dict(record)
        return self.records[record["cache_key"]]


class _DisagreeingRunner(_FakeRunner):
    def embed_audio(self, windows, _sample_rate):
        return [[1.0, 0.0], [0.0, 1.0]][:len(windows)]


def test_decoder_hashes_entire_pcm_and_keeps_bounded_windows(tmp_path):
    audio = tmp_path / "tone.wav"
    _wav(audio, seconds=2.0)
    spec = replace(ModelRegistry().get(), sample_rate_hz=8_000, window_seconds=0.3, max_windows=3)

    decoded = BoundedAudioDecoder(chunk_frames=101).decode(audio, spec)

    assert decoded.identity.source_sha256 == hashlib.sha256(audio.read_bytes()).hexdigest()
    assert decoded.identity.decoded_pcm_sha256
    assert decoded.identity.decoded_frames == 16_000
    assert len(decoded.windows) == 3
    assert decoded.windows[0].start_seconds == 0.0
    assert decoded.windows[-1].start_seconds == pytest.approx(1.7)
    assert all(len(window.samples) <= 2_400 for window in decoded.windows)


def test_tail_audio_change_beyond_first_megabyte_invalidates_decoded_identity(tmp_path):
    audio = tmp_path / "long-tone.wav"
    _wav(audio, sample_rate=48_000, seconds=12.0)
    spec = replace(ModelRegistry().get(), sample_rate_hz=48_000)
    decoder = BoundedAudioDecoder(chunk_frames=4096)
    before = decoder.decode(audio, spec)
    prefix = audio.read_bytes()[:1_048_576]
    with audio.open("r+b") as handle:
        handle.seek(-2, 2)
        handle.write((1).to_bytes(2, "little", signed=True))
    after = decoder.decode(audio, spec)

    assert audio.read_bytes()[:1_048_576] == prefix
    assert after.identity.source_sha256 != before.identity.source_sha256
    assert after.identity.decoded_pcm_sha256 != before.identity.decoded_pcm_sha256


def test_engine_emits_raw_audio_evidence_and_never_auto_approves(tmp_path):
    engine = AudioClassificationEngine(
        installer=_VerifiedInstaller(tmp_path), decoder=_FakeDecoder(), runner_factory=_FakeRunner,
    )
    payload = engine.classify_item("track-7", tmp_path / "ignored.wav").to_service_payload()

    family = payload["axes"]["music_family"]
    assert payload["status"] == "proposed"
    assert payload["reason"] == "audio_only_review_required"
    assert family["status"] == "ready_for_review"
    assert family["candidates"][0]["label_id"] == "salsa"
    assert family["candidates"][0]["raw_score"] == pytest.approx(1.0)
    assert "calibrated_confidence" not in family["candidates"][0]
    assert family["candidates"][0]["evidence"][0]["window_id"] == "w000000000000"
    assert payload["axes"]["style"]["status"] == "experimental_review_only"
    assert payload["feature"]["embedding_dimension"] == 2
    assert payload["feature"]["cache_key"] == payload["cache_key"]


def test_calibrated_class_gate_can_abstain_without_losing_raw_evidence(tmp_path):
    calibration = {
        "version": "test", "fit_split": "calibration", "dataset_manifest_sha256": "digest",
        "labels": {"salsa": {"coefficient": 1.0, "intercept": 0.0, "threshold": 0.9}},
    }
    engine = AudioClassificationEngine(installer=_VerifiedInstaller(tmp_path), decoder=_FakeDecoder(),
                                       runner_factory=_FakeRunner, calibration=calibration)
    family = engine.classify_item("track-8", tmp_path / "ignored.wav").to_service_payload()["axes"]["music_family"]

    assert family["status"] == "abstained"
    assert family["reason"] == "below_calibrated_class_gate"
    assert family["candidates"][0]["raw_score"] == pytest.approx(1.0)
    assert family["candidates"][0]["calibrated_confidence"] == pytest.approx(0.7310585786)


def test_feature_cache_reuses_embedding_for_tag_only_source_identity_change(tmp_path):
    _FakeRunner.audio_calls = 0
    _FakeRunner.text_calls = 0
    cache = _FeatureCache()
    engine = AudioClassificationEngine(installer=_VerifiedInstaller(tmp_path), decoder=_SourceChangingDecoder(),
                                       runner_factory=_FakeRunner, feature_cache=cache)

    first = engine.classify_item("first", tmp_path / "before-tag-edit.wav").to_service_payload()
    text_calls_after_first = _FakeRunner.text_calls
    second = engine.classify_item("second", tmp_path / "after-tag-edit.wav").to_service_payload()

    assert first["identity"]["source_sha256"] != second["identity"]["source_sha256"]
    assert first["cache_key"] == second["cache_key"]
    assert _FakeRunner.audio_calls == 1
    assert _FakeRunner.text_calls == text_calls_after_first
    assert len(cache.records) == 1


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is required for the disposable MP3 fixture")
def test_real_mp3_tag_only_change_keeps_pcm_cache_key(tmp_path):
    from mutagen.id3 import ID3, TIT2
    from mutagen.mp3 import MP3

    audio = tmp_path / "tone.mp3"
    subprocess.run([
        "ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
        "sine=frequency=440:sample_rate=48000:duration=0.5", "-q:a", "5", str(audio),
    ], check=True)
    _FakeRunner.audio_calls = 0
    cache = _FeatureCache()
    engine = AudioClassificationEngine(installer=_VerifiedInstaller(tmp_path), decoder=BoundedAudioDecoder(),
                                       runner_factory=_FakeRunner, feature_cache=cache)

    first = engine.classify_item("before", audio).to_service_payload()
    before_bytes = first["identity"]["source_sha256"]
    tags = MP3(str(audio), ID3=ID3)
    if tags.tags is None:
        tags.add_tags()
    tags.tags["TIT2"] = TIT2(encoding=3, text=["Metadata-only edit"])
    tags.save(v2_version=4)
    second = engine.classify_item("after", audio).to_service_payload()

    assert second["identity"]["source_sha256"] != before_bytes
    assert second["identity"]["decoded_pcm_sha256"] == first["identity"]["decoded_pcm_sha256"]
    assert second["cache_key"] == first["cache_key"]
    assert _FakeRunner.audio_calls == 1


def test_disagreeing_audio_sections_are_retained_for_review(tmp_path):
    engine = AudioClassificationEngine(installer=_VerifiedInstaller(tmp_path), decoder=_TwoWindowDecoder(),
                                       runner_factory=_DisagreeingRunner)
    family = engine.classify_item("sections", tmp_path / "ignored.wav").to_service_payload()["axes"]["music_family"]

    assert family["status"] == "ready_for_review"
    assert family["reason"] == "sections_disagree"
    assert {item["label_id"] for item in family["window_top_labels"]} == {"salsa", "bachata"}


def test_silent_audio_abstains_before_the_model_is_loaded(tmp_path):
    audio = tmp_path / "silent.wav"
    with wave.open(str(audio), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8_000)
        handle.writeframes(b"\0\0" * 8_000)

    result = AudioClassificationEngine().classify_item("silent", audio).to_service_payload()

    assert result["status"] == "abstained"
    assert result["reason"].startswith("audio_silent:")


def test_worker_returns_a_persistable_failure_for_unreadable_audio(tmp_path):
    result = AudioClassificationEngine().classify_item("track-9", tmp_path / "missing.wav").to_service_payload()

    assert result["status"] == "failed"
    assert result["reason"].startswith("audio_decode_failed:")


def test_installed_model_manifest_checks_all_required_assets(tmp_path):
    registry = ModelRegistry()
    spec = registry.get()
    installer = ModelInstaller(registry=registry, root=tmp_path)
    target = installer.model_dir(spec)
    target.mkdir(parents=True)
    files = {}
    for name in spec.required_files:
        item = target / name
        item.write_bytes(name.encode())
        files[name] = hashlib.sha256(name.encode()).hexdigest()
    (target / "installed-manifest.json").write_text(json.dumps({
        "revision": spec.revision, "license": spec.license, "files": files,
    }), encoding="utf-8")

    assert installer.verify_installed() == target
    (target / spec.required_files[0]).write_bytes(b"changed")
    with pytest.raises(ModelIntegrityError, match="checksum"):
        installer.verify_installed()
