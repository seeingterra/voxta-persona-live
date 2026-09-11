import asyncio
import json
import os
import sys
import time
from .storage import ROOT, DATA
from .live_models import ready, verify

class Worker:
    def __init__(self,stage,device='cpu',python=None,module='backend.worker',timeout=240):
        self.stage=stage;self.device=device;self.process=None;self.lock=asyncio.Lock();self.log=None;self.usage_sample=None
        self.python=python or sys.executable;self.module=module;self.timeout=timeout

    async def stop(self):
        p=self.process;self.process=None;self.usage_sample=None
        if p and p.returncode is None:
            if sys.platform=='win32':
                # Windows virtualenv launchers may own the actual CUDA process.
                import psutil
                try:
                    for child in psutil.Process(p.pid).children(recursive=True):
                        try:child.kill()
                        except psutil.NoSuchProcess:pass
                except psutil.NoSuchProcess:pass
            try:p.kill()
            except ProcessLookupError:pass
            await p.wait()
        if self.log:self.log.close();self.log=None

    async def call(self,payload,cancel=None):
        if self.module=='backend.live_worker':
            valid=(
                verify('portrait',dependencies=False)['valid']
                and ready('portrait_detector')
                and ready('portrait_landmarks')
            )
        else:valid=ready(self.stage)
        if not valid:raise RuntimeError(f'Install the {self.stage} model files and their receipts first.')
        if self.lock.locked():raise RuntimeError(f'{self.stage} is busy. Stop the current response or wait.')
        async with self.lock:
            if not self.process or self.process.returncode is not None:
                env=dict(os.environ,CUDA_VISIBLE_DEVICES='' if self.device=='cpu' else self.device,PYTHONIOENCODING='utf-8')
                self.log=(DATA/'logs'/f'{self.stage}.log').open('w',encoding='utf-8')
                self.process=await asyncio.create_subprocess_exec(str(self.python),'-m',self.module,self.stage,str(DATA/'models'/self.stage),cwd=ROOT,env=env,stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=self.log,limit=4*1024*1024,creationflags=0x08000000 if sys.platform=='win32' else 0)
            p=self.process
            try:
                p.stdin.write((json.dumps(payload)+'\n').encode());await p.stdin.drain()
                result={}
                async with asyncio.timeout(self.timeout):
                    while True:
                        if cancel and cancel.is_set():raise asyncio.CancelledError()
                        read=asyncio.create_task(p.stdout.readline())
                        try:
                            while not read.done():
                                if cancel and cancel.is_set():raise asyncio.CancelledError()
                                await asyncio.sleep(.005)
                            line=read.result()
                        finally:
                            if not read.done():read.cancel()
                        if not line:raise RuntimeError(f'{self.stage} worker exited. See its local diagnostic log.')
                        message=json.loads(line)
                        if message['type']=='error':raise RuntimeError(message['message'])
                        if message['type']=='result':result=message
                        if message['type']=='done':return result
            except TimeoutError as error:
                await self.stop()
                raise RuntimeError(
                    f'{self.stage} render timed out after {self.timeout} seconds. '
                    'Free GPU memory or select another graphics processor in Persona Live View settings.'
                ) from error
            except BaseException:
                await self.stop()
                raise

    def usage(self):
        """Return the resource use of the persistent renderer worker."""
        p=self.process
        if p is None or p.returncode is not None:return {'running':False}
        import psutil
        try:
            process=psutil.Process(p.pid)
            with process.oneshot():
                memory_mb=round(process.memory_info().rss/1024/1024)
                times=process.cpu_times()
            now=time.monotonic();cpu_seconds=times.user+times.system
            previous=self.usage_sample;self.usage_sample=(now,cpu_seconds)
            cpu_percent=None if previous is None else round(max(0,(cpu_seconds-previous[1])/(now-previous[0])*100),1)
            return {'running':True,'device':self.device,'cpu_percent':cpu_percent,'memory_mb':memory_mb}
        except psutil.Error:return {'running':False}
