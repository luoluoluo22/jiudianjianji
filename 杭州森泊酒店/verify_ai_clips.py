import os
import sys

# 1. 环境初始化 (必须同步到脚本开头)
# 探测 Skill 路径
skill_root = r"f:\Desktop\kaifa\jianying-editor-skill\.agent\skills\jianying-editor"
sys.path.insert(0, os.path.join(skill_root, "scripts"))
from jy_wrapper import JyProject

if __name__ == "__main__":
    # 创建验证项目
    project_name = "AI智能筛选验证-陈桑桑"
    project = JyProject(project_name)
    
    asset_base = r"F:\Desktop\kaifa\jianying-editor-skill\杭州森泊酒店\杭州开元森泊素材\0128\阿琪5单5条\20260128陈桑桑20s"
    
    print("🎬 正在根据 AI 建议剪辑素材...")
    
    # 1. 视频 1：木屋楼梯（小女孩）
    # AI 建议：00:04 - 00:07 (理由：避开静止起步，动作最连贯)
    project.add_clip(os.path.join(asset_base, "C2700.MP4"), source_start="4s", duration="3s")
    project.add_text_simple("AI筛选：避开静止起步 (4s-7s)", start_time="0s", duration="3s")
    
    # 2. 视频 2：观景台合影（母子三人）
    # AI 建议：00:02 - 00:05 (理由：包含挥手动作)
    project.add_clip(os.path.join(asset_base, "C2701.MP4"), source_start="2s", duration="3s")
    project.add_text_simple("AI筛选：捕捉挥手动作 (2s-5s)", start_time="3s", duration="3s")
    
    # 3. 视频 3：玻璃房看羊（小女孩）
    # AI 建议：00:03 - 00:06 (理由：回头微笑正脸，避开末尾剧烈抖动)
    project.add_clip(os.path.join(asset_base, "C2702.MP4"), source_start="3s", duration="3s")
    project.add_text_simple("AI筛选：回头微笑+防抖 (3s-6s)", start_time="6s", duration="3s")
    
    project.save()
    print(f"✅ 项目 '{project_name}' 已生成，请在剪映中查看。")
