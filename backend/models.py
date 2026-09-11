"""Only curated model IDs are eligible for download; inference never downloads."""
import hashlib
import json
from .storage import DATA, atomic_json

ADMITTED_REVISIONS={
 'portrait':'82a4fa6735ca58432b6ce39301b4b9ee066dea47',
 'portrait_lips':'3ef28bc5cff08c90ad8178a25f1b570cd800170f',
 'portrait_vae':'31f26fdeee1355a5c34592e401dd41e45d25a493',
 'portrait_whisper':'169d4a4341b33bc18d8881c4b69c2e104e1cc0af',
}

CATALOG = {
 'portrait_detector':{'repo':'opencv/opencv_zoo','label':'YuNet face detector','license':'MIT','approx_gb':.001,'patterns':[]},
 'portrait':{'repo':'KlingTeam/LivePortrait','label':'Live portrait · photo animation','license':'MIT','approx_gb':.6,'patterns':['README.md','LICENSE*','liveportrait/base_models/*.pth','liveportrait/retargeting_models/*.pth']},
 'portrait_lips':{'repo':'TMElyralab/MuseTalk','label':'MuseTalk 1.5','license':'creativeml-openrail-m','approx_gb':3.5,'patterns':['README.md','LICENSE*','musetalkV15/musetalk.json','musetalkV15/unet.pth']},
 'portrait_vae':{'repo':'stabilityai/sd-vae-ft-mse','label':'Portrait VAE','license':'MIT','approx_gb':.4,'patterns':['README.md','LICENSE*','config.json','diffusion_pytorch_model.safetensors']},
 'portrait_whisper':{'repo':'openai/whisper-tiny','label':'Portrait audio encoder','license':'Apache-2.0','approx_gb':.2,'patterns':['README.md','LICENSE*','config.json','preprocessor_config.json','model.safetensors']},
 'reconstruction': {'repo':'stabilityai/TripoSR', 'label':'TripoSR · experimental image reconstruction', 'license':'MIT', 'approx_gb':1.7, 'patterns':['config.yaml','model.ckpt','README.md','LICENSE*']},
 'dino_config': {'repo':'facebook/dino-vitb16', 'label':'DINO architecture configuration', 'license':'Apache-2.0', 'approx_gb':0.001, 'patterns':['config.json','README.md','LICENSE*']},
 'stt': {'repo':'Systran/faster-whisper-base', 'label':'Whisper Base', 'license':'MIT', 'approx_gb':0.15, 'patterns':['*.json','*.txt','*.bin','README.md','LICENSE*']},
 'chat': {'repo':'Qwen/Qwen3-1.7B', 'label':'Qwen3 1.7B', 'license':'Apache-2.0', 'approx_gb':3.5, 'patterns':['*.json','*.txt','*.safetensors','*.model','*.tiktoken','README.md','LICENSE*']},
 'tts': {'repo':'Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice', 'label':'Qwen3 TTS 1.7B · expressive', 'license':'Apache-2.0', 'approx_gb':4.5, 'patterns':['*.json','*.txt','*.safetensors','*.model','*.tiktoken','README.md','LICENSE*']},
}

def verify(stage, *, hashes=False, dependencies=True):
    """Check local installation without network access or loading model weights.

    Status polling checks sizes; explicit offline verification also checks SHA256.
    """
    if stage not in CATALOG:
        return {'stage':stage, 'valid':False, 'errors':['Unknown model']}
    folder = (DATA / 'models' / stage).resolve()
    errors=[]
    try:
        receipt=json.loads((folder/'receipt.json').read_text(encoding='utf-8'))
        item=CATALOG[stage]
        if receipt.get('repo')!=item['repo'] or receipt.get('license')!=item['license']:
            raise ValueError('Receipt does not match the admitted model')
        files=receipt.get('files')
        if not isinstance(files,list) or not files:
            raise ValueError('Receipt has no files')
        for entry in files:
            relative=entry['path']
            path=(folder/relative).resolve()
            if not path.is_relative_to(folder) or path==folder:
                raise ValueError('Receipt contains an invalid file path')
            if not path.is_file() or path.stat().st_size!=entry['bytes']:
                errors.append(f'Missing or incomplete file: {relative}')
                continue
            if hashes:
                digest=hashlib.sha256()
                with path.open('rb') as handle:
                    for chunk in iter(lambda:handle.read(8*1024*1024),b''):
                        digest.update(chunk)
                if digest.hexdigest()!=entry['sha256']:
                    errors.append(f'Checksum mismatch: {relative}')
    except (OSError,ValueError,KeyError,TypeError,AttributeError) as exc:
        errors.append(f'Invalid or missing receipt: {exc}')
    if stage=='reconstruction':
        dependency=verify('dino_config',hashes=hashes)
        errors.extend(f'DINO configuration: {error}' for error in dependency['errors'])
    if stage=='portrait' and dependencies:
        for dependency in ('portrait_lips','portrait_vae','portrait_whisper','portrait_detector'):
            errors.extend(f'{dependency}: {error}' for error in verify(dependency,hashes=hashes)['errors'])
    return {'stage':stage, 'valid':not errors, 'errors':errors, 'checksums_checked':hashes}

