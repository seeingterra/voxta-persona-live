"""Continuous local neural portrait frames; no utterance/video-file rendering.

Uses the retained MIT LivePortrait core and YuNet detector. Speech and turn
management are supplied by Voxta. Audio envelopes are approximate articulation,
not phoneme inference or full-body video synthesis.
"""
import base64
import contextlib
import json
import math
import os
import sys
import time
from pathlib import Path
from .live_composite import PortraitComposite
from .live_motion import NaturalMotion

ROOT = Path(__file__).resolve().parents[1]
LIVEPORTRAIT_ROOT = ROOT / "vendor" / "liveportrait"
if str(LIVEPORTRAIT_ROOT) not in sys.path:
    sys.path.insert(0, str(LIVEPORTRAIT_ROOT))


def detect_face(rgb):
    import cv2
    model = Path(os.getenv("PERSONA_DATA", str(ROOT / "data"))) / "models/portrait_detector/face_detection_yunet_2023mar.onnx"
    detector = cv2.FaceDetectorYN.create(str(model), "", (rgb.shape[1], rgb.shape[0]), .8, .3, 5000)
    _, faces = detector.detect(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    faces = [] if faces is None else sorted(faces, key=lambda box: int(box[2]) * int(box[3]), reverse=True)
    if not faces or (len(faces) > 1 and faces[0][2] * faces[0][3] < 1.8 * faces[1][2] * faces[1][3]):
        raise ValueError("Use a clear, front-facing photo containing one face. Crop closer to the face if detection fails.")
    return faces[0]


class LivePortrait:
    def __init__(self):
        import numpy as np
        import torch
        import cv2
        from src.config.inference_config import InferenceConfig
        from src.live_portrait_wrapper import LivePortraitWrapper
        torch.set_num_threads(4)
        cv2.setNumThreads(2)
        torch.backends.cudnn.benchmark=True
        torch.backends.cudnn.benchmark_limit=4
        self.device='cuda:0' if os.getenv('PERSONA_LIVE_DEVICE')!='cpu' and torch.cuda.is_available() else 'cpu'
        # Inductor's max-autotune path is not reliable on the deployed Windows
        # CUDA/Triton stack; retain the stable CUDA-graph acceleration instead.
        self.compiled=False
        root=Path(os.getenv('PERSONA_DATA',str(ROOT/'data')))/'models/portrait/liveportrait'
        config={f'checkpoint_{key}':str(root/'base_models'/filename) for key,filename in {
            'F':'appearance_feature_extractor.pth','M':'motion_extractor.pth',
            'W':'warping_module.pth','G':'spade_generator.pth'}.items()}
        self.model=LivePortraitWrapper(InferenceConfig(**config,
            checkpoint_S=str(root/'retargeting_models/stitching_retargeting_module.pth'),
            flag_force_cpu=self.device=='cpu',flag_use_half_precision=self.device!='cpu',
            flag_do_torch_compile=self.compiled,lip_array=np.zeros(1),mask_crop=None))
        if self.device!='cpu' and not self.compiled:self.model.spade_generator.to(memory_format=torch.channels_last)
        self.identity=None;self.smooth=0.;self.started=time.perf_counter()
        self.cache={}
        from .live_acceleration import install
        install(self.model)
        self.graph=None;self.graph_attempted=False;self.graph_identity=None
        self.motion=NaturalMotion()
        self.sent_identity=None
        self.render_size=64
        from .live_landmarks import SourceLandmarks
        self.landmarks=SourceLandmarks(root.parents[1]/"portrait_landmarks/face_landmarker.task")

    def decode(self,driving):
        """Replay fixed-shape GPU work without Python's per-layer launch overhead."""
        import torch
        def run(feature,source,target):
            with self.model.inference_ctx():
                warped=self.model.warping_module(feature,kp_source=source,kp_driving=target)
                feature=warped['out']
                if self.render_size!=64:feature=torch.nn.functional.interpolate(feature,size=(self.render_size,self.render_size),mode='bilinear',align_corners=False)
                out=self.model.spade_generator(feature=feature)
                return (out[0].permute(1,2,0).float().clamp(0,1)*255).to(torch.uint8)
        if self.device!='cpu' and not self.graph_attempted and os.getenv('PERSONA_CUDA_GRAPH','1')=='1':
            self.graph_attempted=True
            try:
                self.graph_feature=self.feature.clone();self.graph_source=self.kp.clone();self.graph_target=driving.clone()
                stream=torch.cuda.Stream();stream.wait_stream(torch.cuda.current_stream())
                with torch.cuda.stream(stream):
                    for _ in range(3):run(self.graph_feature,self.graph_source,self.graph_target)
                torch.cuda.current_stream().wait_stream(stream)
                graph=torch.cuda.CUDAGraph()
                with torch.cuda.graph(graph):self.graph_out=run(self.graph_feature,self.graph_source,self.graph_target)
                self.graph=graph
            except RuntimeError as error:
                print(f'CUDA graph unavailable; using eager rendering: {error}',file=sys.stderr)
                self.graph=None
        if self.graph:
            if self.graph_identity!=self.identity:
                self.graph_feature.copy_(self.feature);self.graph_source.copy_(self.kp);self.graph_identity=self.identity
            self.graph_target.copy_(driving)
            self.graph.replay();out=self.graph_out
        else:out=run(self.feature,self.kp,driving)
        return out.cpu().numpy()

    def frame(self,request):
        import cv2
        import numpy as np
        import torch
        from PIL import Image
        from src.utils.camera import get_rotation_matrix
        started=time.perf_counter()
        if request.get('disable_graph'):self.graph_attempted=True
        size={'ultra':32,'fast':48}.get(request.get('quality'),64)
        if size!=self.render_size:
            self.render_size=size;self.graph=None;self.graph_attempted=False;self.graph_identity=None;self.identity=None
            for cached in self.cache.values():cached[3].correction=None
        path=Path(request['image_path']);identity=(str(path),path.stat().st_mtime_ns)
        with torch.inference_mode():
            if self.identity!=identity:
                if identity not in self.cache:
                    composite=PortraitComposite(path,detect_face)
                    composite.source_lip=self.landmarks.measure(composite.crop)
                    composite.source_eyes=self.landmarks.measure_eyes(composite.crop)
                    source=self.model.prepare_source(composite.crop)
                    info=self.model.get_kp_info(source)
                    self.cache[identity]=(info,self.model.extract_feature_3d(source),self.model.transform_keypoint(info),composite)
                    if len(self.cache)>4:del self.cache[next(iter(self.cache))]
                self.info,self.feature,self.kp,self.composite=self.cache[identity]
                self.identity=identity
                if self.composite.correction is None:self.composite.calibrate(self.decode(self.kp))
            info=self.info;t=time.perf_counter()-self.started
            emotion=request.get('emotion','neutral');state=request.get('state','idle')
            gaze=request.get('gaze',[0,0]);motion=request.get('motion',[0,0,0])
            pitch,yaw,roll,blink,self.smooth,smile,brow,gaze=self.motion.update(t,request.get('mouth',0),state,gaze,emotion)
            if request.get('style')=='stylized':
                pitch*=1.4;yaw*=1.4;roll*=1.4;smile*=1.35;brow*=1.25
            pitch+=float(motion[0])*8;yaw+=float(motion[1])*8;roll+=float(motion[2])*8
            rotation=get_rotation_matrix(info['pitch']+pitch,info['yaw']+yaw,info['roll']+roll)
            delta=info['exp'].clone()
            for index,axis,factor in ((20,1,-.01),(14,1,-.02),(17,1,.0065),(17,2,.003),(13,1,-.00275),(16,1,-.00275),(3,1,-.0035),(7,1,-.0035)):
                delta[:,index,axis]+=smile*factor
            delta[:,1,1]+=brow*.001;delta[:,2,1]-=brow*.001
            for i in (11,15):delta[:,i,0]+=float(gaze[0])*.0008
            driving=info['scale']*(info['kp']@rotation+delta)
            driving[:,:,:2]+=info['t'][:,:2].unsqueeze(1)
            driving[:,:,1]+=math.sin(t*.82)*.00035
            source_lip=request.get('source_lip')
            if source_lip is None:source_lip=self.composite.source_lip
            source_lip=.02 if source_lip is None else max(0.,min(.5,float(source_lip)))
            ratios=torch.tensor([[source_lip,.02+self.smooth*.3]],device=self.device)
            driving+=self.model.retarget_lip(self.kp,ratios)
            if blink and self.composite.source_eyes:
                source_eyes=self.composite.source_eyes
                target_eye=max(.002,sum(source_eyes)*.5*(1-blink))
                eye_ratios=torch.tensor([[source_eyes[0],source_eyes[1],target_eye]],device=self.device)
                driving+=self.model.retarget_eye(self.kp,eye_ratios)
            driving=self.model.stitching(self.kp,driving)
            image=self.decode(driving)
            neural_ms=(time.perf_counter()-started)*1000
            advanced=request.get('presence')=='advanced' and self.composite.transparent
            transparent=bool(request.get('full_frame') and self.composite.transparent)
            patch_only=bool(request.get('full_frame') and request.get('patch_frames') and self.sent_identity==identity and not advanced)
            if request.get('full_frame'):image=self.composite.apply(image,patch_only=patch_only,body_motion=self.motion.body(t,state) if advanced else None)
            compose_ms=(time.perf_counter()-started)*1000-neural_ms
            self.sent_identity=identity if request.get("full_frame") else None
            if transparent:
                kind='image/png'
                ok,jpeg=cv2.imencode('.png',cv2.cvtColor(image,cv2.COLOR_RGBA2BGRA),[cv2.IMWRITE_PNG_COMPRESSION,1])
            else:
                kind='image/jpeg'
                ok,jpeg=cv2.imencode('.jpg',cv2.cvtColor(image,cv2.COLOR_RGB2BGR),[cv2.IMWRITE_JPEG_QUALITY,92])
            if not ok:raise RuntimeError('Frame encoding failed')
            encode_ms=(time.perf_counter()-started)*1000-neural_ms-compose_ms
        return {'source_lip':self.composite.source_lip,'mouth_detected':self.composite.source_lip is not None,'image':base64.b64encode(jpeg).decode(),'patch':self.composite.bounds if patch_only else None,'content_type':kind,'transparent':transparent,'alpha_embedded':transparent,'accelerated':bool(self.graph),'compiled':self.compiled,'render_ms':round((time.perf_counter()-started)*1000,1),'neural_ms':round(neural_ms,1),'compose_ms':round(compose_ms,1),'encode_ms':round(encode_ms,1),'device':self.device}


def main():
    output=sys.stdout;engine=None
    for line in sys.stdin:
        try:
            with contextlib.redirect_stdout(sys.stderr):
                if engine is None:engine=LivePortrait()
                result=engine.frame(json.loads(line))
            print(json.dumps({'type':'result',**result}),file=output,flush=True)
            print('{"type":"done"}',file=output,flush=True)
        except Exception as error:
            import traceback
            traceback.print_exc(file=sys.stderr)
            print(json.dumps({'type':'error','message':str(error)}),file=output,flush=True)


if __name__=='__main__':main()
