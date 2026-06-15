"""Load all heavy resources once at startup."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from tribe_neural.constants import NETWORK_KEYS, NUM_VERTICES

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.environ.get("TRIBE_DATA_DIR", "./data"))


def _get_device() -> str:
    """Return the best available torch device: cuda > mps > cpu.

    Checks pydantic settings first, then TRIBE_DEVICE env var, then auto-detects.
    """
    override = ""
    try:
        from app.config import get_settings
        override = get_settings().tribe_device.strip().lower()
    except Exception:
        pass
    if not override:
        override = os.environ.get("TRIBE_DEVICE", "").strip().lower()
    if override in {"cuda", "mps", "cpu"}:
        return override

    import torch

    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _get_autocast_device() -> str:
    """Return the device name for torch.amp.autocast.

    CPU does not support autocast, so we return "cpu" as a sentinel
    that callers can check to skip the autocast wrapper entirely.
    """
    device = _get_device()
    if device == "cpu":
        return "cpu"
    return device


@dataclass
class Resources:
    """Container for all pre-loaded pipeline resources."""

    model: object  # TribeModel (typed as object to avoid import at module level)
    masks: dict[str, np.ndarray] = field(default_factory=dict)
    weight_maps: dict[str, np.ndarray] = field(default_factory=dict)
    signatures: dict[str, np.ndarray | None] = field(default_factory=dict)
    whisperx_model: object = None  # Warm whisperx ASR model
    whisperx_align_model: object = None  # Warm whisperx alignment model
    whisperx_align_metadata: dict = field(default_factory=dict)


def _build_schaefer_masks() -> dict[str, np.ndarray]:
    """Compute 6 boolean masks from the Schaefer 400-parcel atlas.

    Projects the volumetric atlas to fsaverage5 surface (left + right)
    since the surface-native fetcher was removed in nilearn 0.13.
    """
    from nilearn import datasets
    from nilearn.surface import vol_to_surf

    nilearn_dir = os.environ.get("NILEARN_DATA_DIR", str(DATA_DIR / "nilearn"))
    schaefer = datasets.fetch_atlas_schaefer_2018(
        n_rois=400, resolution_mm=1, data_dir=nilearn_dir,
    )
    fsav = datasets.fetch_surf_fsaverage("fsaverage5", data_dir=nilearn_dir)

    sch_lh = np.rint(vol_to_surf(schaefer["maps"], fsav["pial_left"])).astype(int)
    sch_rh = np.rint(vol_to_surf(schaefer["maps"], fsav["pial_right"])).astype(int)
    sch_full = np.concatenate([sch_lh, sch_rh])
    sch_names = schaefer["labels"]

    def make_network_mask(key: str) -> np.ndarray:
        mask = np.zeros(NUM_VERTICES, dtype=bool)
        for idx, name in enumerate(sch_names):
            if key in str(name):
                mask |= sch_full == idx
        return mask

    masks = {}
    for roi_name, (network_key, _) in NETWORK_KEYS.items():
        masks[roi_name] = make_network_mask(network_key)
        logger.info(
            "Schaefer mask %s: %d vertices", roi_name, masks[roi_name].sum()
        )

    return masks


def _load_weight_maps(data_dir: Path) -> dict[str, np.ndarray]:
    """Load pre-generated NiMARE weight maps from .npz file."""
    path = data_dir / "neurosynth_weights.npz"
    if not path.exists():
        logger.warning("NiMARE weights not found at %s — using empty weights", path)
        return {}

    data = np.load(str(path))
    weight_maps = {key: data[key] for key in data.files}
    logger.info("Loaded NiMARE weights for terms: %s", list(weight_maps.keys()))
    return weight_maps


def _load_signatures(data_dir: Path) -> dict[str, np.ndarray | None]:
    """Load VIFS/PINES surface projections if validated."""
    sigs: dict[str, np.ndarray | None] = {"vifs": None, "pines": None}

    validation_failed = (data_dir / "vifs_validation_failed").exists()
    if validation_failed:
        logger.warning("VIFS validation failed marker found — signatures disabled")
        return sigs

    for name in ("vifs", "pines"):
        path = data_dir / f"{name}_surface.npy"
        if path.exists():
            sigs[name] = np.load(str(path))
            logger.info("Loaded %s signature: shape %s", name, sigs[name].shape)
        else:
            logger.info("Signature %s not found at %s — skipping", name, path)

    return sigs


def _load_whisperx() -> tuple:
    """Load whisperx ASR and alignment models once into GPU memory."""
    if os.environ.get("TRIBE_DISABLE_WHISPERX", "").strip().lower() in {"1", "true", "yes"}:
        raise RuntimeError("WhisperX disabled by TRIBE_DISABLE_WHISPERX")

    import whisperx

    device = _get_device()
    compute_type = "float16" if device in ("cuda", "mps") else "default"

    asr_model = whisperx.load_model(
        "large-v3", device=device, compute_type=compute_type, language="en",
    )
    align_model, align_metadata = whisperx.load_align_model(
        language_code="en", device=device,
        model_name="WAV2VEC2_ASR_LARGE_LV60K_960H",
    )
    return asr_model, align_model, align_metadata


def _patch_whisperx(asr_model: object, align_model: object, align_metadata: dict) -> None:
    """Monkey-patch ExtractWordsFromAudio to use warm whisperx models."""
    import whisperx
    from tribev2.eventstransforms import ExtractWordsFromAudio

    device = _get_device()

    @staticmethod
    def _fast_transcribe(wav_filename, language):
        audio = whisperx.load_audio(str(wav_filename))
        result = asr_model.transcribe(audio, batch_size=16)

        aligned = whisperx.align(
            result["segments"], align_model, align_metadata,
            audio, device=device,
        )

        words = []
        for i, segment in enumerate(aligned["segments"]):
            sentence = segment["text"].replace('"', "")
            for word in segment.get("words", []):
                if "start" not in word:
                    continue
                words.append({
                    "text": word["word"].replace('"', ""),
                    "start": word["start"],
                    "duration": word["end"] - word["start"],
                    "sequence_id": i,
                    "sentence": sentence,
                })

        import pandas as pd
        return pd.DataFrame(words)

    ExtractWordsFromAudio._get_transcript_from_audio = _fast_transcribe
    logger.info("ExtractWordsFromAudio patched to use in-process whisperx")


def _enable_device_optimizations() -> None:
    """Enable platform-specific performance flags for inference."""
    import torch

    device = _get_device()

    if device == "cuda":
        # TF32: ~2-3x faster matmuls with negligible precision loss
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
        # cuDNN benchmark: auto-tune convolution algorithms for this GPU
        torch.backends.cudnn.benchmark = True
        logger.info(
            "CUDA optimizations enabled: TF32 matmul=%s, cuDNN benchmark=%s",
            torch.backends.cuda.matmul.allow_tf32,
            torch.backends.cudnn.benchmark,
        )
    elif device == "mps":
        try:
            torch.mps.empty_cache()
        except Exception:
            pass
        logger.info("MPS device selected for TRIBE inference")
    else:
        logger.info("CPU device selected for TRIBE inference")


def _optimize_tribe_model(model_wrapper: object) -> None:
    """Enable fp16 autocast for TRIBE inference on the active device."""
    import torch

    model = model_wrapper._model
    if model is None:
        return

    autocast_device = _get_autocast_device()
    if autocast_device == "cpu":
        logger.info("TRIBE model running on CPU — autocast skipped")
        return

    # Wrap the forward method with fp16 autocast so inputs are automatically
    # cast — avoids dtype mismatch between fp32 data loader and fp16 model.
    original_forward = model.forward

    @torch.amp.autocast(autocast_device, dtype=torch.float16)
    def autocast_forward(*args, **kwargs):
        return original_forward(*args, **kwargs)

    model.forward = autocast_forward
    logger.info("TRIBE model forward wrapped with fp16 autocast on %s", autocast_device)


def _patch_tts() -> None:
    """Replace gTTS with edge-tts and skip WhisperX for text-only inputs.

    For text_path inference we already know the source text, so instead of
    synthesizing audio and then re-transcribing it with WhisperX, we write the
    original text next to the generated audio and fabricate word timings from
    the text plus audio duration. This keeps the TRIBE text pipeline moving
    without the heavyweight WhisperX runtime.
    """
    import asyncio
    import json
    import re
    import subprocess

    import edge_tts
    import pandas as pd
    from tribev2.demo_utils import TextToEvents, get_audio_and_text_events
    from tribev2.eventstransforms import ExtractWordsFromAudio

    def _audio_duration_seconds(audio_path: Path) -> float:
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "json",
                    str(audio_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(result.stdout or "{}")
            return max(0.1, float(payload.get("format", {}).get("duration", 0.0)))
        except Exception:
            return 0.0

    def _sentence_chunks(text: str) -> list[str]:
        chunks = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text.strip()) if part.strip()]
        return chunks or [text.strip()]

    @staticmethod
    def _transcript_from_sidecar(wav_filename: Path, language: str) -> pd.DataFrame:
        sidecar = Path(str(wav_filename) + ".source.txt")
        if not sidecar.exists():
            raise FileNotFoundError(f"Missing sidecar text file for {wav_filename}")

        text = sidecar.read_text(encoding="utf-8").strip()
        if not text:
            return pd.DataFrame(columns=["text", "start", "duration", "sequence_id", "sentence"])

        duration = _audio_duration_seconds(Path(wav_filename))
        sentences = _sentence_chunks(text)
        all_words: list[dict[str, object]] = []
        flat_words: list[tuple[int, str, str]] = []
        for idx, sentence in enumerate(sentences):
            words = re.findall(r"[A-Za-z0-9'_-]+", sentence)
            for word in words:
                flat_words.append((idx, sentence, word))

        if not flat_words:
            return pd.DataFrame(columns=["text", "start", "duration", "sequence_id", "sentence"])

        per_word = max(duration / len(flat_words), 0.18) if duration > 0 else 0.32
        cursor = 0.0
        for seq_id, sentence, word in flat_words:
            all_words.append(
                {
                    "text": word,
                    "start": round(cursor, 4),
                    "duration": round(per_word, 4),
                    "sequence_id": seq_id,
                    "sentence": sentence,
                }
            )
            cursor += per_word
        return pd.DataFrame(all_words)

    ExtractWordsFromAudio._get_transcript_from_audio = _transcript_from_sidecar
    logger.info("ExtractWordsFromAudio patched to use source-text sidecars for text inputs")

    def get_events(self):
        audio_path = Path(self.infra.uid_folder(create=True)) / "audio.mp3"
        sidecar_path = Path(str(audio_path) + ".source.txt")

        async def _generate():
            communicate = edge_tts.Communicate(self.text, "en-US-AriaNeural")
            await communicate.save(str(audio_path))

        # Run async edge-tts in a sync context.
        # This runs during model loading at startup (never during request handling),
        # so the asyncio.run-in-threadpool pattern is safe here.
        # If called from an async context, uses a separate thread to avoid deadlock.
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                pool.submit(lambda: asyncio.run(_generate())).result()
        else:
            asyncio.run(_generate())

        sidecar_path.write_text(self.text, encoding="utf-8")
        logger.info("Wrote TTS audio to %s (edge-tts)", audio_path)

        audio_event = {
            "type": "Audio",
            "filepath": str(audio_path),
            "start": 0,
            "timeline": "default",
            "subject": "default",
        }
        return get_audio_and_text_events(pd.DataFrame([audio_event]))

    # Replace the inner method inside the exca InfraMethod decorator
    prop = TextToEvents.__dict__["get_events"]
    prop.fget.method = get_events
    logger.info("TextToEvents patched to use edge-tts instead of gTTS")


def load_resources() -> Resources:
    """Load all resources needed by the pipeline.

    Loads TRIBE v2 model (requires HF_TOKEN env var), Schaefer masks,
    NiMARE weight maps, and optionally VIFS/PINES signatures.
    """
    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        raise RuntimeError("HF_TOKEN environment variable is not set")

    # Avoid tokenizer/fork deadlocks once TRIBE builds dataloaders.
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

    # Enable device-specific optimizations before loading any models
    _enable_device_optimizations()

    logger.info("Loading TRIBE v2 model...")
    from tribev2.demo_utils import TribeModel

    device = _get_device()
    logger.info("TRIBE device: %s", device)

    # On Apple Silicon, the text/audio/image/video feature extractors
    # default to "cuda" in the checkpoint config.yaml.  Override them
    # to "cpu" so the Llama embedding model loads without CUDA hooks.
    # The main brain model still runs on the detected device (usually MPS).
    extractor_device = "cpu"
    if device == "cuda":
        extractor_device = "cuda"

    model = TribeModel.from_pretrained(
        "facebook/tribev2",
        cache_folder=str(DATA_DIR / "cache"),
        device=device,
        config_update={
            "data.text_feature.device": extractor_device,
            "data.audio_feature.device": extractor_device,
        },
    )
    logger.info("TRIBE v2 model loaded")

    # Optimize TRIBE model: bf16 + torch.compile
    _optimize_tribe_model(model)

    logger.info("Building Schaefer masks...")
    masks = _build_schaefer_masks()

    logger.info("Loading NiMARE weight maps...")
    weight_maps = _load_weight_maps(DATA_DIR)

    logger.info("Loading signatures...")
    signatures = _load_signatures(DATA_DIR)

    whisperx_model = None
    align_model = None
    align_metadata = {}
    try:
        logger.info("Loading whisperx models (ASR + alignment)...")
        whisperx_model, align_model, align_metadata = _load_whisperx()
        logger.info("whisperx models loaded — monkey-patching ExtractWordsFromAudio")
        _patch_whisperx(whisperx_model, align_model, align_metadata)
    except Exception as exc:
        logger.warning("Skipping whisperx acceleration patch: %s", exc)

    # Replace gTTS with edge-tts
    _patch_tts()

    return Resources(
        model=model,
        masks=masks,
        weight_maps=weight_maps,
        signatures=signatures,
        whisperx_model=whisperx_model,
        whisperx_align_model=align_model,
        whisperx_align_metadata=align_metadata,
    )
