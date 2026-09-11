"""Renderer owned by Voxta's native Live View module; no standalone app services."""
import os
import asyncio
import secrets
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from .voxta import router, live
from .live_models import verify

@asynccontextmanager
async def lifespan(app):
    async def watch_parent():
        import psutil
        parent=int(os.getenv('PERSONA_PARENT_PID','0'))
        while parent:
            await asyncio.sleep(1)
            if not psutil.pid_exists(parent):
                await live.stop()
                os._exit(0)
    watcher=asyncio.create_task(watch_parent())
    try:
        yield
    finally:
        watcher.cancel()
        await asyncio.gather(watcher,return_exceptions=True)
        await live.stop()

app=FastAPI(lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
app.state.live_token=os.environ['PERSONA_MODULE_TOKEN']
app.include_router(router)

@app.middleware('http')
async def module_only(request:Request,call_next):
    if not secrets.compare_digest(request.headers.get('x-persona-module',''),app.state.live_token):
        return JSONResponse({'detail':'Module authorization required'},status_code=403)
    path=request.url.path
    allowed=(path in {'/api/session','/health','/api/voxta/status','/api/voxta/hardware','/api/voxta/usage','/api/voxta/native-reference'}
             or path.startswith('/api/voxta/matte/'))
    if not allowed:return JSONResponse({'detail':'Not a Live View endpoint'},status_code=404)
    try:length=int(request.headers.get('content-length','0') or 0)
    except ValueError:return JSONResponse({'detail':'Invalid content length'},status_code=400)
    if length>36*1024*1024:
        return JSONResponse({'detail':'Image too large'},status_code=413)
    if request.method=='POST' and not secrets.compare_digest(request.headers.get('x-persona-token',''),app.state.live_token):
        return JSONResponse({'detail':'Refresh Live View'},status_code=403)
    return await call_next(request)

@app.get('/api/session')
async def session():return {'token':app.state.live_token}

@app.get('/health')
async def health():
    checks=[verify('portrait',dependencies=False),verify('portrait_detector'),verify('portrait_landmarks')]
    if not all(c['valid'] for c in checks):
        return JSONResponse({'ready':False,'detail':'Live View model files are missing or incomplete.'},status_code=503)
    return {'ready':True,'gpu_loaded':bool(live.process)}

@app.exception_handler(ValueError)
async def invalid(request,error):return JSONResponse({'detail':str(error)},status_code=400)

@app.exception_handler(FileNotFoundError)
async def missing(request,error):return JSONResponse({'detail':'Image not found'},status_code=404)
