"""Local, audio-only CLAP candidate runner for the classifier redesign.

This module deliberately owns neither database state nor tag writes.  Callers
persist the service payload and enforce human locks.  CLAP similarities are
rankings; a calibrated probability is emitted only from a supplied, recorded
calibration profile and no result is ever ``auto_ready`` here.
"""
from __future__ import annotations

import hashlib
from importlib.util import find_spec
import json
import math
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence

from app.utils.paths import app_user_dir, atomic_write


RESOURCE_DIR = Path(__file__).resolve().parents[1] / "resources" / "audio_classification"
DEFAULT_MODEL_ID = "laion-clap-htsat-unfused"
MANIFEST_NAME = "installed-manifest.json"
_RUNTIME_MODULES = ("torch", "transformers", "huggingface_hub", "soundfile", "safetensors")


def audio_runtime_status() -> dict[str, Any]:
    """Cheap build capability gate; it neither imports ML code nor downloads."""
    missing = [name for name in _RUNTIME_MODULES if find_spec(name) is None]
    return {
        "available": not missing,
        "missing": missing,
        "reason": None if not missing else "This desktop build does not include local audio classification runtime: " + ", ".join(missing),
    }


class AudioClassificationError(RuntimeError):
    """Base error with a stable service-facing error code."""

    code = "audio_classification_error"


class AudioDecodeError(AudioClassificationError):
    code = "audio_decode_failed"


class AudioSilenceError(AudioClassificationError):
    code = "audio_silent"


class ModelUnavailableError(AudioClassificationError):
    code = "model_unavailable"


class ModelInstallError(AudioClassificationError):
    code = "model_install_failed"


class ModelIntegrityError(AudioClassificationError):
    code = "model_integrity_failed"


class CalibrationError(AudioClassificationError):
    code = "invalid_calibration"


@dataclass(frozen=True)
class ModelSpec:
    id: str
    adapter: str
    repo_id: str
    revision: str
    license: str
    license_url: str
    source_url: str
    feature_version: str
    sample_rate_hz: int
    window_seconds: float
    max_windows: int
    required_files: tuple[str, ...]

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ModelSpec":
        return cls(
            id=str(value["id"]), adapter=str(value["adapter"]), repo_id=str(value["repo_id"]),
            revision=str(value["revision"]), license=str(value["license"]),
            license_url=str(value["license_url"]), source_url=str(value["source_url"]),
            feature_version=str(value["feature_version"]), sample_rate_hz=int(value["sample_rate_hz"]),
            window_seconds=float(value["window_seconds"]), max_windows=int(value["max_windows"]),
            required_files=tuple(str(path) for path in value["required_files"]),
        )


def _read_json(path: Path) -> Any:
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise AudioClassificationError(f"Cannot read audio-classifier resource {path.name}: {exc}") from exc


class ModelRegistry:
    def __init__(self, registry_path: Path | None = None):
        raw = _read_json(registry_path or RESOURCE_DIR / "models.json")
        self._models = {entry["id"]: ModelSpec.from_mapping(entry) for entry in raw["models"]}

    def get(self, model_id: str = DEFAULT_MODEL_ID) -> ModelSpec:
        try:
            return self._models[model_id]
        except KeyError as exc:
            raise ModelUnavailableError(f"Unknown local audio model: {model_id}") from exc


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise AudioClassificationError(f"Cannot read {path.name}: {exc}") from exc
    return digest.hexdigest()


def _git_blob_sha1(path: Path) -> str:
    """Git's object digest for small Hub files which are not LFS objects."""
    try:
        size = path.stat().st_size
        digest = hashlib.sha1(f"blob {size}\0".encode("ascii"))
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise AudioClassificationError(f"Cannot read {path.name}: {exc}") from exc
    return digest.hexdigest()


