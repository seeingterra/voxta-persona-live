"""Offline validation for the model files used exclusively by Live View."""
import json
from pathlib import Path

from .storage import DATA


LIVE_VIEW_MODELS = {
    "portrait": "KlingTeam/LivePortrait",
    "portrait_detector": "opencv/opencv_zoo",
}


def verify(name: str, *, dependencies: bool = False) -> dict:
    """Validate an installed Live View model receipt without loading its weights."""
    expected_repo = LIVE_VIEW_MODELS.get(name)
    if expected_repo is None:
        return {"valid": False, "errors": ["Unknown Live View model"]}
    folder = (DATA / "models" / name).resolve()
    errors = []
    try:
        receipt = json.loads((folder / "receipt.json").read_text(encoding="utf-8"))
        if receipt.get("repo") != expected_repo:
            raise ValueError("Receipt does not match the required model")
        files = receipt.get("files")
        if not isinstance(files, list) or not files:
            raise ValueError("Receipt has no files")
        for entry in files:
            path = (folder / entry["path"]).resolve()
            if not path.is_relative_to(folder) or path == folder:
                raise ValueError("Receipt contains an invalid file path")
            if not path.is_file() or path.stat().st_size != entry["bytes"]:
                errors.append(f"Missing or incomplete file: {entry['path']}")
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        errors.append(f"Invalid or missing receipt: {error}")
    return {"valid": not errors, "errors": errors}


def ready(name: str) -> bool:
    return verify(name)["valid"]
