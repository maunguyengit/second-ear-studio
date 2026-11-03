"""Small, explicit model choices. Downloads occur only after a user setup action."""
import json
import os
import sys
from pathlib import Path

MODELS = {
    "tiny.en": {"label":"English · Quick", "repo":"Systran/faster-whisper-tiny.en", "size":"about 75 MB", "english_only":True},
    "base": {"label":"Multilingual · Balanced", "repo":"Systran/faster-whisper-base", "size":"about 150 MB", "english_only":False},
    "small": {"label":"Multilingual · Detailed", "repo":"Systran/faster-whisper-small", "size":"about 500 MB", "english_only":False},
}
REQUIRED = ("model.bin","config.json","tokenizer.json")
VOCABULARY = ("vocabulary.txt","vocabulary.json")


def bundled_root():
    # PyInstaller stores package resources inside the bundle; wheels do not bundle weights.
    return Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "bundled_models"


def model_path(root, name):
    for candidate in (Path(root)/"models"/name, bundled_root()/name):
        if all((candidate/file).is_file() and (candidate/file).stat().st_size for file in REQUIRED) and any((candidate/file).is_file() for file in VOCABULARY):
            return candidate
    return None


def download(root, name):
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["HF_HOME"] = str(Path(root)/".model-cache")
    os.environ["HF_XET_CACHE"] = str(Path(root)/".model-cache"/"xet")
    import truststore
    truststore.inject_into_ssl()
    from huggingface_hub import snapshot_download
    destination = Path(root)/"models"/name
    destination.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    snapshot_download(MODELS[name]["repo"], local_dir=str(destination), allow_patterns=list(REQUIRED+VOCABULARY), max_workers=2)
    if model_path(root,name) is None:
        raise RuntimeError("The model download is incomplete. Check your connection and try again.")
    (destination/"source.json").write_text(json.dumps({"repository":MODELS[name]["repo"],"source":"Hugging Face public model repository"},indent=2))