def _canonical_digest(value: Mapping[str, Any]) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class ModelInstaller:
    """Installs a pinned Hub snapshot into user data and verifies every file.

    The Hub supplies LFS SHA-256 metadata for the exact pinned revision.  It is
    compared with the downloaded bytes before a manifest makes the model usable.
    A partial download remains resumable and is never treated as installed.
    """
    def __init__(self, registry: ModelRegistry | None = None, root: Path | None = None):
        self.registry = registry or ModelRegistry()
        self.root = root or Path(app_user_dir()) / "models" / "audio-classification"

    def model_dir(self, spec: ModelSpec) -> Path:
        return self.root / spec.id / spec.revision

    def verify_installed(self, model_id: str = DEFAULT_MODEL_ID) -> Path:
        spec = self.registry.get(model_id)
        target = self.model_dir(spec)
        manifest_path = target / MANIFEST_NAME
        manifest = _read_json(manifest_path) if manifest_path.exists() else None
        if not isinstance(manifest, dict):
            raise ModelUnavailableError("Local audio model is not installed. Install it from Settings while online.")
        if manifest.get("revision") != spec.revision or manifest.get("license") != spec.license:
            raise ModelIntegrityError("Installed model does not match the pinned registry version.")
        files = manifest.get("files")
        if not isinstance(files, dict) or set(spec.required_files) - set(files):
            raise ModelIntegrityError("Installed model manifest is incomplete.")
        for relative, expected in files.items():
            file_path = target / relative
            if not file_path.is_file() or _sha256_path(file_path) != expected:
                raise ModelIntegrityError(f"Installed model checksum failed: {relative}")
        return target

    def install(self, model_id: str = DEFAULT_MODEL_ID,
                progress: Callable[[str], None] | None = None) -> Path:
        runtime = audio_runtime_status()
        if not runtime["available"]:
            # Do this before the Hub call: a base-only desktop build must not
            # consume disk/bandwidth downloading a checkpoint it cannot run.
            raise ModelUnavailableError(str(runtime["reason"]))
        spec = self.registry.get(model_id)
        try:
            return self.verify_installed(model_id)
        except (ModelUnavailableError, ModelIntegrityError):
            # A missing or corrupt model is repaired below. It never becomes
            # usable until the new snapshot's exact pinned revision is checked.
            pass
        try:
            from huggingface_hub import HfApi, snapshot_download
        except ImportError as exc:
            raise ModelUnavailableError(
                "Local audio runtime is unavailable in this build; install the packaged audio component."
            ) from exc
        target = self.model_dir(spec)
        partial = target.with_name(target.name + ".partial")
        partial.mkdir(parents=True, exist_ok=True)
        if progress:
            progress("Checking the pinned local model manifest")
        try:
            info = HfApi().model_info(spec.repo_id, revision=spec.revision, files_metadata=True)
            if getattr(info, "sha", None) != spec.revision:
                raise ModelIntegrityError("Model host returned a revision other than the pinned registry revision.")
            expected: dict[str, tuple[str, str]] = {}
            for sibling in getattr(info, "siblings", []):
                name = getattr(sibling, "rfilename", None)
                if name not in spec.required_files:
                    continue
                lfs = getattr(sibling, "lfs", None)
                if lfs is not None and getattr(lfs, "sha256", None):
                    expected[name] = ("sha256", lfs.sha256)
                elif getattr(sibling, "blob_id", None):
                    expected[name] = ("git_blob_sha1", sibling.blob_id)
            missing = set(spec.required_files) - set(expected)
            if missing:
                raise ModelIntegrityError("Model host did not provide checksums for: " + ", ".join(sorted(missing)))
            if progress:
                progress("Downloading pinned local audio model")
            snapshot_download(
                repo_id=spec.repo_id, revision=spec.revision, local_dir=str(partial),
                allow_patterns=list(spec.required_files), resume_download=True,
            )
            actual = {relative: _sha256_path(partial / relative) for relative in spec.required_files}
            bad = []
            for name in spec.required_files:
                kind, expected_digest = expected[name]
                observed = actual[name] if kind == "sha256" else _git_blob_sha1(partial / name)
                if observed != expected_digest:
                    bad.append(name)
            if bad:
                raise ModelIntegrityError("Model checksum failed: " + ", ".join(bad))
        except AudioClassificationError:
            raise
        except Exception as exc:
            raise ModelInstallError(f"Could not install the local audio model: {exc}") from exc

        manifest = {
            "model_id": spec.id, "revision": spec.revision, "license": spec.license,
            "source_url": spec.source_url, "files": actual,
        }
        atomic_write(str(partial / MANIFEST_NAME), manifest, indent=2, sort_keys=True)
        if target.exists():
            # Keep corrupt weights recoverable until a user deliberately clears
            # model cache. Model binaries are replaceable cache, never music data.
            quarantine = target.with_name(target.name + f".invalid-{int(time.time())}")
            os.replace(target, quarantine)
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(partial, target)
        if progress:
            progress("Local audio model installed and verified")
        return self.verify_installed(model_id)


