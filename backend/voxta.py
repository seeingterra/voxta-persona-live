"""Loopback-only Voxta companion bridge. Voxta owns conversation and providers."""
import asyncio
import base64
import io
import json
import os
import re
import secrets
import time
import uuid
from urllib.parse import urlparse,unquote
import httpx
from fastapi import APIRouter,WebSocket,WebSocketDisconnect,UploadFile,File,HTTPException
from fastapi.responses import Response,FileResponse
from pydantic import BaseModel,Field
from PIL import Image
from .storage import DATA,ROOT,asset_path,atomic_json
from .hardware import detect, select_live_device
from .inference import Worker
from .optional_visual import PYTHON

router=APIRouter(prefix='/api/voxta')
BASE=os.getenv('PERSONA_VOXTA_URL','http://localhost:5384').rstrip('/')
ID=r'[a-fA-F0-9-]{36}'
BINDINGS=DATA/'voxta-characters.json'
live=Worker('portrait','cpu',python=PYTHON,module='backend.live_worker',timeout=30)
live_session=asyncio.Lock()


@router.get('/addon/{name}')
async def addon_asset(name:str):
    if name not in {'live-view.js','live-view.css','adapter.json'}:raise HTTPException(404)
    return FileResponse(ROOT/'addon/voxta-live-view'/name)


@router.get('/matte/{image_id}')
async def matte(image_id:str):
    path=asset_path(image_id)
    if path.suffix!='.png':raise ValueError('Use an image reference')
    source=Image.open(path).convert('RGBA');source.thumbnail((960,960),Image.Resampling.LANCZOS)
    result=Image.new('RGBA',source.size,(255,255,255,255));result.putalpha(source.getchannel('A'))
    output=io.BytesIO();result.save(output,format='PNG')
    return Response(output.getvalue(),media_type='image/png')


def media_path(value):
    parsed=urlparse(value)
    if parsed.scheme and (parsed.scheme!='http' or parsed.hostname not in {'localhost','127.0.0.1'} or parsed.port!=urlparse(BASE).port):raise ValueError('Only media from the local Voxta server is allowed')
    decoded=unquote(unquote(parsed.path))
    if parsed.netloc and not parsed.scheme:raise ValueError('Invalid media address')
    if '\\' in decoded or '..' in decoded.split('/') or not re.match(r'^/api/(characters|scenarios|packages|audio|chats|speech)/',decoded):raise ValueError('Unsupported Voxta media path')
    return parsed.path+('?' + parsed.query if parsed.query else '')


async def get(path):
    async with httpx.AsyncClient(base_url=BASE,trust_env=False,timeout=15) as client:
        result=await client.get(path)
        if result.status_code in (401,403):raise HTTPException(401,'Sign in to your local Voxta server first.')
        result.raise_for_status();return result.json()


def bindings():
    return json.loads(BINDINGS.read_text(encoding='utf-8')) if BINDINGS.exists() else {}


@router.get('/status')
async def status():
    try:
        definitions=(await get('/api/modules-definitions'))['definitions']
        return {'connected':True,'url':BASE,'modules':[{k:d.get(k) for k in ('serviceName','label','supports','serviceCount','notes','pricing','hosting')} for d in definitions], 'live_loaded':bool(live.process and live.process.returncode is None)}
    except httpx.HTTPError:return {'connected':False,'url':BASE,'modules':[],'message':'Start Voxta.Server.exe in the Voxta folder.'}


@router.get('/hardware')
def hardware():
    return detect()


@router.get('/usage')
def usage():
    return live.usage()


@router.get('/characters')
async def characters():
    records=(await get('/api/characters/'))['characters'];saved=bindings()
    return [{'id':c['id'],'name':c['name'],'thumbnail':c.get('thumbnailUrl'),'image_id':saved.get(c['id'],{}).get('image_id')} for c in records]


class Binding(BaseModel):
    image_id:str|None=Field(default=None,pattern=r'^[a-f0-9]{32}$')


class NativeReference(BaseModel):
    path:str=Field(default='',max_length=2000)
    image_data:str|None=Field(default=None,max_length=34*1024*1024)


