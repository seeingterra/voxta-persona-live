/** Persona Live View: render-only adapter. Native Voxta owns all chat and audio. */
(async()=>{
  if(window.__personaLiveView)return;
  const BASE=new URL(import.meta.url).pathname.startsWith('/persona-live-view/')?location.origin+'/persona-live-view':'http://127.0.0.1:8765',root=BASE+'/api/voxta/addon/';
  let store=null,audio=()=>null,notifier=null;
  try{
    const config=await fetch(root+'adapter.json').then(response=>{if(!response.ok)throw Error(`adapter request failed (${response.status})`);return response.json();});
    const exports=await import(location.origin+config.store),audioExports=await import(location.origin+config.audio).catch(()=>({})),notificationExports=config.notifications?await import(location.origin+config.notifications).catch(()=>({})):{};
    store=Object.values(exports).find(value=>typeof value?.getAvatarUrl==='function'&&typeof value?.chat==='function')||null;
    audio=()=>Object.values(audioExports).find(value=>{try{return typeof value==='function'&&typeof value()?.getAnalyser==='function';}catch{return false;}})?.();
    notifier=Object.values(notificationExports).find(value=>typeof value?.notify==='function')||null;
  }catch(error){console.warn('Persona Live View adapter fallback:',error);}
  const style=document.createElement('link');style.rel='stylesheet';style.crossOrigin='anonymous';style.href=root+'live-view.css';document.head.append(style);
  let enabled=false,ws=null,host=null,layer=null,canvas=null,token='',selected='',imageId='',loading='',generation=0,decoding=false,analyser=null,audioSamples=null,header=null,lastImage='',oldFrame=null,blendAt=0,frames=0,lastTime=performance.now(),fps=0,installed=false,resource=null,usagePending=false,lastUsage=0;
  const masks=new Map();const cache=new Map(),gaze=[0,0],head=[0,0,0];let motion=null,motionKey='',motionStart=0;
  const bar=document.createElement('div');bar.id='persona-live-controls';
  const title=document.createElement('div');title.className='persona-live-title';title.textContent='Persona Live View';
  const minimize=document.createElement('button');minimize.className='persona-live-minimize';minimize.type='button';minimize.setAttribute('aria-expanded','true');minimize.textContent='−';minimize.setAttribute('aria-label','Minimize Live View controls');
  const titleRow=document.createElement('div');titleRow.className='persona-live-title-row';titleRow.append(title,minimize);
  const controlHeader=document.createElement('div');controlHeader.className='persona-live-control-header';
  const toggle=document.createElement('button');toggle.textContent='Live view';toggle.type='button';toggle.setAttribute('aria-pressed','false');
  const displayToggle=document.createElement('div');displayToggle.className='persona-live-display-toggle';displayToggle.setAttribute('role','button');displayToggle.tabIndex=0;
  const displayIcon=document.createElement('i');displayIcon.className='bi bi-camera-video persona-live-display-icon';
  const displayBody=document.createElement('div');displayBody.className='persona-live-display-body';
  const displayTitle=document.createElement('div');displayTitle.textContent='Live View';
  const displayDetail=document.createElement('div');displayDetail.className='persona-live-display-detail';
  displayBody.append(displayTitle,displayDetail);
  const displaySwitch=document.createElement('div');displaySwitch.className='persona-live-display-switch';displaySwitch.setAttribute('role','switch');
  const displayKnob=document.createElement('div');displayKnob.className='persona-live-display-knob';displaySwitch.append(displayKnob);
  displayToggle.append(displayIcon,displayBody,displaySwitch);
  const status=document.createElement('span');status.setAttribute('role','status');status.textContent='Select Live view in chat augmentations';
  const optionsToggle=document.createElement('button');optionsToggle.className='persona-live-options-toggle';optionsToggle.type='button';optionsToggle.textContent='Options';optionsToggle.setAttribute('aria-expanded','false');
  const options=document.createElement('div');options.className='persona-live-options';options.hidden=true;
  controlHeader.append(toggle,status,optionsToggle);bar.append(titleRow,controlHeader,options);
  minimize.onclick=()=>{const collapsed=bar.classList.toggle('persona-live-minimized');minimize.textContent=collapsed?'+':'−';minimize.setAttribute('aria-expanded',String(!collapsed));minimize.setAttribute('aria-label',collapsed?'Expand Live View controls':'Minimize Live View controls');};
  let drag=null;
  title.onpointerdown=event=>{const host=bar.parentElement;if(!host)return;drag={x:event.clientX,y:event.clientY,left:bar.offsetLeft,top:bar.offsetTop,host};title.setPointerCapture(event.pointerId);bar.classList.add('persona-live-dragging');};
  title.onpointermove=event=>{if(!drag)return;const left=Math.max(0,Math.min(drag.host.clientWidth-bar.offsetWidth,drag.left+event.clientX-drag.x)),top=Math.max(0,Math.min(drag.host.clientHeight-bar.offsetHeight,drag.top+event.clientY-drag.y));bar.style.left=left+'px';bar.style.top=top+'px';bar.style.right='auto';bar.style.bottom='auto';};
  title.onpointerup=event=>{if(!drag)return;drag=null;bar.classList.remove('persona-live-dragging');title.releasePointerCapture(event.pointerId);};
  optionsToggle.onclick=()=>{const expanded=options.hidden;options.hidden=!expanded;optionsToggle.setAttribute('aria-expanded',String(expanded));optionsToggle.textContent=expanded?'Hide options':'Options';};
  function choice(label,items){const row=document.createElement('label');row.className='persona-live-option';row.textContent=label;const select=document.createElement('select');select.setAttribute('aria-label',label);for(const [value,text] of items){const option=document.createElement('option');option.value=value;option.textContent=text;select.append(option);}row.append(select);options.append(row);return select;}
  const quality=choice('Render quality',[['quality','Full detail'],['fast','Faster rendering'],['ultra','Ultra fast (lower face detail)']]);
  const gpu=choice('Graphics processor (this chat)',[['auto','Automatic — choose a suitable GPU'],['cpu','CPU — no GPU memory']]);
  const presence=choice('Character presence',[['normal','Normal Presence'],['advanced','Advanced Presence (beta)']]);
  const visualStyle=choice('Character style',[['auto','Style: automatic (name hints)'],['realistic','Realistic'],['stylized','Stylized']]);
  const sourceMouth=choice('Mouth in source picture',[['auto','Source mouth: automatic'],['.02','Source mouth: closed'],['.12','Source mouth: slightly open'],['.25','Source mouth: open']]);
  let awaitingFull=false,frameBuffer=null,paintRequest=0;
  let starting=false,paused=false,chatKey='',active=false,checking=false,lastCheck=0;
  const native=BASE.startsWith(location.origin+'/persona-live-view');
  const state={version:'0.5.12',enabled:false,preparing:false,frames:0,fps:0,source:'',error:'',audioLevel:0};window.__personaLiveView=state;
  function notify(level,message,details,tag){notifier?.notify({level,message,details,tag});}
  function setStatus(message,loading=false){status.textContent=message;status.classList.toggle('persona-live-loading',loading);}
  async function api(path,body){if(!token){const response=await fetch(BASE+'/api/session');const value=await response.json().catch(()=>({}));if(!response.ok)throw Error(value.detail||'Live View could not start. Check its settings in Voxta Services.');token=value.token;}
    const r=await fetch(BASE+'/api/voxta/'+path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json','X-Persona-Token':token}:{},body:body?JSON.stringify(body):undefined});if(!r.ok){const e=await r.json().catch(()=>({}));throw Error(e.detail||'Live View renderer unavailable.');}return r.json();}
  async function loadGpus(){const selectedGpu=gpu.value,value=await api('hardware'),choices=[['auto','Automatic — choose a suitable GPU'],['cpu','CPU — no GPU memory'],...(value.gpus||[]).map(card=>[card.uuid,`GPU ${card.index}: ${card.name} · ${(card.total_mb/1024).toFixed(1)} GB`])];if(!choices.some(([value])=>value===selectedGpu))choices.push([selectedGpu,`Previously selected GPU — unavailable (${selectedGpu})`]);gpu.replaceChildren();for(const [value,text] of choices){const option=document.createElement('option');option.value=value;option.textContent=text;gpu.append(option);}gpu.value=selectedGpu;}
  function updateLiveStatus(){if(!enabled)return;const details=[];if(resource?.running){if(resource.cpu_percent!==null&&resource.cpu_percent!==undefined)details.push(`CPU ${resource.cpu_percent.toFixed(0)}%`);if(resource.memory_mb!==undefined)details.push(`RAM ${(resource.memory_mb/1024).toFixed(resource.memory_mb>=1024?1:0)} ${resource.memory_mb>=1024?'GB':'MB'}`);}setStatus(`Live · ${fps<1?fps.toFixed(1):fps.toFixed(0)} fps${details.length?' · '+details.join(' · '):''}`);}
  async function refreshUsage(){const now=performance.now();if(!enabled||usagePending||now-lastUsage<1000)return;usagePending=true;lastUsage=now;try{resource=await api('usage');updateLiveStatus();}catch{}finally{usagePending=false;}}
  function updateDisplayToggle(){
    displayDetail.textContent=active?'Animated character portrait':'Enable Live view in chat augmentations';
    displayToggle.classList.toggle('persona-live-display-disabled',!active);
    displayToggle.setAttribute('aria-disabled',String(!active));
    displaySwitch.setAttribute('aria-checked',String(enabled));
  }
  function attachDisplayToggle(){
    const label=[...document.querySelectorAll('div')].find(node=>node.childElementCount===0&&node.textContent.trim()==='Display'&&node.nextElementSibling?.querySelector('[role="switch"]'));
    const group=label?.nextElementSibling;
    if(group&&displayToggle.parentElement!==group){
      group.append(displayToggle);
    }
    updateDisplayToggle();
  }
  function stop(message='Animation paused'){generation++;enabled=false;starting=false;state.enabled=false;state.preparing=false;resource=null;gpu.disabled=false;if(ws){ws.onclose=null;ws.close();}ws=null;imageId='';loading='';selected='';lastImage='';oldFrame=null;frameBuffer=null;cancelAnimationFrame(paintRequest);host?.classList.remove('persona-live-active','persona-live-positioned');layer?.remove();layer=null;canvas=null;toggle.textContent='Start animation';toggle.setAttribute('aria-pressed','false');setStatus(message);updateDisplayToggle();}
  function fail(e){state.error=String(e.message||e);paused=true;stop(state.error);}
  function attach(target){if(host===target&&layer?.isConnected)return;host?.classList.remove('persona-live-active','persona-live-positioned');layer?.remove();host=target;if(getComputedStyle(host).position==='static')host.classList.add('persona-live-positioned');layer=document.createElement('div');layer.className='persona-live-layer';canvas=document.createElement('canvas');canvas.setAttribute('aria-label','Voxta live character');layer.append(canvas);host.append(layer);if(frameBuffer){canvas.width=frameBuffer.width;canvas.height=frameBuffer.height;paint();host.classList.add('persona-live-active');layer.style.opacity='1';}else awaitingFull=true;host.addEventListener('pointerleave',()=>{gaze[0]=0;gaze[1]=0;},{signal:life.signal});host.addEventListener('pointermove',e=>{const r=host.getBoundingClientRect();gaze[0]=(e.clientX-r.left)/r.width*2-1;gaze[1]=(e.clientY-r.top)/r.height*2-1;},{signal:life.signal});}
  function paint(){
    if(!canvas||!frameBuffer)return;
    const ctx=canvas.getContext('2d'),elapsed=(performance.now()-blendAt)/420;
    const t=Math.min(1,Math.max(0,elapsed)),blend=t*t*(3-2*t);
    ctx.clearRect(0,0,canvas.width,canvas.height);
    // Blend independent frames with additive premultiplied alpha, never into the patch base.
    ctx.globalAlpha=oldFrame?1-blend:0;
    if(oldFrame)ctx.drawImage(oldFrame,0,0,canvas.width,canvas.height);
    ctx.globalCompositeOperation='lighter';ctx.globalAlpha=oldFrame?blend:1;
    ctx.drawImage(frameBuffer,0,0);ctx.globalAlpha=1;ctx.globalCompositeOperation='source-over';
    if(oldFrame&&t<1)paintRequest=requestAnimationFrame(paint);else oldFrame=null;
  }
  const life=new AbortController();
  async function install(){if(installed)return;status.textContent='Installing Live View…';const response=await fetch(BASE+'/api/voxta/install',{method:'POST'}),value=await response.json().catch(()=>({}));if(!response.ok)throw Error(value.detail||'Live View installation failed. Check Voxta Services and try again.');installed=true;}
  async function start(message='Starting animation…'){if(enabled||starting||!active)return;starting=true;state.preparing=true;state.error='';gpu.disabled=true;const epoch=generation;toggle.textContent='Cancel animation';setStatus(message,true);try{await install();if(epoch!==generation)return;setStatus('Starting renderer…',true);await api('status');try{await loadGpus();}catch{}if(epoch!==generation)return;enabled=true;state.enabled=true;gpu.disabled=false;toggle.textContent='Pause animation';toggle.setAttribute('aria-pressed','true');setStatus('Preparing character image…',true);frames=0;lastTime=performance.now();updateDisplayToggle();
    // Reading Voxta's analyser must never block animation or change voice settings.
    try{void Promise.resolve(audio()?.getAnalyser?.()).then(value=>{if(epoch===generation){analyser=value;audioSamples=null;}}).catch(()=>{});}catch{}
  }catch(e){if(epoch===generation)fail(e);}finally{if(epoch===generation){starting=false;state.preparing=false;}}}
  toggle.onclick=()=>{if(enabled||starting){paused=true;stop();return;}paused=false;void start();};
  gpu.onchange=()=>{if(!enabled)return;const name=gpu.selectedOptions[0]?.textContent||'selected processor';paused=false;stop(`Switching to ${name}…`);void start(`Switching to ${name}…`);};
  function toggleFromDisplay(){if(!active)return;if(enabled||starting){paused=true;stop();return;}paused=false;void start();}
  displayToggle.onclick=toggleFromDisplay;
  displayToggle.onkeydown=event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();toggleFromDisplay();}};
  fetch(BASE+'/api/voxta/install-status').then(response=>response.ok?response.json():null).then(value=>{if(value&&!value.ready)notify('info','Persona Live View is ready to install','Open a chat with Live view enabled, then select Start animation. The one-time setup downloads module dependencies and licensed model files.','persona-live-view-install');}).catch(()=>{});
  function sourceIn(target){const candidates=[...target.querySelectorAll('[style*="background-image"]')].filter(e=>!e.className.includes('fade-out'));
    const child=candidates.at(-1)||target;const match=child.style.backgroundImage.match(/url\(["']?(.*?)["']?\)/);return match?.[1]||target.querySelector('video')?.currentSrc||'';}
  function characterState(){const id=store?.speakingMessageId?.(),generating=store?.generating?.();const label=decodeURIComponent(selected).toLowerCase();const map={angry:'angry',happy:'warm',smile:'warm',excited:'excited',sad:'sad',surpris:'surprised',fear:'afraid',disgust:'disgusted',calm:'calm'};const mood=Object.keys(map).find(k=>label.includes(k));return {emotion:mood?map[mood]:'neutral',state:id?'speaking':generating?'thinking':label.includes('listening')?'listening':'idle'};}
  async function reference(url){if(loading===url)return;loading=url;const epoch=generation;try{setStatus('Loading character portrait…',true);let binding=cache.get(url);if(!binding){let source={path:url};if(url.startsWith('blob:')||url.startsWith('data:')){const blob=await fetch(url).then(r=>r.blob());if(blob.size>24*1024*1024)throw Error('Voxta image is too large');const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(blob);});source={image_data:data};}binding=await api('native-reference',source);cache.set(url,binding);}if(epoch!==generation||!enabled||selected!==url)return;imageId=binding.image_id;state.source=url;
      if(!ws){setStatus('Connecting renderer…',true);ws=new WebSocket(BASE.replace('http:','ws:')+'/api/voxta/live/'+imageId+'?token='+encodeURIComponent(token)+'&device='+encodeURIComponent(gpu.value));ws.binaryType='arraybuffer';ws.onopen=()=>setStatus('Rendering first frame…',true);
        ws.onmessage=async e=>{if(typeof e.data==='string'){const value=JSON.parse(e.data);if(value.error){fail(Error(value.error));return;}header=value;state.mouthDetected=value.mouth_detected;state.sourceLip=value.source_lip;state.renderMs=value.render_ms;state.neuralMs=value.neural_ms;state.composeMs=value.compose_ms;state.encodeMs=value.encode_ms;state.accelerated=value.accelerated;state.compiled=value.compiled;state.device=value.device;return;}if(decoding||!canvas)return;decoding=true;const frameHeader=header;
          try{if(frameHeader?.image_id!==imageId)return;if(frameHeader?.patch&&(lastImage!==frameHeader.image_id||canvas.width!==frameHeader.patch.canvas_width||canvas.height!==frameHeader.patch.canvas_height)){awaitingFull=true;return;}if(!frameHeader?.patch)awaitingFull=false;let mask=null;if(frameHeader?.transparent&&!frameHeader?.alpha_embedded){if(!masks.has(frameHeader.image_id))masks.set(frameHeader.image_id,fetch(BASE+'/api/voxta/matte/'+frameHeader.image_id).then(r=>{if(!r.ok)throw Error('Could not load character transparency');return r.blob();}).then(blob=>createImageBitmap(blob)));if(masks.size>4){const key=masks.keys().next().value;void masks.get(key).then(m=>m.close()).catch(()=>{});masks.delete(key);}mask=await masks.get(frameHeader.image_id);}const bitmap=await createImageBitmap(new Blob([e.data],{type:frameHeader?.content_type||'image/jpeg'}));if(epoch!==generation||!enabled||!canvas||frameHeader?.image_id!==imageId){bitmap.close();return;}
            if(lastImage&&frameHeader?.image_id!==lastImage){oldFrame=document.createElement('canvas');oldFrame.width=canvas.width;oldFrame.height=canvas.height;oldFrame.getContext('2d').drawImage(canvas,0,0);blendAt=performance.now();}
            lastImage=frameHeader?.image_id||imageId;
            if(!frameBuffer)frameBuffer=document.createElement('canvas');
            if(!frameHeader?.patch){frameBuffer.width=bitmap.width;frameBuffer.height=bitmap.height;}
            if(canvas.width!==frameBuffer.width||canvas.height!==frameBuffer.height){canvas.width=frameBuffer.width;canvas.height=frameBuffer.height;}
            const ctx=frameBuffer.getContext('2d'),region=frameHeader?.patch;
            ctx.clearRect(region?.x||0,region?.y||0,region?.width||frameBuffer.width,region?.height||frameBuffer.height);
            ctx.drawImage(bitmap,region?.x||0,region?.y||0);bitmap.close();
            if(mask){ctx.globalCompositeOperation='destination-in';ctx.drawImage(mask,0,0,frameBuffer.width,frameBuffer.height);ctx.globalCompositeOperation='source-over';}
            cancelAnimationFrame(paintRequest);paint();
            host.classList.add('persona-live-active');layer.style.opacity='1';layer.style.background=frameHeader?.transparent?'transparent':'#181d21';layer.classList.toggle('persona-live-cutout',!!frameHeader?.transparent);frames++;state.frames++;const now=performance.now();if(now-lastTime>1000){fps=frames*1000/(now-lastTime);frames=0;lastTime=now;state.fps=fps;updateLiveStatus();}
          }catch(e){fail(e);}finally{decoding=false;}};
        ws.onerror=()=>fail(Error('Animation connection failed. Check Live View settings in Voxta Services.'));ws.onclose=()=>{if(enabled)fail(Error('Animation disconnected. Press Start animation to retry.'));};
      }
    }catch(e){if(epoch===generation)fail(e);}finally{if(loading===url)loading='';}}
  function currentChat(){const known=store?.getActiveChat?.()||store?.chat?.();if(known)return known;const match=location.pathname.match(/^\/chat\/([0-9a-f-]{36})(?:\/|$)/i);return match?{sessionId:match[1],chatId:match[1],started:true}:null;}
  const timer=setInterval(()=>{
    const chat=currentChat(),key=chat?.sessionId||chat?.chatId||'';
    if(key!==chatKey){stop();chatKey=key;paused=false;active=false;state.error='';lastCheck=0;token='';}
    if(chat&&native&&!checking&&performance.now()-lastCheck>1000){checking=true;lastCheck=performance.now();const current=chatKey;void fetch(BASE+'/api/voxta/module-state?sessionId='+encodeURIComponent(chat.sessionId||'')).then(r=>{if(!r.ok)throw Error('Live View module is unavailable.');return r.json();}).then(value=>{if(current!==chatKey)return;const becameActive=value.active&&!active;active=value.active;if(becameActive&&!paused&&!(["stage","portrait"].includes(store?.displayMode?.())))store?.setDisplayMode?.("stage",true);if(active&&!paused)void start();else if(!active){if(enabled||starting)stop();if(!state.error)status.textContent=chat.started?'Select Live view in chat augmentations, then restart the chat.':'Waiting for Voxta to start the chat. Check any chat error first.';}updateDisplayToggle();}).catch(e=>{if(current===chatKey&&!enabled)status.textContent=e.message;}).finally(()=>{checking=false;});}
    const targets=[...document.querySelectorAll('[class*="cover-image-fader-container"], [class*="avatar-apply"]')].filter(e=>e.getBoundingClientRect().height>180&&e.getBoundingClientRect().width>140);
    const target=targets.sort((a,b)=>Number(!!b.closest('[class*="is-speaking"]'))-Number(!!a.closest('[class*="is-speaking"]'))||b.getBoundingClientRect().width*b.getBoundingClientRect().height-a.getBoundingClientRect().width*a.getBoundingClientRect().height)[0];
    if(!target||!chat){bar.remove();if(!chat&&(enabled||starting))stop();return;}
    const barHost=target.closest('[class*="stage-view"]')||target.closest('[class*="avatar-constraint"]')?.parentElement||target.closest('[role="button"]')?.parentElement||target.parentElement;
    if(!barHost)return;
    bar.dataset.stage=String(barHost!==target.parentElement);if(!bar.isConnected||bar.parentElement!==barHost)barHost.append(bar);attachDisplayToggle();
    if(!enabled)return;void refreshUsage();attach(target);const url=sourceIn(target);
    if(/\.(mp4|webm)(?:[?&#]|$)/i.test(decodeURIComponent(url))){if(ws){ws.onclose=null;ws.close();ws=null;}imageId='';host.classList.remove('persona-live-active','persona-live-positioned');layer.style.opacity='0';selected=url;status.textContent='Playing character video';return;}
    if(!url){status.textContent='Waiting for the character image…';return;}
    if(url&&url!==selected){selected=url;void reference(url);}
    const clip=store?.avatarMotionClip?.();if(clip?.url&&(!clip.charId||selected.includes(clip.charId))&&clip.animationId!==motionKey){motionKey=clip.animationId;const key=motionKey;void fetch(new URL(clip.url,location.origin)).then(r=>r.json()).then(m=>{if(key===motionKey&&Array.isArray(m.poses)&&m.frameCount>0&&m.fps>0){motion=m;motionStart=performance.now();}}).catch(()=>{});}
    if(ws?.readyState===WebSocket.OPEN&&imageId){let mouth=0;if(analyser){if(!audioSamples||audioSamples.length!==analyser.fftSize)audioSamples=new Float32Array(analyser.fftSize);analyser.getFloatTimeDomainData(audioSamples);let sum=0;for(const sample of audioSamples)sum+=sample*sample;mouth=Math.min(1,Math.sqrt(sum/audioSamples.length)*6);}const current=characterState();if(layer){layer.dataset.mood=current.emotion;layer.dataset.activity=current.state;layer.dataset.presence=presence.value;}state.audioLevel=mouth;head[0]=0;head[1]=0;head[2]=0;if(motion){const joints=motion.poses.length/(motion.frameCount*3),frame=Math.min(motion.frameCount-1,Math.floor((performance.now()-motionStart)/1000*motion.fps));if(Number.isInteger(joints)&&joints>15){const offset=(frame*joints+15)*3;head[0]=motion.poses[offset];head[1]=motion.poses[offset+1];head[2]=motion.poses[offset+2];}}ws.send(JSON.stringify({quality:quality.value,presence:presence.value,style:visualStyle.value==='auto'?(/anime|cartoon|illustration|stylized/i.test(decodeURIComponent(selected))?'stylized':'realistic'):visualStyle.value,source_lip:sourceMouth.value==='auto'?null:Number(sourceMouth.value),motion:head,image_id:imageId,mouth:current.state==='speaking'?mouth:0,gaze,full_frame:true,patch_frames:presence.value!=='advanced'&&!awaitingFull,...current}));}
  },40);
  addEventListener('pagehide',()=>{clearInterval(timer);stop();life.abort();for(const mask of masks.values())void mask.then(m=>m.close()).catch(()=>{});},{once:true});
})().catch(e=>{console.error('Persona Live View:',e);window.__personaLiveView={error:String(e.message||e)};});