@dataclass(frozen=True)
class AudioIdentity:
    source_sha256: str
    decoded_pcm_sha256: str
    sample_rate_hz: int
    channels: int
    decoded_frames: int
    duration_seconds: float
    decoder: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_sha256": self.source_sha256, "decoded_pcm_sha256": self.decoded_pcm_sha256,
            "sample_rate_hz": self.sample_rate_hz, "channels": self.channels,
            "decoded_frames": self.decoded_frames, "duration_seconds": self.duration_seconds,
            "decoder": self.decoder,
        }


@dataclass(frozen=True)
class AudioWindow:
    window_id: str
    start_seconds: float
    duration_seconds: float
    samples: Any = field(repr=False)


@dataclass(frozen=True)
class DecodedAudio:
    identity: AudioIdentity
    windows: tuple[AudioWindow, ...]


def _window_starts(duration: float, window_seconds: float, maximum: int) -> tuple[float, ...]:
    if duration <= window_seconds or maximum <= 1:
        return (0.0,)
    last = max(0.0, duration - window_seconds)
    return tuple(last * index / (maximum - 1) for index in range(maximum))


class BoundedAudioDecoder:
    """Hashes the entire decoded stream but retains only representative windows."""
    def __init__(self, chunk_frames: int = 262_144):
        self.chunk_frames = chunk_frames

    def decode(self, path: str | Path, spec: ModelSpec) -> DecodedAudio:
        try:
            import numpy as np
            import soundfile as sf
        except ImportError as exc:
            raise AudioDecodeError("Audio decoder dependencies are unavailable in this build.") from exc
        audio_path = Path(path)
        if not audio_path.is_file():
            raise AudioDecodeError("Audio file does not exist or is not a regular file.")
        source_sha = _sha256_path(audio_path)
        try:
            info = sf.info(str(audio_path))
            if info.samplerate <= 0 or info.channels <= 0:
                raise AudioDecodeError("Audio file has invalid sample-rate or channel metadata.")
            decoded_digest = hashlib.sha256()
            decoded_frames = 0
            peak = 0.0
            with sf.SoundFile(str(audio_path), "r") as stream:
                while True:
                    block = stream.read(self.chunk_frames, dtype="float32", always_2d=True)
                    if len(block) == 0:
                        break
                    if not np.isfinite(block).all():
                        raise AudioDecodeError("Decoded audio contains non-finite sample values.")
                    canonical = np.asarray(block, dtype="<f4", order="C")
                    decoded_digest.update(canonical.tobytes())
                    decoded_frames += len(canonical)
                    peak = max(peak, float(np.max(np.abs(canonical))))
            if decoded_frames == 0:
                raise AudioDecodeError("Decoded audio has no frames.")
            if peak <= 1e-5:
                raise AudioSilenceError("Decoded audio is silent; no music-family proposal was made.")
            duration = decoded_frames / info.samplerate
            starts = _window_starts(duration, spec.window_seconds, spec.max_windows)
            windows = tuple(self._read_window(audio_path, start, spec, info.samplerate) for start in starts)
        except AudioClassificationError:
            raise
        except Exception as exc:
            raise AudioDecodeError(f"Could not decode audio locally: {exc}") from exc
        identity = AudioIdentity(
            source_sha256=source_sha, decoded_pcm_sha256=decoded_digest.hexdigest(),
            sample_rate_hz=int(info.samplerate), channels=int(info.channels), decoded_frames=decoded_frames,
            duration_seconds=duration, decoder=f"soundfile-{getattr(sf, '__version__', 'unknown')}",
        )
        return DecodedAudio(identity=identity, windows=windows)

    @staticmethod
    def _read_window(path: Path, start_seconds: float, spec: ModelSpec, source_rate: int) -> AudioWindow:
        import numpy as np
        import soundfile as sf
        start_frame = int(start_seconds * source_rate)
        wanted = max(1, int(math.ceil(spec.window_seconds * source_rate)))
        with sf.SoundFile(str(path), "r") as stream:
            stream.seek(start_frame)
            frames = stream.read(wanted, dtype="float32", always_2d=True)
        if len(frames) == 0:
            raise AudioDecodeError("Representative window has no decoded frames.")
        mono = np.asarray(frames, dtype="float32").mean(axis=1)
        samples = BoundedAudioDecoder._resample(mono, source_rate, spec.sample_rate_hz)
        return AudioWindow(
            window_id=f"w{start_frame:012d}", start_seconds=start_frame / source_rate,
            duration_seconds=len(frames) / source_rate, samples=samples,
        )

    @staticmethod
    def _resample(samples: Any, source_rate: int, target_rate: int) -> Any:
        if source_rate == target_rate:
            return samples
        try:
            import librosa
            return librosa.resample(samples, orig_sr=source_rate, target_sr=target_rate, res_type="soxr_hq")
        except Exception as exc:
            raise AudioDecodeError(f"Could not resample audio for the local model: {exc}") from exc


