"""Optional offline talking portrait. No InsightFace, DWPose or face-parser weights.

LivePortrait supplies identity-conditioned motion; MuseTalk supplies audio-driven
mouth pixels. Their upstream license notices remain in vendor/ and model receipts.
"""
import contextlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1')
sys.path[:0] = [str(ROOT/'vendor/liveportrait'), str(ROOT/'vendor/musetalk')]


def detect_face(rgb):
    import cv2
    model=Path(os.getenv('PERSONA_DATA',str(ROOT/'data')))/'models/portrait_detector/face_detection_yunet_2023mar.onnx'
    detector=cv2.FaceDetectorYN.create(str(model),'',(rgb.shape[1],rgb.shape[0]),.8,.3,5000)
    _,faces=detector.detect(cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR))
    faces=[] if faces is None else faces
    faces=sorted(faces,key=lambda box:int(box[2])*int(box[3]),reverse=True)
    if not faces or (len(faces)>1 and faces[0][2]*faces[0][3]<1.8*faces[1][2]*faces[1][3]):
        raise ValueError('Use a clear, front-facing photo containing one face. Crop closer to the face if detection fails.')
    return faces[0]


def crop_portrait(path):
    import cv2
    import numpy as np
    from PIL import Image
    image = Image.open(path).convert('RGBA')
    background = Image.new('RGBA', image.size, (235, 235, 235, 255))
    rgb = np.array(Image.alpha_composite(background, image).convert('RGB'))
    x,y,w,h = detect_face(rgb)[:4]
    side = int(max(w,h)*2.3)
    left,top = int(x+w/2-side/2), int(y+h*.55-side/2)
    canvas = cv2.copyMakeBorder(rgb, side, side, side, side, cv2.BORDER_REFLECT_101)
    crop = canvas[top+side:top+side+side, left+side:left+side+side]
    return cv2.resize(crop, (512,512), interpolation=cv2.INTER_LANCZOS4)


