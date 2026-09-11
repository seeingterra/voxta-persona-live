"""Local, one-time source-mouth measurement. No downloads at inference time."""
import numpy as np


def mouth_ratio(points):
    points=np.asarray(points,dtype=float)
    width=np.linalg.norm(points[61,:2]-points[291,:2])
    if width<1e-6:raise ValueError('Degenerate mouth landmarks')
    return float(np.clip(np.linalg.norm(points[13,:2]-points[14,:2])/width,0,.5))


def eye_ratios(points):
    points=np.asarray(points,dtype=float)
    pairs=((159,145,33,133),(386,374,362,263))
    ratios=[]
    for upper,lower,inner,outer in pairs:
        width=np.linalg.norm(points[inner,:2]-points[outer,:2])
        if width<1e-6:raise ValueError('Degenerate eye landmarks')
        ratios.append(float(np.clip(np.linalg.norm(points[upper,:2]-points[lower,:2])/width,0,.5)))
    return tuple(ratios)


class SourceLandmarks:
    def __init__(self,path):
        import mediapipe as mp
        self.mp=mp
        self.detector=mp.tasks.vision.FaceLandmarker.create_from_options(
            mp.tasks.vision.FaceLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=str(path)),
                running_mode=mp.tasks.vision.RunningMode.IMAGE,num_faces=1,
                min_face_detection_confidence=.5,min_face_presence_confidence=.5))

    def measure(self,rgb):
        result=self._detect(rgb)
        if not result.face_landmarks:return None
        h,w=rgb.shape[:2]
        points=[[p.x*w,p.y*h] for p in result.face_landmarks[0]]
        return mouth_ratio(points)

    def measure_eyes(self,rgb):
        result=self._detect(rgb)
        if not result.face_landmarks:return None
        h,w=rgb.shape[:2]
        points=[[p.x*w,p.y*h] for p in result.face_landmarks[0]]
        return eye_ratios(points)

    def _detect(self,rgb):
        return self.detector.detect(self.mp.Image(image_format=self.mp.ImageFormat.SRGB,data=np.ascontiguousarray(rgb)))