class EmbeddingRunner(Protocol):
    def embed_audio(self, windows: Sequence[AudioWindow], sample_rate_hz: int) -> Sequence[Sequence[float]]: ...
    def embed_text(self, prompts: Sequence[str]) -> Sequence[Sequence[float]]: ...


class FeatureCache(Protocol):
    """Persistence seam owned by the store; cache identity excludes source bytes."""
    def get_feature(self, cache_key: str) -> Mapping[str, Any] | None: ...
    def put_feature(self, record: Mapping[str, Any]) -> Mapping[str, Any]: ...


class TransformersClapRunner:
    """Lazy CPU CLAP adapter; imports no optional ML dependency at app startup."""
    def __init__(self, model_dir: Path):
        self.model_dir = model_dir
        self._model = None
        self._processor = None

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            import torch
            from transformers import AutoProcessor, ClapModel
        except ImportError as exc:
            raise ModelUnavailableError(
                "Local audio runtime is unavailable in this build; install the packaged audio component."
            ) from exc
        try:
            self._processor = AutoProcessor.from_pretrained(str(self.model_dir), local_files_only=True)
            # The pinned artifact currently supplies a PyTorch .bin file. Keep
            # PyTorch's restricted tensor-only loader explicit; do not relax it
            # merely to load an untrusted or older checkpoint.
            self._model = ClapModel.from_pretrained(
                str(self.model_dir), local_files_only=True, weights_only=True
            )
            self._model.to("cpu")
            self._model.eval()
            self._torch = torch
        except Exception as exc:
            raise ModelUnavailableError(f"Local audio model could not be loaded: {exc}") from exc

    def embed_audio(self, windows: Sequence[AudioWindow], sample_rate_hz: int) -> Sequence[Sequence[float]]:
        self._load()
        inputs = self._processor(audio=[window.samples for window in windows], sampling_rate=sample_rate_hz,
                                 return_tensors="pt", padding=True)
        with self._torch.inference_mode():
            values = self._model.get_audio_features(**inputs).cpu().tolist()
        return values

    def embed_text(self, prompts: Sequence[str]) -> Sequence[Sequence[float]]:
        self._load()
        inputs = self._processor(text=list(prompts), return_tensors="pt", padding=True)
        with self._torch.inference_mode():
            values = self._model.get_text_features(**inputs).cpu().tolist()
        return values


def _normalise(vector: Sequence[float]) -> list[float]:
    norm = math.sqrt(sum(float(value) ** 2 for value in vector))
    if norm == 0:
        raise AudioClassificationError("Local model returned a zero-length embedding.")
    return [float(value) / norm for value in vector]


