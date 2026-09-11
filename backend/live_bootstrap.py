"""Install the module-owned runtime dependencies and licensed model files."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.request import urlretrieve

from huggingface_hub import snapshot_download


DATA = Path(os.environ["PERSONA_DATA"]).resolve()
PYTHON_ROOT = Path(sys.executable).resolve().parent.parent
MODULE_ROOT = PYTHON_ROOT / "modules" / "PersonaLiveView"
SITE_PACKAGES = MODULE_ROOT / "site-packages"
MARKER = MODULE_ROOT / "bootstrap.json"

REQUIREMENTS = [
    "fastapi>=0.141,<0.142",
    "uvicorn>=0.52,<0.53",
    "python-multipart>=0.0.32,<0.0.33",
    "opencv-contrib-python==4.13.0.92",
    "scikit-image==0.26.0",
    "imageio==2.37.2",
    "mediapipe==0.10.32",
    "rich==14.3.3",
]

PORTRAIT_FILES = [
    "README.md",
    "liveportrait/base_models/appearance_feature_extractor.pth",
    "liveportrait/base_models/motion_extractor.pth",
    "liveportrait/base_models/spade_generator.pth",
    "liveportrait/base_models/warping_module.pth",
    "liveportrait/retargeting_models/stitching_retargeting_module.pth",
]

DETECTOR_FILES = {
    "face_detection_yunet_2023mar.onnx": (
        "https://media.githubusercontent.com/media/opencv/opencv_zoo/"
        "47534e27c9851bb1128ccc0102f1145e27f23f98/models/face_detection_yunet/"
        "face_detection_yunet_2023mar.onnx"
    ),
    "LICENSE": (
        "https://raw.githubusercontent.com/opencv/opencv_zoo/"
        "47534e27c9851bb1128ccc0102f1145e27f23f98/models/face_detection_yunet/LICENSE"
    ),
    "README.md": (
        "https://raw.githubusercontent.com/opencv/opencv_zoo/"
        "47534e27c9851bb1128ccc0102f1145e27f23f98/models/face_detection_yunet/README.md"
    ),
}


def _receipt(folder: Path, repo: str, revision: str, files: list[Path]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    entries = []
    for file in files:
        relative = file.relative_to(folder).as_posix()
        with file.open("rb") as stream:
            checksum = hashlib.file_digest(stream, "sha256").hexdigest()
        entries.append(
            {
                "path": relative,
                "sha256": checksum,
                "bytes": file.stat().st_size,
            }
        )
    (folder / "receipt.json").write_text(
        json.dumps({"repo": repo, "revision": revision, "license": "MIT", "files": entries}, indent=2),
        encoding="utf-8",
    )


def _models_ready() -> bool:
    portrait = DATA / "models" / "portrait"
    detector = DATA / "models" / "portrait_detector"
    return all((portrait / path).is_file() for path in PORTRAIT_FILES) and all(
        (detector / path).is_file() for path in DETECTOR_FILES
    )


def _install_dependencies() -> None:
    expected = {"python": sys.version, "requirements": REQUIREMENTS}
    if MARKER.is_file():
        try:
            if json.loads(MARKER.read_text(encoding="utf-8")) == expected:
                return
        except json.JSONDecodeError:
            pass
    SITE_PACKAGES.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--upgrade-strategy",
        "only-if-needed",
        "--target",
        str(SITE_PACKAGES),
        *REQUIREMENTS,
    ]
    subprocess.run(command, check=True)
    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text(json.dumps(expected, indent=2), encoding="utf-8")


def _install_models() -> None:
    if _models_ready():
        return
    portrait = DATA / "models" / "portrait"
    snapshot_download(
        repo_id="KlingTeam/LivePortrait",
        revision="82a4fa6735ca58432b6ce39301b4b9ee066dea47",
        allow_patterns=PORTRAIT_FILES,
        local_dir=portrait,
    )
    _receipt(
        portrait,
        "KlingTeam/LivePortrait",
        "82a4fa6735ca58432b6ce39301b4b9ee066dea47",
        [portrait / path for path in PORTRAIT_FILES],
    )
    detector = DATA / "models" / "portrait_detector"
    detector.mkdir(parents=True, exist_ok=True)
    for relative, url in DETECTOR_FILES.items():
        destination = detector / relative
        if not destination.is_file():
            urlretrieve(url, destination)
    _receipt(
        detector,
        "opencv/opencv_zoo",
        "47534e27c9851bb1128ccc0102f1145e27f23f98",
        [detector / path for path in DETECTOR_FILES],
    )


def main() -> None:
    _install_dependencies()
    _install_models()


if __name__ == "__main__":
    main()