class Portrait:
    def __init__(self, models):
        import numpy as np
        import torch
        from src.config.inference_config import InferenceConfig
        from src.live_portrait_wrapper import LivePortraitWrapper
        from musetalk.models.unet import UNet
        from musetalk.models.vae import VAE
        from musetalk.utils.audio_processor import AudioProcessor
        from transformers import WhisperModel
        self.device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
        torch.set_num_threads(4)
        self.dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        base = models/'portrait/liveportrait/base_models'
        self.live = LivePortraitWrapper(InferenceConfig(
            checkpoint_F=str(base/'appearance_feature_extractor.pth'),
            checkpoint_M=str(base/'motion_extractor.pth'),
            checkpoint_W=str(base/'warping_module.pth'),
            checkpoint_G=str(base/'spade_generator.pth'),
            checkpoint_S=str(models/'portrait/liveportrait/retargeting_models/stitching_retargeting_module.pth'),
            flag_force_cpu=self.device=='cpu', flag_use_half_precision=self.device!='cpu',
            lip_array=np.zeros((1,)), mask_crop=None))
        lips = models/'portrait_lips/musetalkV15'
        self.unet = UNet(str(lips/'musetalk.json'),str(lips/'unet.pth'),self.device!='cpu',self.device)
        self.unet.model.eval()
        self.pe = self.unet.pe.to(device=self.device, dtype=self.dtype)
        self.vae = VAE(str(models/'portrait_vae'),use_float16=self.device!='cpu')
        self.vae.vae.eval()
        self.processor = AudioProcessor(str(models/'portrait_whisper'))
        self.whisper = WhisperModel.from_pretrained(str(models/'portrait_whisper'), local_files_only=True).to(device=self.device,dtype=self.dtype).eval()
        self.cached = None

    def render(self, payload):
        import cv2
        import numpy as np
        import torch
        from src.utils.camera import get_rotation_matrix
        started = time.perf_counter()
        if torch.cuda.is_available():torch.cuda.reset_peak_memory_stats()
        source = Path(payload['image_path'])
        audio = Path(payload['audio_path'])
        output = Path(payload['output_path'])
        ffmpeg = shutil.which('ffmpeg')
        if not ffmpeg: raise RuntimeError('Install FFmpeg locally to enable talking portraits.')
        torch.manual_seed(1)
        fps = 25
        identity = (str(source),source.stat().st_mtime_ns)
        with torch.inference_mode():
            if not self.cached or self.cached[0] != identity:
                rgb = crop_portrait(source)
                tensor = self.live.prepare_source(rgb)
                info = self.live.get_kp_info(tensor)
                feature = self.live.extract_feature_3d(tensor)
                kp = self.live.transform_keypoint(info)
                self.cached = (identity, rgb, info, feature, kp)
            _, rgb, info, feature, kp = self.cached
            features,length = self.processor.get_audio_feature(str(audio),weight_dtype=self.dtype)
            if length < 3200 or length > 16000*45:
                raise ValueError('Portrait speech must be between 0.2 and 45 seconds.')
            prompts = self.processor.get_whisper_chunk(features,self.device,self.dtype,self.whisper,length,fps)
            count = len(prompts)
            # YuNet replaces the upstream restricted landmark detector. Keep its
            # crop fixed across small head motions to avoid detector jitter.
            detection=detect_face(rgb)
            x,y,w,h=detection[:4]
            nose_y=float(detection[9]);chin_y=float(y+h)
            # Match MuseTalk's crop: nose bridge near the vertical midpoint.
            x0=max(0,int(x));x1=min(512,int(x+w))
            y0=max(0,int(2*nose_y-chin_y));y1=min(512,int(chin_y))
            if x1-x0<32 or y1-y0<32:raise ValueError('The face is too small or too close to the edge. Use a closer portrait.')
            mask=np.zeros((256,256),np.float32)
            mouth_x=float(detection[10]+detection[12])/2
            mouth_y=float(detection[11]+detection[13])/2
            center=(int((mouth_x-x0)/(x1-x0)*256),int((mouth_y-y0)/(y1-y0)*256))
            cv2.ellipse(mask,center,(82,51),0,0,360,1,-1)
            mask=cv2.GaussianBlur(mask,(31,31),9)
            mask=cv2.resize(mask,(x1-x0,y1-y0))[...,None]
            emotion=payload.get('emotion','neutral')
            smile={'warm':.3,'excited':.6,'calm':.1,'sad':-.15,'angry':-.15,'disgusted':-.2}.get(emotion,0)
            brow={'surprised':3,'afraid':2,'sad':1,'angry':-3,'disgusted':-2}.get(emotion,0)
            controls=payload.get('face_controls') or {}
            smile+=.3*(controls.get('mouthSmileLeft',0)+controls.get('mouthSmileRight',0))
            smile-=.3*(controls.get('mouthFrownLeft',0)+controls.get('mouthFrownRight',0))
            brow+=2*controls.get('browInnerUp',0)
            brow-=2*(controls.get('browDownLeft',0)+controls.get('browDownRight',0))
            command=[ffmpeg,'-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','512x512','-r',str(fps),'-i','pipe:0','-i',str(audio),'-map','0:v:0','-map','1:a:0','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-shortest','-movflags','+faststart',str(output)]
            # Streaming to the encoder bounds CPU memory for long utterances.
            process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,creationflags=0x08000000 if sys.platform=='win32' else 0)
            try:
                for start in range(0,count,4):
                    frames=[];latents=[]
                    for i in range(start,min(start+4,count)):
                        t=i/fps
                        delta=info['exp'].clone()
                        pulse=.85+.15*math.sin(t*1.6)
                        for index,axis,factor in ((20,1,-.01),(14,1,-.02),(17,1,.0065),(17,2,.003),(13,1,-.00275),(16,1,-.00275),(3,1,-.0035),(7,1,-.0035)):
                            delta[:,index,axis]+=smile*pulse*factor
                        delta[:,1,1]+=brow*.001;delta[:,2,1]-=brow*.001
                        blink=5*math.exp(-((t%3.7-2.7)/.09)**2)
                        for index,name in ((11,'eyeBlinkRight'),(15,'eyeBlinkLeft')):delta[:,index,1]-=(blink+5*controls.get(name,0))*.001
                        for index in (13,16):delta[:,index,1]+=blink*.0003
                        rotation=get_rotation_matrix(info['pitch']+math.sin(t*1.8)*1.2,info['yaw']+math.sin(t*.8)*1.5,info['roll']+math.sin(t*.6)*.6)
                        driving=info['scale']*(info['kp']@rotation+delta)
                        driving[:,:,:2]+=info['t'][:,:2].unsqueeze(1)
                        generated=self.live.warp_decode(feature,kp,driving)['out']
                        frame=self.live.parse_output(generated)[0]
                        frames.append(frame)
                        roi=cv2.resize(frame[y0:y1,x0:x1],(256,256))[:,:,::-1].copy()
                        latents.append(roi)
                    # Batch both VAE passes instead of encoding each frame alone.
                    masked=torch.cat([self.vae.preprocess_img(roi,half_mask=True) for roi in latents])
                    reference=torch.cat([self.vae.preprocess_img(roi,half_mask=False) for roi in latents])
                    latent=torch.cat([self.vae.encode_latents(masked),self.vae.encode_latents(reference)],dim=1)
                    predicted=self.unet.model(latent,torch.tensor([0],device=self.device),encoder_hidden_states=self.pe(prompts[start:start+len(frames)])).sample
                    mouths=self.vae.decode_latents(predicted)
                    for frame,mouth in zip(frames,mouths):
                        mouth=cv2.resize(mouth[:,:,::-1],(x1-x0,y1-y0))
                        frame[y0:y1,x0:x1]=(mouth*mask+frame[y0:y1,x0:x1]*(1-mask)).clip(0,255).astype(np.uint8)
                        process.stdin.write(frame.tobytes())
                process.stdin.close()
                error=process.stderr.read().decode(errors='replace')
                if process.wait(timeout=30):raise RuntimeError(f'Video encoder failed: {error[:300]}')
            finally:
                if process.poll() is None:process.kill();process.wait()
                if not process.stdin.closed:process.stdin.close()
                process.stderr.close()
        seconds=time.perf_counter()-started
        return {'path':str(output),'seconds':round(seconds,3),'duration':round(count/fps,3),'fps':fps,'frames':count,'render_fps':round(count/seconds,2),'device':self.device,'backend':'liveportrait-musetalk-1.5-yunet-v1','realtime':count/seconds>=fps,'peak_allocated_mib':round(torch.cuda.max_memory_allocated()/1024**2) if torch.cuda.is_available() else 0}


def main():
    protocol=sys.stdout
    engine=None
    for line in sys.stdin:
        try:
            payload=json.loads(line)
            loading=time.perf_counter();cold=engine is None
            with contextlib.redirect_stdout(sys.stderr):
                if engine is None:engine=Portrait(Path(os.getenv('PERSONA_DATA',str(ROOT/'data')))/'models')
                load_seconds=time.perf_counter()-loading if cold else 0
                result=engine.render(payload)
                result['load_seconds']=round(load_seconds,3)
            print(json.dumps({'type':'result',**result}),file=protocol,flush=True)
            print(json.dumps({'type':'done'}),file=protocol,flush=True)
        except Exception as exc:
            import traceback
            traceback.print_exc(file=sys.stderr)
            print(json.dumps({'type':'error','message':str(exc)}),file=protocol,flush=True)


if __name__=='__main__':main()