def ready(stage):
    return verify(stage)['valid']

def catalog():
    items=[dict(id=k, **{n:v for n,v in c.items() if n!='patterns'}, installed=ready(k)) for k,c in CATALOG.items() if k!='dino_config' and not k.startswith('portrait_')]
    for item in items:
        if item['id']=='portrait':item.update(approx_gb=4.7,license='MIT / Apache + MuseTalk OpenRAIL (separate terms)')
    return items

def install(stage):
    # This function is invoked only by an explicit setup action, never inference.
    if stage=='portrait_detector':
        from .portrait_detector import install as install_detector
        return install_detector()
    import os
    import shutil
    os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
    from huggingface_hub import HfApi
    if stage=='reconstruction':install('dino_config')
    if stage=='portrait':
        for dependency in ('portrait_lips','portrait_vae','portrait_whisper','portrait_detector'):
            if not ready(dependency):install(dependency)
    item = CATALOG[stage]
    folder = DATA / 'models' / stage
    (folder / 'receipt.json').unlink(missing_ok=True)
    lockfile = DATA / 'models' / 'sources.lock.json'
    lock = json.loads(lockfile.read_text()) if lockfile.exists() else {}
    info = HfApi().model_info(item['repo'], revision=lock.get(stage,ADMITTED_REVISIONS.get(stage)), files_metadata=True)
    if info.card_data is None or info.card_data.get('license','').lower() != item['license'].lower():
        raise ValueError('Model card license differs from the admitted license; review required')
    if shutil.disk_usage(DATA).free < int(item['approx_gb'] * 2.2 * 1024**3):
        raise ValueError('Insufficient free disk space for this model and download staging')
    lock[stage]=info.sha
    atomic_json(lockfile,lock)
    folder.mkdir(parents=True,exist_ok=True)
    # Some corporate proxies strip Hugging Face HEAD metadata. Use the same
    # pinned official URLs and verify GET bytes against Hub git/LFS hashes.
    import fnmatch
    import httpx
    from urllib.parse import quote
    def digest_file(path,lfs=False):
        h=hashlib.sha256() if lfs else hashlib.sha1(f'blob {path.stat().st_size}\0'.encode())
        with path.open('rb') as f:
            for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
        return h.hexdigest()
    with httpx.Client(follow_redirects=True,timeout=120) as client:
        for entry in info.siblings:
            if not any(fnmatch.fnmatch(entry.rfilename,p) for p in item['patterns']):continue
            path=folder/entry.rfilename
            if not path.resolve().is_relative_to(folder.resolve()):raise ValueError('Invalid model artifact path')
            expected=entry.lfs.sha256 if entry.lfs else entry.blob_id
            if path.is_file() and digest_file(path,bool(entry.lfs))==expected:continue
            path.parent.mkdir(parents=True,exist_ok=True)
            partial=path.with_suffix(path.suffix+'.partial')
            offset=partial.stat().st_size if partial.exists() else 0
            url=f"https://huggingface.co/{item['repo']}/resolve/{info.sha}/{quote(entry.rfilename,safe='/')}"
            print(f'Downloading {stage}/{entry.rfilename}',flush=True)
            with client.stream('GET',url,headers={'Range':f'bytes={offset}-'} if offset else {}) as response:
                response.raise_for_status()
                append=offset>0 and response.status_code==206 and response.headers.get('content-range','').startswith(f'bytes {offset}-')
                with partial.open('ab' if append else 'wb') as handle:
                    for chunk in response.iter_bytes(1024*1024):handle.write(chunk)
            if digest_file(partial,bool(entry.lfs))!=expected:raise ValueError(f'Checksum mismatch: {entry.rfilename}')
            os.replace(partial,path)
    files=[]
    for entry in info.siblings:
        path=folder / entry.rfilename
        if not path.is_file(): continue
        sha=hashlib.sha256()
        git=hashlib.sha1(f'blob {path.stat().st_size}\0'.encode())
        with path.open('rb') as handle:
            for chunk in iter(lambda: handle.read(8*1024*1024), b''):
                sha.update(chunk);git.update(chunk)
        digest=sha.hexdigest()
        lfs=entry.lfs
        expected=lfs.sha256 if lfs else entry.blob_id
        actual=digest if lfs else git.hexdigest()
        if not expected or actual != expected:
            raise ValueError(f'Integrity verification failed: {entry.rfilename}')
        files.append({'path':entry.rfilename,'sha256':digest,'bytes':path.stat().st_size})
    if not any('license' in f['path'].lower() for f in files):
        # These official model cards explicitly identify the license. Preserve
        # the card AND its upstream license text; do not mistake a missing
        # standalone LICENSE filename for a missing license declaration.
        sources={'stt':'https://raw.githubusercontent.com/openai/whisper/main/LICENSE',
                 'portrait':'https://raw.githubusercontent.com/KlingAIResearch/LivePortrait/main/LICENSE',
                 'portrait_lips':'https://raw.githubusercontent.com/CompVis/stable-diffusion/main/LICENSE',
                 'portrait_vae':'https://raw.githubusercontent.com/CompVis/latent-diffusion/main/LICENSE',
                 'portrait_whisper':'https://raw.githubusercontent.com/huggingface/transformers/main/LICENSE',
                 'tts':'https://raw.githubusercontent.com/QwenLM/Qwen3-TTS/main/LICENSE',
                 'dino_config':'https://raw.githubusercontent.com/facebookresearch/dino/main/LICENSE',
                 'trellis2':'https://raw.githubusercontent.com/microsoft/TRELLIS.2/main/LICENSE',
                 'trellis_hd':'https://raw.githubusercontent.com/microsoft/TRELLIS.2/main/LICENSE',
                 'trellis_ss':'https://raw.githubusercontent.com/microsoft/TRELLIS/main/LICENSE',
                 'reconstruction':'https://raw.githubusercontent.com/VAST-AI-Research/TripoSR/107cefdc244c39106fa830359024f6a2f1c78871/LICENSE'}
        if stage not in sources:raise ValueError('No license evidence source configured')
        with httpx.Client(follow_redirects=True,timeout=30) as client:
            response=client.get(sources[stage]);response.raise_for_status()
        text=response.text
        marker={'MIT':'MIT License','Apache-2.0':'Apache License','creativeml-openrail-m':'CreativeML Open RAIL-M'}[item['license']]
        if marker not in text:raise ValueError('Unexpected upstream license text')
        (folder/'UPSTREAM_LICENSE.txt').write_text(text,encoding='utf-8')
        files.append({'path':'UPSTREAM_LICENSE.txt','sha256':hashlib.sha256((folder/'UPSTREAM_LICENSE.txt').read_bytes()).hexdigest(),'bytes':(folder/'UPSTREAM_LICENSE.txt').stat().st_size,'source':sources[stage]})
    atomic_json(folder/'receipt.json',{'repo':item['repo'],'revision':info.sha,'license':item['license'],'files':files})
    return {'stage':stage,'revision':info.sha,'verified_files':len(files)}

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description='Verify installed model checksums offline; never downloads.')
    parser.add_argument('stage',choices=[*CATALOG,'all'],default='all',nargs='?')
    args=parser.parse_args()
    stages=[k for k in CATALOG if k!='dino_config'] if args.stage=='all' else [args.stage]
    results=[verify(stage,hashes=True) for stage in stages]
    print(json.dumps(results,indent=2))
    raise SystemExit(0 if all(r['valid'] for r in results) else 1)
