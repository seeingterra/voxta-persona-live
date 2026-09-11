"""Local records. User-supplied names are never filesystem paths."""
import json
import os
import re
import uuid
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.getenv('PERSONA_DATA', str(ROOT / 'data'))).resolve()
for name in ('personas', 'assets', 'models', 'logs', 'tmp', 'revisions'):
    (DATA / name).mkdir(parents=True, exist_ok=True)

def identifier(value: str) -> str:
    if not re.fullmatch(r'[a-f0-9]{32}', value):
        raise ValueError('Invalid record identifier')
    return value

def atomic_json(path: Path, value):
    tmp = path.with_suffix('.' + uuid.uuid4().hex + '.tmp')
    try:
        tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)

def read_persona(id: str):
    return json.loads((DATA / 'personas' / f'{identifier(id)}.json').read_text(encoding='utf-8'))

def save_persona(value, id=None):
    id = identifier(id) if id else uuid.uuid4().hex
    path = DATA / 'personas' / f'{id}.json'
    if path.exists():
        old = read_persona(id)
        atomic_json(DATA / 'revisions' / f'{id}-{uuid.uuid4().hex}.json', old)
    record = dict(value, id=id, schema_version=1, updated_at=datetime.now(timezone.utc).isoformat())
    atomic_json(path, record)
    return record

def asset_path(id: str):
    matches = list((DATA / 'assets').glob(identifier(id) + '.*'))
    if len(matches) != 1:
        raise FileNotFoundError('Asset not found')
    return matches[0]
