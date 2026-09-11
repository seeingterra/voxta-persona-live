import numpy as np
from PIL import Image
from pathlib import Path
from backend.live_motion import NaturalMotion


def test_composite_preserves_alpha_and_silhouette(tmp_path):
    import pytest
    pytest.importorskip("cv2")
    from backend.live_composite import PortraitComposite
    rgba=np.zeros((128,128,4),dtype=np.uint8)
    rgba[:,:,:3]=[170,110,80]
    rgba[15:115,25:105,3]=255
    rgba[15:115,24,3]=80
    path=tmp_path/'source.png';Image.fromarray(rgba).save(path)
    composite=PortraitComposite(path,lambda _:np.array([40,25,45,55]))
    result=composite.apply(np.full((512,512,3),230,dtype=np.uint8))
    np.testing.assert_array_equal(result[:,:,3],composite.rgba[:,:,3])
    np.testing.assert_array_equal(result[15:115,24],composite.rgba[15:115,24])
    assert np.any(result[:,:,:3]!=rgba[:,:,:3])


def test_advanced_body_motion_deforms_only_transparent_lower_body(tmp_path):
    import pytest
    pytest.importorskip("cv2")
    from backend.live_composite import PortraitComposite
    rgba=np.zeros((128,128,4),dtype=np.uint8)
    rgba[:,:,:3]=[170,110,80]
    rgba[12:120,24:104,3]=255
    path=tmp_path/'source.png';Image.fromarray(rgba).save(path)
    composite=PortraitComposite(path,lambda _:np.array([44,16,40,40]))
    face=np.full((512,512,3),230,dtype=np.uint8)
    normal=composite.apply(face)
    advanced=composite.apply(face,body_motion=(.012,.006,.004))
    assert advanced.shape==normal.shape==(128,128,4)
    np.testing.assert_array_equal(advanced[:composite.body_start,:,:],normal[:composite.body_start,:,:])
    assert np.any(advanced[composite.body_start:,:,:]!=normal[composite.body_start:,:,:])


def test_advanced_body_motion_is_disabled_for_opaque_sources(tmp_path):
    import pytest
    pytest.importorskip("cv2")
    from backend.live_composite import PortraitComposite
    image=np.full((128,128,3),[170,110,80],dtype=np.uint8)
    path=tmp_path/'source.jpg';Image.fromarray(image).save(path)
    composite=PortraitComposite(path,lambda _:np.array([44,16,40,40]))
    face=np.full((512,512,3),230,dtype=np.uint8)
    np.testing.assert_array_equal(composite.apply(face),composite.apply(face,body_motion=(.012,.006,.004)))


def test_motion_is_smooth_and_blinks_are_irregular():
    motion=NaturalMotion(seed=12);previous=None;starts=[];was_blink=False
    for i in range(1800):
        value=motion.update(i/30,0,'idle',[0,0],'neutral')
        if previous is not None:assert max(abs(a-b) for a,b in zip(value[:3],previous[:3]))<.08
        if value[3]>0 and not was_blink:starts.append(i/30)
        was_blink=value[3]>0;previous=value
        assert value[4]==0
    assert len(starts)>5
    assert np.std(np.diff(starts))>.3


def test_advanced_body_motion_is_bounded():
    motion=NaturalMotion(seed=2)
    for i in range(600):
        breath,settle,rise=motion.body(i/30,'speaking')
        assert abs(breath)<=.0032
        assert abs(settle)<=.0026
        assert abs(rise)<=.0015


def test_mouth_releases_after_speech():
    motion=NaturalMotion(seed=3)
    for i in range(30):motion.update(i/30,.5,'speaking',[0,0],'warm')
    assert motion.mouth>.4
    for i in range(30,60):motion.update(i/30,.5,'idle',[0,0],'neutral')
    assert motion.mouth<.001


def test_gaze_jump_is_speed_limited_at_low_fps():
    motion=NaturalMotion(seed=1)
    for i in range(50):
        before=list(motion.gaze)
        value=motion.update(i/9,0,'idle',[1 if i%2 else -1,1],'neutral')
        assert max(abs(a-b) for a,b in zip(before,value[7]))<=.65/9+1e-6
        assert max(abs(x) for x in value[7])<=.65


def test_mouth_measurement_is_scale_invariant():
    from backend.live_landmarks import mouth_ratio
    points=np.zeros((478,2));points[61]=[10,20];points[291]=[50,20]
    points[13]=[30,19];points[14]=[30,21]
    assert abs(mouth_ratio(points)-.05)<1e-8
    points[14]=[30,29]
    assert abs(mouth_ratio(points)-.25)<1e-8
    assert mouth_ratio(points)==mouth_ratio(points*3)


def test_eye_measurement_is_scale_invariant():
    from backend.live_landmarks import eye_ratios
    points=np.zeros((478,2))
    points[33]=[10,20];points[133]=[50,20];points[159]=[30,18];points[145]=[30,22]
    points[362]=[60,20];points[263]=[100,20];points[386]=[80,18];points[374]=[80,22]
    assert eye_ratios(points)==(.1,.1)
    assert eye_ratios(points)==eye_ratios(points*3)


