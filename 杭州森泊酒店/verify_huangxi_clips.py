import os
import sys

# 1. 环境初始化
skill_root = r"f:\Desktop\kaifa\jianying-editor-skill\.agent\skills\jianying-editor"
sys.path.insert(0, os.path.join(skill_root, "scripts"))
from jy_wrapper import JyProject

if __name__ == "__main__":
    # 创建验证项目
    project_name = "AI智能筛选验证-黄茜-动态优先版"
    project = JyProject(project_name)

    asset_base = r"F:\Desktop\kaifa\jianying-editor-skill\杭州森泊酒店\杭州开元森泊素材\0128\阿琪5单5条\20260128黄茜20s"

    print("🎬 正在应用 [AI动态优先分析] 结果生成项目...")

    # 1. 视频 1：C2708 - 避开静止起步
    # AI 建议：03s - 06s
    project.add_clip(os.path.join(asset_base, "C2708.MP4"), target_start="0s", source_start="3s", duration="3s")
    project.add_text_simple("AI动态筛选：避开静止起步 (3s-6s)", start_time="0s", duration="3s")

    # 2. 视频 2：C2709 - 动态攀爬瞬间
    # AI 建议：03s - 06s
    project.add_clip(os.path.join(asset_base, "C2709.MP4"), target_start="3s", source_start="3s", duration="3s")
    project.add_text_simple("AI动态筛选：动态攀爬瞬间 (3s-6s)", start_time="3s", duration="3s")

    # 3. 视频 3：C2710 - 迎向镜头互动
    # AI 建议：02s - 05s
    project.add_clip(os.path.join(asset_base, "C2710.MP4"), target_start="6s", source_start="2s", duration="3s")
    project.add_text_simple("AI动态筛选：迎向镜头互动 (2s-5s)", start_time="6s", duration="3s")

    # 4. 视频 4：C2711 - 流畅侧拉镜头
    # AI 建议：01s - 04s
    project.add_clip(os.path.join(asset_base, "C2711.MP4"), target_start="9s", source_start="1s", duration="3s")
    project.add_text_simple("AI动态筛选：流畅侧拉镜头 (1s-4s)", start_time="9s", duration="3s")

    # 5. 视频 5：C2712 - 自然生活瞬间
    # AI 建议：00s - 03s
    project.add_clip(os.path.join(asset_base, "C2712.MP4"), target_start="12s", source_start="0s", duration="3s")
    project.add_text_simple("AI动态筛选：自然生活瞬间 (0s-3s)", start_time="12s", duration="3s")

    project.save()
    print(f"✅ 项目 '{project_name}' 已生成，请在剪映中查看。")
