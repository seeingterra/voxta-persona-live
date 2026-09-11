"""Equivalent device-local coordinate/heatmap construction for LivePortrait.

The upstream implementation copies tiny CPU tensors to CUDA during each frame.
Keeping these tensors on device permits CUDA graph capture without changing weights.
The corresponding MIT upstream code/notices remain in vendor/liveportrait.
"""
def install(model):
    import types
    import torch
    from src.modules import util,dense_motion
    grids={}
    def grid(spatial_size,ref,**_kwargs):
        key=(tuple(spatial_size),ref.dtype,ref.device)
        if key not in grids:
            d,h,w=spatial_size
            x=2*(torch.arange(w,device=ref.device,dtype=ref.dtype)/(w-1))-1
            y=2*(torch.arange(h,device=ref.device,dtype=ref.dtype)/(h-1))-1
            z=2*(torch.arange(d,device=ref.device,dtype=ref.dtype)/(d-1))-1
            zz,yy,xx=torch.meshgrid(z,y,x,indexing='ij')
            grids[key]=torch.stack((xx,yy,zz),dim=-1)
        return grids[key]
    def heatmap(self,feature,kp_driving,kp_source):
        size=feature.shape[3:]
        delta=util.kp2gaussian(kp_driving,size,.01)-util.kp2gaussian(kp_source,size,.01)
        return torch.cat((torch.zeros_like(delta[:,:1]),delta),dim=1).unsqueeze(2)
    util.make_coordinate_grid=grid;dense_motion.make_coordinate_grid=grid
    network=model.warping_module.dense_motion_network
    network.create_heatmap_representations=types.MethodType(heatmap,network)
