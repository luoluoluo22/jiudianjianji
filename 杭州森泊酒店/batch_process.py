import os
import sys
import shutil
import re
import json

# 1. 环境初始化
current_dir = os.path.dirname(os.path.abspath(__file__))
skill_root = os.path.abspath(r"f:\Desktop\kaifa\jianying-editor-skill\.agent\skills\jianying-editor")
sys.path.insert(0, os.path.join(skill_root, "scripts"))
sys.path.insert(0, os.path.join(skill_root, "references"))

from jy_wrapper import get_default_drafts_root
import pyJianYingDraft as draft

# 2. 路径配置
PROJECT_ROOT = r"F:\Desktop\杭州森泊酒店"
ASSETS_DIR = os.path.join(PROJECT_ROOT, "杭州开元森泊素材")
TEMPLATE_DIR = os.path.join(PROJECT_ROOT, "杭州森泊工程模版", "杭州开元森泊20S")
DRAFTS_ROOT = get_default_drafts_root()

def get_video_duration(file_path):
    """获取视频物理时长 (微秒)"""
    try:
        mat = draft.VideoMaterial(file_path)
        return mat.duration
    except:
        return 0

def extract_name(folder_name):
    match = re.search(r'[\u4e00-\u9fa5]{2,3}', folder_name)
    return match.group(0) if match else folder_name

def patch_draft_with_fitting(project_path, client_videos):
    content_path = os.path.join(project_path, "draft_content.json")
    with open(content_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # --- 1. 更新 Material 库中的路径和物理时长 ---
    video_mats = data["materials"]["videos"]
    # 客户素材索引 2, 3, 4, 5
    actual_durations = {} # local_material_id -> duration
    
    for i in range(4):
        idx = i + 2
        new_path = client_videos[i].replace("/", "\\")
        phys_dur = get_video_duration(new_path)
        
        video_mats[idx]["path"] = new_path
        video_mats[idx]["duration"] = phys_dur
        video_mats[idx]["material_name"] = os.path.basename(new_path)
        actual_durations[video_mats[idx]["id"]] = phys_dur

    # 修正固定素材路径
    video_mats[0]["path"] = os.path.join(PROJECT_ROOT, "杭州森泊工程模版", "开幕森泊.mp4")
    video_mats[1]["path"] = os.path.join(PROJECT_ROOT, "杭州森泊工程模版", "水乐园环绕.mp4")
    video_mats[6]["path"] = os.path.join(PROJECT_ROOT, "杭州森泊工程模版", "杭州森泊X屹奇旅拍logo.jpg")

    # --- 2. 遍历轨道进行动态适配 (防止静止帧) ---
    # 我们要找 MainVideo 轨道 (在模板中通常是第一个视频轨)
    for track in data["tracks"]:
        if track["type"] == "video":
            for seg in track["segments"]:
                mat_id = seg["material_id"]
                if mat_id in actual_durations:
                    phys_dur = actual_durations[mat_id]
                    
                    target_dur = seg["target_timerange"]["duration"] # 轨道上占用的坑位长度
                    orig_source_dur = seg["source_timerange"]["duration"] # 模板原本想用的长度
                    
                    # 如果原片长度不足以支持原本的切片长度
                    if phys_dur < orig_source_dur:
                        print(f"  📏 长度不足适配: 素材 {phys_dur/1e6}s < 需求 {orig_source_dur/1e6}s")
                        # 强行将 source 处理为原片全长，防止静止帧
                        seg["source_timerange"]["duration"] = phys_dur
                        seg["source_timerange"]["start"] = 0 # 从头开始拿
                        
                        # 此时由于坑位 (target_dur) 不变，我们必须调整速度
                        # Speed = source_dur / target_dur
                        new_speed_val = phys_dur / target_dur
                        
                        # 在 materials.speeds 中找到对应的速度对象并更新
                        speed_ref_id = None
                        for ref in seg["extra_material_refs"]:
                            for s_mat in data["materials"]["speeds"]:
                                if s_mat["id"] == ref:
                                    s_mat["speed"] = new_speed_val
                                    print(f"    🚀 动态调速: {new_speed_val:.2f}x")
                                    break

    with open(content_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def process_client(folder_path):
    folder_name = os.path.basename(folder_path)
    client_name = extract_name(folder_name)
    videos = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.lower().endswith(('.mp4', '.mov'))]
    if len(videos) < 4: return

    videos.sort()
    
    # 优化命名：如果文件夹名包含数字后缀 (比如 20S 1, 20S 2)，也包含进项目名中
    suffix_match = re.search(r'20s\s*(\d)', folder_name.lower())
    suffix = f"-{suffix_match.group(1)}" if suffix_match else ""
    
    project_name = f"杭州森泊-20S-{client_name}{suffix}"
    dest_path = os.path.join(DRAFTS_ROOT, project_name)

    print(f"🎬 正在【动态适配】生成项目: {project_name}")
    if os.path.exists(dest_path): shutil.rmtree(dest_path)
    shutil.copytree(TEMPLATE_DIR, dest_path)
    
    # 路径注入 + 动态调速适配
    patch_draft_with_fitting(dest_path, videos)
    
    # 刷新剪映列表
    meta_path = os.path.join(dest_path, "draft_meta_info.json")
    if os.path.exists(meta_path):
        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = json.load(f)
        meta["draft_name"] = project_name
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=4)
            
    # 调用 wrapper 刷新 root_meta
    from jy_wrapper import JyProject
    p = JyProject(project_name, overwrite=False)
    p.save()
    print(f"✅ {project_name} 完成\n")

def main():
    target_folders = []
    for root, dirs, files in os.walk(ASSETS_DIR):
        for d in dirs:
            if "20s" in d.lower():
                target_folders.append(os.path.join(root, d))
    for folder in target_folders:
        try:
            process_client(folder)
        except Exception as e:
            print(f"❌ 失败 {folder}: {e}")

if __name__ == "__main__":
    main()