@router.post('/native-reference')
async def native_reference(value:NativeReference):
    """Import precisely the avatar chosen by Voxta, including mood overrides."""
    import hashlib
    if value.image_data:
        if value.path:raise ValueError('Supply one image source')
        if not re.match(r'^data:image/(png|jpeg|webp);base64,',value.image_data):raise ValueError('Use PNG, JPEG or WebP image data')
        raw=base64.b64decode(value.image_data.split(',',1)[1],validate=True)
    else:
        path=media_path(value.path)
        if not re.match(r'^/api/(characters|scenarios|packages)/',path):raise ValueError('Use a Voxta visual asset')
        async with httpx.AsyncClient(base_url=BASE,trust_env=False,timeout=15) as client:
            response=await client.get(path);response.raise_for_status()
        raw=response.content
    if len(raw)>24*1024*1024:raise ValueError('Image is too large')
    key=hashlib.sha256(raw).hexdigest()[:32]
    target=DATA/'assets'/f'{key}.png'
    if not target.exists():
        image=Image.open(io.BytesIO(raw))
        if image.width*image.height>24_000_000:raise ValueError('Image exceeds 24 megapixels')
        image.convert('RGBA').save(target)
    return {'image_id':key}


@router.post('/characters/{id}/reference')
async def reference(id:str,value:Binding):
    if not re.fullmatch(ID,id):raise ValueError('Invalid Voxta character ID')
    if value.image_id:
        if asset_path(value.image_id).suffix!='.png':raise ValueError('Use an image reference')
        image_id=value.image_id
    else:
        async with httpx.AsyncClient(base_url=BASE,trust_env=False,timeout=15) as client:
            result=await client.get(f'/api/characters/{id}/thumbnail');result.raise_for_status()
        if len(result.content)>24*1024*1024:raise ValueError('Voxta image is too large')
        image=Image.open(io.BytesIO(result.content))
        if image.width*image.height>24_000_000:raise ValueError('Voxta image exceeds 24 megapixels')
        image_id=uuid.uuid4().hex;image.convert('RGB').save(DATA/'assets'/f'{image_id}.png')
    saved=bindings();saved[id]={'image_id':image_id};atomic_json(BINDINGS,saved)
    return saved[id]


@router.get('/media')
async def media(path:str):
    path=media_path(path)
    async with httpx.AsyncClient(base_url=BASE,trust_env=False,timeout=30) as client:
        result=await client.get(path);result.raise_for_status()
    kind=result.headers.get('content-type','').split(';')[0]
    if not kind.startswith(('image/','audio/')) and kind!='application/octet-stream':raise ValueError('Voxta response is not image or audio media')
    if len(result.content)>32*1024*1024:raise ValueError('Media is too large')
    return Response(result.content,media_type=kind)


@router.post('/transcribe')
async def transcribe(file:UploadFile=File(...)):
    raw=await file.read(12*1024*1024+1)
    if len(raw)>12*1024*1024:raise ValueError('Recording is too long')
    async with httpx.AsyncClient(base_url=BASE,trust_env=False,timeout=60) as client:
        result=await client.post('/api/transcription',files={'audio':('clip.wav' if file.content_type=='audio/wav' else 'clip.webm',raw,file.content_type or 'audio/webm')})
        result.raise_for_status();return result.json()


class Motion(BaseModel):
    prompt:str=Field(min_length=3,max_length=600)


class Appearance(Motion):
    image_id:str|None=Field(default=None,pattern=r'^[a-f0-9]{32}$')