def _mean_embedding(vectors: Sequence[Sequence[float]]) -> list[float]:
    if not vectors:
        raise AudioClassificationError("No audio windows were available for embedding.")
    dimensions = len(vectors[0])
    if not dimensions or any(len(vector) != dimensions for vector in vectors):
        raise AudioClassificationError("Local model returned inconsistent embedding dimensions.")
    return _normalise([sum(float(vector[index]) for vector in vectors) / len(vectors) for index in range(dimensions)])


def _dot(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise AudioClassificationError("Audio and text embedding dimensions differ.")
    return sum(a * b for a, b in zip(_normalise(left), _normalise(right)))


class CalibrationProfile:
    """A recorded per-class Platt profile fitted only on the calibration split."""
    def __init__(self, raw: Mapping[str, Any]):
        if raw.get("fit_split") != "calibration" or not raw.get("dataset_manifest_sha256"):
            raise CalibrationError("Calibration profile must record a calibration-only dataset manifest.")
        self.version = str(raw.get("version", "unknown"))
        self.labels = raw.get("labels")
        if not isinstance(self.labels, Mapping):
            raise CalibrationError("Calibration profile has no per-class parameters.")

    def confidence(self, label_id: str, raw_score: float) -> float | None:
        params = self.labels.get(label_id)
        if not isinstance(params, Mapping):
            return None
        try:
            logit = float(params["coefficient"]) * raw_score + float(params["intercept"])
        except (KeyError, TypeError, ValueError) as exc:
            raise CalibrationError(f"Invalid calibration values for {label_id}") from exc
        return 1.0 / (1.0 + math.exp(-max(-60.0, min(60.0, logit))))

    def threshold(self, label_id: str) -> float | None:
        params = self.labels.get(label_id)
        if not isinstance(params, Mapping) or "threshold" not in params:
            return None
        return float(params["threshold"])


@dataclass(frozen=True)
class AudioClassificationResult:
    item_id: str
    status: str
    reason: str | None
    identity: AudioIdentity | None
    cache_key: str | None
    model: Mapping[str, Any] | None
    feature_version: str | None
    axes: Mapping[str, Any]
    embedding: tuple[float, ...] | None = field(default=None, repr=False)

    def to_service_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "item_id": self.item_id, "status": self.status, "reason": self.reason,
            "identity": self.identity.as_dict() if self.identity else None, "cache_key": self.cache_key,
            "model": dict(self.model) if self.model else None, "feature_version": self.feature_version,
            "axes": self.axes,
        }
        if self.embedding is not None:
            vector = list(self.embedding)
            payload["feature"] = {
                "embedding": vector, "embedding_dimension": len(vector),
                "embedding_sha256": _canonical_digest({"embedding": vector}),
                "aggregation": "mean_l2_normalized_representative_windows",
                "cache_key": self.cache_key,
            }
        return payload


