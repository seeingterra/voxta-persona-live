import csv
import io
import subprocess
import ctypes
import sys

def detect():
    gpus, warning = [], None
    try:
        result = subprocess.run(['nvidia-smi', '--query-gpu=index,name,uuid,memory.total,memory.free,driver_version', '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=5, creationflags=0x08000000 if sys.platform == 'win32' else 0)
        result.check_returncode()
        for r in csv.reader(io.StringIO(result.stdout)):
            gpus.append(dict(index=int(r[0]), name=r[1].strip(), uuid=r[2].strip(), total_mb=int(r[3]), free_mb=int(r[4]), driver=r[5].strip()))
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        warning = f'GPU detection unavailable: {type(e).__name__}; CPU remains available.'
    return {'gpus':gpus, 'warning':warning, 'platform':sys.platform}

def plan(gpus, overrides=None):
    overrides = overrides or {}
    ordered = sorted(gpus, key=lambda g:g['total_mb'], reverse=True)
    # Reserve display headroom; keep inference workers on separate physical cards.
    devices = {'chat':'cpu', 'tts':'cpu', 'stt':'cpu'}
    if ordered and ordered[0]['free_mb'] >= 5500:
        devices['chat'] = ordered[0]['uuid']
    if len(ordered)>1 and ordered[1]['free_mb'] >= 5500:
        devices['tts'] = ordered[1]['uuid']
    elif ordered and ordered[0]['free_mb'] >= 11500:
        devices['tts'] = ordered[0]['uuid']
    valid = {'cpu', *(g['uuid'] for g in gpus)}
    for stage, device in overrides.items():
        if stage not in devices or (device != 'auto' and device not in valid):
            raise ValueError('Selected compute device is not currently available')
        if device != 'auto':
            devices[stage] = device
    return devices