@router.post('/appearance')
async def appearance(value:Appearance):
    payload={'prompt':value.prompt,'width':768,'height':768,'requestId':str(uuid.uuid4())}
    if value.image_id:
        path=asset_path(value.image_id)
        if path.suffix!='.png':raise ValueError('Use an image reference')
        payload['inputImages']=['data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode()]
    async with httpx.AsyncClient(base_url=BASE,trust_env=False,timeout=300) as client:
        response=await client.post('/api/image/generate',json=payload,headers={'Accept':'image/*'})
        if not response.is_success:raise HTTPException(503,'Voxta image generation failed. Check the selected diffusion service and whether it supports reference images in Voxta.')
    if len(response.content)>24*1024*1024:raise ValueError('Generated image is too large')
    image=Image.open(io.BytesIO(response.content))
    if image.width*image.height>24_000_000:raise ValueError('Generated image exceeds 24 megapixels')
    image_id=uuid.uuid4().hex
    image.convert('RGB').save(DATA/'assets'/f'{image_id}.png')
    return {'image_id':image_id}


@router.post('/motion')
async def motion(value:Motion):
    # Explicit preparation action; never starts a diffusion job during a reply.
    async with httpx.AsyncClient(base_url=BASE,trust_env=False,timeout=300) as client:
        response=await client.post('/api/animation/generate',json={'prompt':value.prompt,'requestId':str(uuid.uuid4())})
        if not response.is_success:raise HTTPException(503,'Voxta motion generation failed. Check HY-Motion in Voxta; no replacement service was used.')
        result=response.json()
    if not isinstance(result.get('poses'),list) or not 0<result.get('frameCount',0)<=18000:raise ValueError('Unsupported Voxta motion format')
    atomic_json(DATA/'voxta-motion.json',result)
    return result


@router.get('/motion')
def saved_motion():
    path=DATA/'voxta-motion.json'
    return json.loads(path.read_text()) if path.exists() else None


async def authorize(socket):
    token=getattr(socket.app.state,'live_token',None)
    if token is not None and not socket.url.path.startswith('/api/voxta/live/'):
        await socket.close(code=1008);return False
    if token is None:
        from .main import TOKEN
        token=TOKEN
    if socket.headers.get('origin') not in {BASE,'http://127.0.0.1:5173','http://localhost:5173','http://127.0.0.1:8765','http://localhost:8765','http://localhost:5384','http://127.0.0.1:5384'} or not secrets.compare_digest(socket.query_params.get('token',''),token):
        await socket.close(code=1008);return False
    await socket.accept();return True


ALLOWED={'startChat','resumeChat','stopChat','send','interrupt','speechPlaybackStart','speechPlaybackComplete','pauseChat','toolCallResult'}


@router.websocket('/socket')
async def bridge(socket:WebSocket):
    if not await authorize(socket):return
    from websockets.asyncio.client import connect
    session_id=None
    try:
        async with connect('ws://localhost:5384/hub',origin=BASE,proxy=None,max_size=8*1024*1024) as upstream:
            async def send(message):
                await upstream.send(json.dumps({'type':1,'target':'SendMessage','arguments':[message]})+'\x1e')
            await upstream.send('{"protocol":"json","version":1}\x1e')
            handshake=await upstream.recv()
            if json.loads(handshake.split('\x1e')[0]).get('error'):raise RuntimeError('Voxta rejected the connection')
            await send({'$type':'authenticate','client':'PersonaStudio','clientVersion':'0.2.0','scope':['role:app'],'capabilities':{'audioOutput':'Url','acceptedAudioContentTypes':['audio/wav','audio/mpeg','audio/ogg']}})
            async def receive():
                nonlocal session_id
                async for raw in upstream:
                    for record in raw.split('\x1e'):
                        if not record:continue
                        envelope=json.loads(record)
                        if envelope.get('type')==6:await upstream.send('{"type":6}\x1e')
                        for message in envelope.get('arguments',[]):
                            if message.get('$type')=='chatStarted':session_id=message.get('sessionId')
                            await socket.send_json(message)
            async def transmit():
                while True:
                    message=await socket.receive_json()
                    if len(json.dumps(message))>16000 or message.get('$type') not in ALLOWED:raise ValueError('Unsupported Voxta command')
                    await send(message)
            tasks=[asyncio.create_task(receive()),asyncio.create_task(transmit())]
            try:
                done,_=await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
                for task in done:task.result()
            finally:
                for task in tasks:task.cancel()
                await asyncio.gather(*tasks,return_exceptions=True)
                if session_id:
                    try:await send({'$type':'stopChat','sessionId':session_id})
                    except Exception:pass
    except (WebSocketDisconnect,asyncio.CancelledError):pass
    except Exception as error:
        try:await socket.send_json({'$type':'error','message':str(error)[:300]})
        except Exception:pass


@router.websocket('/live/{image_id}')
async def frames(socket:WebSocket,image_id:str):
    if not await authorize(socket):return
    if live_session.locked():await socket.send_json({'error':'Another live portrait is already open.'});await socket.close();return
    requested_device=socket.query_params.get('device','auto')
    if requested_device!='auto' and requested_device!='cpu' and requested_device not in {gpu['uuid'] for gpu in detect()['gpus']}:
        await socket.send_json({'error':'The selected graphics processor is no longer available.'});await socket.close();return
    controls={'full_frame':True,'image_id':image_id,'mouth':0.,'gaze':[0.,0.],'emotion':'neutral','state':'idle','motion':[0.,0.,0.],'presence':'normal'}
    async with live_session:
        try:
            path=asset_path(image_id)
            if path.suffix!='.png':raise ValueError('Use a portrait image')
            if not live.process:
                # Prefer the smaller suitable GPU, leaving the largest card for Voxta.
                device=requested_device if requested_device!='auto' else os.getenv('PERSONA_LIVE_DEVICE','auto')
                live.device=select_live_device(detect()['gpus']) if device=='auto' else device
            async def receive():
                while True:
                    value=await socket.receive_json()
                    if value.get('image_id'):
                        candidate=asset_path(value['image_id'])
                        if candidate.suffix!='.png':raise ValueError('Use an image reference')
                        controls['image_id']=value['image_id']
                    controls['mouth']=max(0.,min(1.,float(value.get('mouth',0))))
                    controls['gaze']=[max(-1.,min(1.,float(v))) for v in value.get('gaze',[0,0])[:2]]
                    controls['motion']=[max(-.5,min(.5,float(v))) for v in value.get('motion',[0,0,0])[:3]]
                    controls['full_frame']=bool(value.get('full_frame',False))
                    controls['patch_frames']=bool(value.get('patch_frames',False))
                    controls['quality']=value.get('quality') if value.get('quality') in {'ultra','fast'} else 'quality'
                    controls['presence']='advanced' if value.get('presence')=='advanced' else 'normal'
                    controls['style']='stylized' if value.get('style')=='stylized' else 'realistic'
                    controls['source_lip']=None if value.get('source_lip') is None else max(0.,min(.5,float(value['source_lip'])))
                    controls['emotion']=str(value.get('emotion','neutral'))[:20]
                    controls['state']=str(value.get('state','idle'))[:20]
                    if len(controls['gaze'])!=2 or len(controls['motion'])!=3:raise ValueError('Invalid control dimensions')
            async def render():
                graph_disabled=False
                while True:
                    start=time.perf_counter()
                    current=dict(controls)
                    try:result=await live.call({'image_path':str(asset_path(current['image_id'])),**current,'disable_graph':graph_disabled})
                    except RuntimeError as error:
                        if not graph_disabled and 'capture' in str(error).lower():
                            graph_disabled=True
                            continue
                        raise
                    await socket.send_json({'mouth_detected':result.get('mouth_detected',False),'source_lip':result.get('source_lip'),'render_ms':result['render_ms'],'neural_ms':result.get('neural_ms'),'compose_ms':result.get('compose_ms'),'encode_ms':result.get('encode_ms'),'patch':result.get('patch'),'device':result['device'],'image_id':current['image_id'],'content_type':result.get('content_type','image/jpeg'),'transparent':result.get('transparent',False),'alpha_embedded':result.get('alpha_embedded',False),'compiled':result.get('compiled',False),'accelerated':result.get('accelerated',False)})
                    await socket.send_bytes(base64.b64decode(result['image']))
                    await asyncio.sleep(max(0,1/max(1,min(30,int(os.getenv('PERSONA_LIVE_FPS','25'))))-(time.perf_counter()-start)))
            tasks=[asyncio.create_task(receive()),asyncio.create_task(render())]
            try:
                done,_=await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
                for task in done:task.result()
            finally:
                for task in tasks:task.cancel()
                await asyncio.gather(*tasks,return_exceptions=True)
                await live.stop()
        except (WebSocketDisconnect,asyncio.CancelledError):pass
        except Exception as error:
            try:await socket.send_json({'error':str(error)[:350]})
            except Exception:pass