class AudioClassificationEngine:
    """Service-facing local inference engine with bounded decode and one model runner."""
    def __init__(self, registry: ModelRegistry | None = None, installer: ModelInstaller | None = None,
                 decoder: BoundedAudioDecoder | None = None, runner_factory: Callable[[Path], EmbeddingRunner] | None = None,
                 labels_path: Path | None = None, calibration: Mapping[str, Any] | None = None,
                 feature_cache: FeatureCache | None = None):
        self.registry = registry or ModelRegistry()
        self.installer = installer or ModelInstaller(self.registry)
        self.decoder = decoder or BoundedAudioDecoder()
        self.runner_factory = runner_factory or TransformersClapRunner
        self.labels = _read_json(labels_path or RESOURCE_DIR / "labels.json")
        self.calibration = CalibrationProfile(calibration) if calibration else None
        self._runners: dict[str, EmbeddingRunner] = {}
        self._model_dirs: dict[str, Path] = {}
        self._text_embeddings: dict[tuple[str, tuple[str, ...]], Sequence[Sequence[float]]] = {}
        self.feature_cache = feature_cache

    def classify_item(self, item_id: str, path: str | Path, model_id: str = DEFAULT_MODEL_ID) -> AudioClassificationResult:
        try:
            return self._classify(item_id, Path(path), model_id)
        except AudioSilenceError as exc:
            return AudioClassificationResult(item_id=item_id, status="abstained", reason=f"{exc.code}: {exc}",
                                             identity=None, cache_key=None, model=None, feature_version=None, axes={})
        except AudioClassificationError as exc:
            return AudioClassificationResult(item_id=item_id, status="failed", reason=f"{exc.code}: {exc}",
                                             identity=None, cache_key=None, model=None, feature_version=None, axes={})
        except Exception as exc:  # boundary: workers persist failure and continue the next item
            return AudioClassificationResult(item_id=item_id, status="failed", reason=f"audio_classification_error: {exc}",
                                             identity=None, cache_key=None, model=None, feature_version=None, axes={})

    def _classify(self, item_id: str, path: Path, model_id: str) -> AudioClassificationResult:
        spec = self.registry.get(model_id)
        decoded = self.decoder.decode(path, spec)
        cache_key = _canonical_digest({
            # Source SHA guards file writes but must not defeat a verified
            # tag-only/container change reusing identical decoded audio.
            "decoded_audio": {
                "decoded_pcm_sha256": decoded.identity.decoded_pcm_sha256,
                "sample_rate_hz": decoded.identity.sample_rate_hz, "channels": decoded.identity.channels,
                "decoded_frames": decoded.identity.decoded_frames, "decoder": decoded.identity.decoder,
            }, "model_id": spec.id, "model_revision": spec.revision,
            "feature_version": spec.feature_version, "sample_rate_hz": spec.sample_rate_hz,
            "window_seconds": spec.window_seconds, "max_windows": spec.max_windows,
        })
        cached = self.feature_cache.get_feature(cache_key) if self.feature_cache else None
        if self._valid_feature(cached, decoded, spec):
            embedding = [float(value) for value in cached["embedding"]]
            per_window_embeddings = cached["window_embeddings"]
        else:
            runner = self._runner(model_id)
            per_window_embeddings = runner.embed_audio(decoded.windows, spec.sample_rate_hz)
            embedding = _mean_embedding(per_window_embeddings)
            if self.feature_cache:
                self.feature_cache.put_feature({
                    "cache_key": cache_key, "decoded_pcm_sha256": decoded.identity.decoded_pcm_sha256,
                    "sample_rate_hz": decoded.identity.sample_rate_hz, "channels": decoded.identity.channels,
                    "decoded_frames": decoded.identity.decoded_frames, "decoder": decoded.identity.decoder,
                    "model_id": spec.id, "model_revision": spec.revision, "feature_version": spec.feature_version,
                    "preprocessing": {"sample_rate_hz": spec.sample_rate_hz, "window_seconds": spec.window_seconds,
                                      "max_windows": spec.max_windows},
                    "embedding": embedding, "window_embeddings": per_window_embeddings,
                })
        axes = self._score_axes(model_id, aggregate=embedding, window_embeddings=per_window_embeddings, windows=decoded.windows)
        model = {"id": spec.id, "revision": spec.revision, "license": spec.license, "source_url": spec.source_url}
        return AudioClassificationResult(item_id=item_id, status="proposed", reason="audio_only_review_required",
                                         identity=decoded.identity, cache_key=cache_key, model=model,
                                         feature_version=spec.feature_version, axes=axes,
                                         embedding=tuple(embedding))

    def _runner(self, model_id: str) -> EmbeddingRunner:
        if model_id not in self._runners:
            # Full manifests are rehashed once per worker, not once per track.
            self._model_dirs[model_id] = self.installer.verify_installed(model_id)
            self._runners[model_id] = self.runner_factory(self._model_dirs[model_id])
        return self._runners[model_id]

    @staticmethod
    def _valid_feature(record: Mapping[str, Any] | None, decoded: DecodedAudio, spec: ModelSpec) -> bool:
        if not isinstance(record, Mapping):
            return False
        expected = (record.get("decoded_pcm_sha256") == decoded.identity.decoded_pcm_sha256
                    and record.get("sample_rate_hz") == decoded.identity.sample_rate_hz
                    and record.get("channels") == decoded.identity.channels
                    and record.get("decoded_frames") == decoded.identity.decoded_frames
                    and record.get("decoder") == decoded.identity.decoder
                    and record.get("model_id") == spec.id and record.get("model_revision") == spec.revision
                    and record.get("feature_version") == spec.feature_version
                    and record.get("preprocessing") == {"sample_rate_hz": spec.sample_rate_hz,
                                                        "window_seconds": spec.window_seconds,
                                                        "max_windows": spec.max_windows})
        embeddings = record.get("window_embeddings")
        return bool(expected and isinstance(record.get("embedding"), Sequence)
                    and isinstance(embeddings, Sequence) and len(embeddings) == len(decoded.windows))

    def _score_axes(self, model_id: str, aggregate: Sequence[float], window_embeddings: Sequence[Sequence[float]],
                    windows: Sequence[AudioWindow]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        configured_axes = [(name, axis, False) for name, axis in self.labels["axes"].items()]
        configured_axes.extend((name, axis, True) for name, axis in self.labels.get("experimental_axes", {}).items())
        for axis_name, axis, experimental in configured_axes:
            labels = axis["candidates"]
            prompts = [prompt for label in labels for prompt in label["prompts"]]
            cache_key = (model_id, tuple(prompts))
            if cache_key not in self._text_embeddings:
                self._text_embeddings[cache_key] = self._runner(model_id).embed_text(prompts)
            text_embeddings = iter(self._text_embeddings[cache_key])
            candidates = []
            for label in labels:
                label_embeddings = [next(text_embeddings) for _ in label["prompts"]]
                raw_score = max(_dot(aggregate, vector) for vector in label_embeddings)
                evidence = []
                for window, window_embedding in zip(windows, window_embeddings):
                    evidence.append({"window_id": window.window_id, "start_seconds": window.start_seconds,
                                     "duration_seconds": window.duration_seconds,
                                     "raw_score": max(_dot(window_embedding, vector) for vector in label_embeddings)})
                confidence = self.calibration.confidence(label["id"], raw_score) if self.calibration else None
                candidate: dict[str, Any] = {"label_id": label["id"], "raw_score": raw_score, "evidence": evidence}
                if confidence is not None:
                    candidate["calibrated_confidence"] = confidence
                candidates.append(candidate)
            candidates.sort(key=lambda candidate: candidate["raw_score"], reverse=True)
            selected = candidates[0] if candidates else None
            window_top_labels = []
            for window, window_embedding in zip(windows, window_embeddings):
                window_top = max(
                    labels,
                    key=lambda label: max(_dot(window_embedding, text) for text in (
                        self._text_embeddings[cache_key][prompts.index(prompt)] for prompt in label["prompts"]
                    )),
                )
                window_top_labels.append({"window_id": window.window_id, "label_id": window_top["id"]})
            disagreement = len({item["label_id"] for item in window_top_labels}) > 1
            threshold = self.calibration.threshold(selected["label_id"]) if self.calibration and selected else None
            negative = selected and selected["label_id"] in set(axis.get("negative_label_ids", []))
            if experimental:
                status, reason = "experimental_review_only", "experimental_zero_shot_not_a_certified_head"
            elif negative:
                status, reason = "unsupported", "outside_enabled_music_family"
            elif threshold is not None and selected.get("calibrated_confidence", 0.0) < threshold:
                status, reason = "abstained", "below_calibrated_class_gate"
            elif disagreement:
                status, reason = "ready_for_review", "sections_disagree"
            else:
                status, reason = "ready_for_review", "raw_similarity_is_not_auto_approval"
            result[axis_name] = {"status": status, "reason": reason, "candidates": candidates,
                                 "window_top_labels": window_top_labels, "definition": axis.get("definition")}
        for axis_name, reason in self.labels.get("unsupported_axes", {}).items():
            if axis_name not in result:
                result[axis_name] = {"status": "unsupported", "reason": reason, "candidates": []}
        return result