def test_blink_reaches_full_closure_and_has_visible_duration():
    motion=NaturalMotion(seed=4);values=[]
    for i in range(300):
        values.append(motion.update(i/30,0,'idle',[0,0],'neutral')[3])
    assert max(values)>.99
    assert sum(value>.5 for value in values)>=6


def test_live_view_package_embeds_only_the_live_renderer():
    build = (Path(__file__).parents[1] / "scripts" / "Build-VoxtaModule.ps1").read_text(encoding="utf-8")
    project = (Path(__file__).parents[1] / "module" / "Voxta.Modules.LiveView" / "Voxta.Modules.LiveView.csproj").read_text(encoding="utf-8")
    assert 'LogicalName="runtime/backend/live_bootstrap.py"' in project
    assert 'Include="../../vendor/liveportrait/src/**/*"' in project
    assert 'LogicalName="runtime/vendor/liveportrait/src/%(RecursiveDir)%(Filename)%(Extension)"' in project
    assert "portrait_worker.py" not in project
    assert "../../backend/models.py" not in project
    assert "Copy-Item -LiteralPath (Join-Path $workspace 'module\\Voxta.Modules.LiveView\\bin\\Release\\net10.0\\Voxta.Modules.LiveView.dll')" in build


def test_live_view_detects_voxta_python_without_exposing_a_path_setting():
    configuration = (Path(__file__).parents[1] / "module" / "Voxta.Modules.LiveView" / "LiveViewConfiguration.cs").read_text(encoding="utf-8")
    host = (Path(__file__).parents[1] / "module" / "Voxta.Modules.LiveView" / "RendererHost.cs").read_text(encoding="utf-8")
    assert "PythonPath" not in configuration
    assert 'Directory.EnumerateDirectories(pythonRoot,"python-*-amd64")' in host


def test_live_view_model_validation_accepts_the_health_check_signature():
    from backend.live_models import verify
    assert verify("unknown", dependencies=False)["valid"] is False


def test_live_view_bootstrap_installs_required_landmark_model():
    bootstrap = (Path(__file__).parents[1] / "backend" / "live_bootstrap.py").read_text(encoding="utf-8")
    assert '"face_landmarker.task"' in bootstrap
    assert "storage.googleapis.com/mediapipe-models/face_landmarker/" in bootstrap
    assert 'DATA / "models" / "portrait_landmarks"' in bootstrap


def test_live_renderer_avoids_saturated_gpus():
    from backend.hardware import select_live_device
    assert select_live_device([
        {"uuid": "GPU-small", "total_mb": 8192, "free_mb": 4300},
        {"uuid": "GPU-large", "total_mb": 16384, "free_mb": 3400},
    ]) == "cpu"
    assert select_live_device([
        {"uuid": "GPU-small", "total_mb": 8192, "free_mb": 6000},
        {"uuid": "GPU-large", "total_mb": 16384, "free_mb": 11000},
    ]) == "GPU-small"


def test_live_renderer_requires_landmark_receipt_and_bounds_hung_renders():
    inference = (Path(__file__).parents[1] / "backend" / "inference.py").read_text(encoding="utf-8")
    bridge = (Path(__file__).parents[1] / "backend" / "voxta.py").read_text(encoding="utf-8")
    assert "ready('portrait_landmarks')" in inference
    assert "timeout=30" in bridge
    assert "render timed out after" in inference


def test_native_proxy_allows_in_chat_hardware_and_usage_endpoints():
    startup = (Path(__file__).parents[1] / "module" / "Voxta.Modules.LiveView" / "LiveViewStartup.cs").read_text(encoding="utf-8")
    assert '"/api/voxta/hardware"' in startup
    assert '"/api/voxta/usage"' in startup


def test_live_bootstrap_requires_current_complete_setup():
    bootstrap = (Path(__file__).parents[1] / "backend" / "live_bootstrap.py").read_text(encoding="utf-8")
    host = (Path(__file__).parents[1] / "module" / "Voxta.Modules.LiveView" / "RendererHost.cs").read_text(encoding="utf-8")
    assert "BOOTSTRAP_REVISION = 2" in bootstrap
    assert '"revision": BOOTSTRAP_REVISION' in bootstrap
    assert 'folder / "receipt.json"' in bootstrap
    assert 'revision.GetInt32()==2' in host


def test_live_view_worker_configures_its_own_liveportrait_import_path():
    worker = (Path(__file__).parents[1] / "backend" / "live_worker.py").read_text(encoding="utf-8")
    assert 'LIVEPORTRAIT_ROOT = ROOT / "vendor" / "liveportrait"' in worker
    assert "sys.path.insert(0, str(LIVEPORTRAIT_ROOT))" in worker
