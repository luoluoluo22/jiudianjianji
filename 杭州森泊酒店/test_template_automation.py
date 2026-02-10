import os
import sys
import shutil
import json
import re

# 1. 环境初始化
skill_root = r"f:\Desktop\kaifa\jianying-editor-skill\.agent\skills\jianying-editor"
sys.path.insert(0, os.path.join(skill_root, "scripts"))
from jy_wrapper import JyProject, get_default_drafts_root
import pyJianYingDraft as draft

def get_video_duration(file_path):
    """获取视频物理时长 (微秒)"""
    try:
        mat = draft.VideoMaterial(file_path)
        return mat.duration
    except: return 0

def fix_json_ultimate(file_path, local_root, replacements, new_display_name):
    """终极 JSON 修复：路径重连、清空 ID、重命名"""
    if not os.path.exists(file_path): return
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    def walk_and_fix(obj):
        if isinstance(obj, dict):
            for k, v in list(obj.items()):
                # 1. 路径修复与强制重连
                if k.lower() in ['path', 'file_path'] and isinstance(v, str) and "Z:/" in v:
                    filename = os.path.basename(v)
                    if filename in replacements:
                        obj[k] = replacements[filename]["new_path"]
                        if "material_name" in obj: obj["material_name"] = filename
                    else:
                        obj[k] = os.path.join(local_root, filename).replace("\\", "/")

                    # 关键：清空 local_material_id 强制剪映重新识别物理文件
                    if "local_material_id" in obj:
                        obj["local_material_id"] = ""

                # 2. 清理残留名称 (如 "高梦雅" -> "黄茜")
                elif isinstance(v, str) and "高梦雅" in v:
                    obj[k] = v.replace("高梦雅", new_display_name)

                # 递归
                else:
                    walk_and_fix(v)
        elif isinstance(obj, list):
            for item in obj: walk_and_fix(item)

    walk_and_fix(data)

    # 特殊补丁：Meta 和 VirtualStore 的全局显示名称
    if "draft_fold_path" in data:
        data["draft_fold_path"] = data["draft_fold_path"].replace("高梦雅", new_display_name)

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    # 配置
    project_name = "模板替换-终极完美修复版"
    template_dir = r"F:\Desktop\kaifa\jianying-editor-skill\杭州森泊酒店\杭州森泊工程模版\杭州开元森泊20S"
    asset_base = r"F:\Desktop\kaifa\jianying-editor-skill\杭州森泊酒店\杭州开元森泊素材\0128\阿琪5单5条\20260128黄茜20s"
    local_assets_root = r"F:\Desktop\kaifa\jianying-editor-skill\杭州森泊酒店\杭州森泊工程模版"

    # 替换配置
    repl_map = {
        "PXMX0789.MP4": {"new_path": os.path.join(asset_base, "C2708.MP4").replace("\\", "/"), "start": 3000000},
        "PXMX0790.MP4": {"new_path": os.path.join(asset_base, "C2709.MP4").replace("\\", "/"), "start": 3000000},
        "PXMX0791.MP4": {"new_path": os.path.join(asset_base, "C2710.MP4").replace("\\", "/"), "start": 2000000},
        "PXMX0792.MP4": {"new_path": os.path.join(asset_base, "C2711.MP4").replace("\\", "/"), "start": 1000000}
    }

    drafts_root = get_default_drafts_root()
    dest_path = os.path.join(drafts_root, project_name)

    print(f"[*] 1. 物理克隆品牌模板...")
    if os.path.exists(dest_path): shutil.rmtree(dest_path)
    shutil.copytree(template_dir, dest_path)

    # 2. 深度同步修复三文件
    print(f"[*] 2. 正在执行三文件深度同步 (Content, Meta, VirtualStore)...")
    target_files = ["draft_content.json", "draft_meta_info.json", "draft_virtual_store.json"]
    for f_name in target_files:
        fix_json_ultimate(os.path.join(dest_path, f_name), local_assets_root, repl_map, "黄茜")

    # 3. 对齐时间轴裁剪点
    print(f"[*] 3. 正在同步时间轴裁剪点...")
    content_path = os.path.join(dest_path, "draft_content.json")
    with open(content_path, 'r', encoding='utf-8') as f:
        content_data = json.load(f)

    # 建立 ID 映射 (基于路径匹配)
    mat_id_to_start = {}
    for mat in content_data["materials"]["videos"]:
        m_path = mat.get("path", "").lower()
        for old_name, cfg in repl_map.items():
            if cfg["new_path"].lower() in m_path:
                mat_id_to_start[mat["id"]] = cfg["start"]

    for track in content_data["tracks"]:
        if track["type"] == "video":
            for seg in track["segments"]:
                mid = seg["material_id"]
                if mid in mat_id_to_start:
                    seg["source_timerange"]["start"] = mat_id_to_start[mid]

    with open(content_path, 'w', encoding='utf-8') as f:
        json.dump(content_data, f, ensure_ascii=False, indent=4)

    # 4. 交付保存
    p = JyProject(project_name, drafts_root=drafts_root, overwrite=False)
    p.save()

    print(f"\n✅ 终极全量修复完成！请打开剪映确认项目: {project_name}")
    print(f"改进：清空 local_material_id 强制重连 + VirtualStore 彻底清洗。")
