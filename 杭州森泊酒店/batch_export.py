import os
import sys
import re
import time

# 1. 环境初始化
current_dir = os.path.dirname(os.path.abspath(__file__))
skill_root = os.path.abspath(r"f:\Desktop\kaifa\jianying-editor-skill\.agent\skills\jianying-editor")
sys.path.insert(0, os.path.join(skill_root, "scripts"))
sys.path.insert(0, os.path.join(skill_root, "references"))

import pyJianYingDraft as draft

# 2. 路径配置
PROJECT_ROOT = r"F:\Desktop\杭州森泊酒店"
ASSETS_DIR = os.path.join(PROJECT_ROOT, "杭州开元森泊素材")
OUTPUT_ROOT = os.path.join(PROJECT_ROOT, "杭州开元森泊成片")

def extract_name(folder_name):
    match = re.search(r'[\u4e00-\u9fa5]{2,3}', folder_name)
    return match.group(0) if match else folder_name

def get_export_tasks():
    tasks = []
    for root, dirs, files in os.walk(ASSETS_DIR):
        for d in dirs:
            if "20s" in d.lower():
                folder_path = os.path.join(root, d)
                
                # 检查视频素材是否足够 (至少4个)
                videos = [f for f in os.listdir(folder_path) if f.lower().endswith(('.mp4', '.mov'))]
                if len(videos) < 4:
                    continue
                
                # 提取日期 (素材目录下的一级目录)
                rel_path = os.path.relpath(folder_path, ASSETS_DIR)
                date_str = rel_path.split(os.sep)[0]
                
                # 提取客户名和项目名
                client_name = extract_name(d)
                suffix_match = re.search(r'20s\s*(\d)', d.lower())
                suffix = f"-{suffix_match.group(1)}" if suffix_match else ""
                
                project_name = f"杭州森泊-20S-{client_name}{suffix}"
                file_name = f"{client_name}{suffix}.mp4"
                
                output_dir = os.path.join(OUTPUT_ROOT, date_str)
                output_path = os.path.join(output_dir, file_name)
                
                tasks.append({
                    "project_name": project_name,
                    "output_path": output_path,
                    "output_dir": output_dir
                })
    return tasks

def main():
    print("🚀 正在扫描待导出项目...")
    tasks = get_export_tasks()
    print(f"🔍 找到 {len(tasks)} 个导出任务")
    
    if not tasks:
        return

    # 初始化剪映控制器
    print("⚠️ 注意：批量导出将控制您的鼠标和键盘，请在执行期间不要操作电脑。")
    print("⌨️ 正在尝试连接剪映专业版...")
    
    try:
        ctrl = draft.JianyingController()
    except Exception as e:
        print(f"❌ 无法连接到剪映: {e}")
        print("💡 请确保已打开剪映专业版并停留在主界面。")
        return

    for i, task in enumerate(tasks):
        p_name = task["project_name"]
        o_path = task["output_path"]
        o_dir = task["output_dir"]
        
        print(f"\n🎬 [{i+1}/{len(tasks)}] 正在导出: {p_name}")
        
        # 确保输出目录存在
        if not os.path.exists(o_dir):
            os.makedirs(o_dir)
            
        # 检查是否已经存在 (可选跳过)
        if os.path.exists(o_path):
            print(f"⏩ 跳过: {o_path} 已存在")
            continue
            
        try:
            # 执行导出
            # 默认使用 1080P, 30FPS
            ctrl.export_draft(p_name, o_path, resolution=draft.ExportResolution.RES_1080P, framerate=draft.ExportFramerate.FR_30)
            print(f"✅ 导出成功: {o_path}")
            # 给系统一点喘息时间
            time.sleep(2)
        except Exception as e:
            print(f"❌ 导出失败 {p_name}: {e}")
            # 如果连续失败，可能需要检查 UI 状态
            continue

    print("\n✨ 所有导出任务处理完毕！")

if __name__ == "__main__":
    main()
