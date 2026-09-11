"""Availability of the explicitly installed, separately licensed visual backend."""
import json
import os
from .storage import DATA,ROOT

from pathlib import Path
PYTHON=Path(os.getenv('PERSONA_VISUAL_PYTHON',str(ROOT/'.venv-trellis'/'Scripts'/'python.exe')))

def available(stages=('trellis2','trellis_ss','dinov3')):
    if not PYTHON.is_file():return False
    for stage in stages:
        folder=(DATA/'models'/stage).resolve()
        try:
            receipt=json.loads((folder/'receipt.json').read_text())
            if not receipt['files']:return False
            for entry in receipt['files']:
                path=(folder/entry['path']).resolve()
                if not path.is_relative_to(folder) or not path.is_file() or path.stat().st_size!=entry['bytes']:return False
        except (OSError,ValueError,KeyError,TypeError,AttributeError):return False
    return True
