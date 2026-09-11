"""One coordinate system and cached, feathered blending for live portraits."""
import cv2
import numpy as np
from PIL import Image


class PortraitComposite:
    def __init__(self,path,detector):
        original=Image.open(path).convert('RGBA')
        original.thumbnail((960,960),Image.Resampling.LANCZOS)
        self.rgba=np.array(original)
        self.base=self.rgba[:,:,:3].copy()
        self.matte=self.rgba[:,:,3]
        self.transparent=bool(self.matte.min()<255)
        if self.transparent:
            # Repair small staircase/speck artifacts in authored cutouts once per image.
            opened=cv2.morphologyEx(self.matte,cv2.MORPH_OPEN,np.ones((3,3),np.uint8))
            trimmed=cv2.erode(opened,np.ones((3,3),np.uint8))
            self.matte=cv2.GaussianBlur(trimmed,(3,3),.55)
            self.rgba[:,:,3]=self.matte
        a=self.matte.astype(np.float32)[...,None]/255
        model_rgb=np.rint(self.base*a+235*(1-a)).astype(np.uint8)
        x,y,w,h=detector(model_rgb)[:4]
        side=max(2,int(max(w,h)*2.3))
        left,top=int(x+w/2-side/2),int(y+h*.55-side/2)
        padded=cv2.copyMakeBorder(model_rgb,side,side,side,side,cv2.BORDER_REFLECT_101)
        self.crop=cv2.resize(padded[top+side:top+2*side,left+side:left+2*side],(512,512),interpolation=cv2.INTER_LANCZOS4)
        height,width=self.base.shape[:2]
        x0,y0=max(0,left),max(0,top);x1,y1=min(width,left+side),min(height,top+side)
        self.region=(slice(y0,y1),slice(x0,x1))
        self.bounds={'x':x0,'y':y0,'width':x1-x0,'height':y1-y0,'canvas_width':width,'canvas_height':height}
        self.patch_region=(slice(y0-top,y1-top),slice(x0-left,x1-left))
        self.side=side
        yy,xx=np.mgrid[0:side,0:side].astype(np.float32)/(side-1)
        radius=np.sqrt(((xx-.5)/.36)**2+((yy-.48)/.43)**2)
        blend=np.clip((1-radius)/.34,0,1)
        blend=blend*blend*(3-2*blend)
        # Preserve authored hair/cloth silhouette pixels instead of tinting their alpha fringe.
        interior=cv2.erode(self.matte,np.ones((3,3),np.uint8)).astype(np.float32)/255
        self.alpha=(blend[self.patch_region]*interior[self.region])[...,None]
        self.original=self.base[self.region].astype(np.float32)
        self.correction=None
        self.body_start=min(height-1,max(0,int(y+h*.6)))
        self.body_center=float(x+w*.5)
        self.transition=max(12,int(h*.45))
        self.body_y,self.body_x=np.mgrid[:height,:width].astype(np.float32)

    def calibrate(self,neutral):
        source=cv2.resize(self.crop,(neutral.shape[1],neutral.shape[0]),interpolation=cv2.INTER_AREA)
        difference=source.astype(np.float32)-neutral.astype(np.float32)
        # Match low-frequency illumination only; do not paste static eyes or teeth onto motion.
        self.correction=np.clip(cv2.GaussianBlur(difference,(0,0),9),-18,18)

    def body_frame(self,body_motion):
        if not self.transparent or body_motion is None:return self.rgba.copy()
        breath,settle,rise=body_motion
        height,width=self.base.shape[:2]
        y,x=self.body_y,self.body_x
        amount=np.clip((y-self.body_start)/self.transition,0,1)
        amount=amount*amount*(3-2*amount)
        map_x=x-amount*((x-self.body_center)*breath+settle*width)
        map_y=y-amount*rise*height
        return cv2.remap(self.rgba,map_x,map_y,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT,borderValue=(0,0,0,0))

    def apply(self,frame,patch_only=False,body_motion=None):
        if patch_only and body_motion is not None:raise ValueError('Body motion requires a full frame')
        if self.correction is not None:
            frame=np.clip(frame.astype(np.float32)+self.correction,0,255).astype(np.uint8)
        patch=cv2.resize(frame,(self.side,self.side),interpolation=cv2.INTER_CUBIC)[self.patch_region]
        result=(self.rgba[self.region] if patch_only else self.body_frame(body_motion))
        original=(self.original if patch_only else result[self.region[0],self.region[1],:3].astype(np.float32))
        blended=np.rint(original+(patch.astype(np.float32)-original)*self.alpha).clip(0,255).astype(np.uint8)
        if patch_only:result[:,:,:3]=blended
        else:result[self.region[0],self.region[1],:3]=blended
        return result if self.transparent else result[:,:,:3]
