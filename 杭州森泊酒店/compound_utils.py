import os
import sys
import uuid
import json

# 1. 环境初始化
current_dir = os.path.dirname(os.path.abspath(__file__))
skill_root = os.path.abspath(r"f:\Desktop\kaifa\jianying-editor-skill\.agent\skills\jianying-editor")
sys.path.insert(0, os.path.join(skill_root, "scripts"))
sys.path.insert(0, os.path.join(skill_root, "references"))

from jy_wrapper import JyProject
import pyJianYingDraft as draft

class MockVideoMaterial:
    """跳过物理文件检测的伪视频素材类"""
    def __init__(self, material_id, duration, name):
        self._id = material_id
        self.duration = duration
        self.material_name = name
    
    @property
    def material_id(self): return self._id

    def export_json(self):
        return {
            "id": self._id,
            "type": "video",
            "material_name": self.material_name,
            "path": "",
            "extra_type_option": 2, # 核心标识
            "duration": self.duration,
            "height": 1080,
            "width": 1920,
            "category_id": "",
            "category_name": "local",
            "check_flag": 63487,
            "local_material_id": ""
        }

class CompoundSegment(draft.VideoSegment):
    """自定义复合片段 Segment，完全解耦库的依赖"""
    def __init__(self, mock_material, draft_id, duration):
        self.material_instance = mock_material
        self.target_timerange = draft.Timerange(0, duration)
        self.draft_id = draft_id
        self.duration_val = duration
        
        # 兼容基类必要的存根
        self.segment_id = uuid.uuid4().hex.upper()
        self.material_id = mock_material.material_id
        self.common_keyframes = []

    def export_json(self):
        # 纯手工构建复合片段所需的 Segment 协议字典
        return {
            "id": self.segment_id,
            "material_id": self.material_id,
            "extra_material_refs": [self.draft_id],
            "target_timerange": {"start": 0, "duration": self.duration_val},
            "source_timerange": {"start": 0, "duration": self.duration_val},
            "render_index": 0,
            "visible": True,
            "volume": 1.0,
            "speed": 1.0,
            "track_attribute": 0,
            "extra_type_option": 0,
            "clip": {"alpha": 1.0, "flip": {"horizontal": False, "vertical": False}, "rotation": 0.0, "scale": {"x": 1.0, "y": 1.0}, "transform": {"x": 0.0, "y": 0.0}},
            "common_keyframes": [],
            "enable_adjust": True,
            "enable_color_correct_adjust": False,
            "enable_color_curves": True,
            "enable_color_match_adjust": False,
            "enable_color_wheels": True,
            "enable_lut": True,
            "enable_smart_color_adjust": False,
            "hdr_settings": {"intensity": 1.0, "mode": 1, "nits": 1000},
            "responsive_layout": {"enable": False, "horizontal_pos_layout": 0, "size_layout": 0, "target_follow": "", "vertical_pos_layout": 0},
            "uniform_scale": {"on": True, "value": 1.0}
        }
    
    # 模拟 overlaps 方法防止报错
    def overlaps(self, other): return False

def add_compound_clip(main_project, sub_project, clip_name="我的复合片段"):
    main_script = main_project.script
    sub_script = sub_project.script
    
    combination_id = str(uuid.uuid4()).upper()
    draft_material_id = str(uuid.uuid4()).upper()
    video_material_id = str(uuid.uuid4()).upper()
    
    sub_data = json.loads(sub_script.dumps())
    duration = sub_data.get("duration", 0)
    
    # 1. 注入视频素材
    mock_mat = MockVideoMaterial(video_material_id, duration, clip_name)
    main_script.materials.videos.append(mock_mat)
    
    # 2. 注入工程素材 (Hook export_json)
    draft_meta = {
        "id": draft_material_id,
        "combination_id": combination_id,
        "type": "combination",
        "name": clip_name,
        "draft": sub_data
    }
    
    if not hasattr(main_script.materials, "custom_drafts"):
        main_script.materials.custom_drafts = []
        orig_export = main_script.materials.export_json
        def new_export():
            d = orig_export()
            d["drafts"] = main_script.materials.custom_drafts
            return d
        main_script.materials.export_json = new_export
        
    main_script.materials.custom_drafts.append(draft_meta)
    
    # 3. 添加到轨道
    # 如果没轨道，新建一个
    if not main_script.tracks:
        main_script.add_track(draft.TrackType.video, "VideoTrack")
    track = list(main_script.tracks.values())[0]
    
    seg = CompoundSegment(mock_mat, draft_material_id, duration)
    track.add_segment(seg)
    
    main_script.duration = max(main_script.duration, duration)
    print(f"✅ 复合片段 '{clip_name}' 注入完成 (时长: {duration/1e6}s)")
    return seg

def demo_compound():
    rand_id = str(uuid.uuid4())[:8]
    p_name = f"复合演示_{rand_id}"
    
    print(f"🎬 正在生成: {p_name}")
    try:
        p_main = JyProject(p_name, overwrite=True)
        # 为子工程也使用随机名，确保不冲突
        p_sub = JyProject(f"Sub_{rand_id}", overwrite=True)
        p_sub.add_text_simple("这是一个包含在复合片段内的文本", start_time="0s", duration="5s")
        
        add_compound_clip(p_main, p_sub, "我的包装组件")
        p_main.save()
        print(f"🚀 成功生成！请在剪映中查看项目: {p_name}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"❌ 运行报错: {e}")

if __name__ == "__main__":
    demo_compound()
