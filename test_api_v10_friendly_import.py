
import os
import sys

# 注入路径
skill_root = r"f:\Desktop\kaifa\jianying-editor-skill\.agent\skills\jianying-editor"
sys.path.insert(0, os.path.join(skill_root, "scripts"))

from jy_wrapper import JyProject

def run_friendly_import():
    # 外部模板路径
    external_template = r"f:\Desktop\kaifa\jianying-editor-skill\杭州森泊酒店\杭州森泊工程模版"
    official_name = "森泊正式生产模板_V2_交互测试"
    
    print(f"[*] 第 1 步：尝试导入外部工程: {official_name}")
    try:
        # 1. 执行物理挂载 (导入)
        p = JyProject.import_external_draft(external_template, new_name=official_name)
        
        # 2. 主动诊断：检测缺失物料
        missing = p.get_missing_assets()
        
        if missing:
            print(f"\n⚠️  [AI 深度诊断]: 检测到工程中有 {len(missing)} 个素材物理丢失！")
            for m in missing:
                print(f"  - 🔴 文件: {m['name']}")
                print(f"    ↘ 原始位置: {m['orig_path']}")
            
            print(f"\n[*] 根据您的反馈，我将从本地备份目录尝试找回这些素材...")
            # 模拟用户告知了路径：f:\Desktop\kaifa\jianying-editor-skill\杭州森泊酒店\杭州开元森泊素材
            asset_root = r"f:\Desktop\kaifa\jianying-editor-skill\杭州森泊酒店\杭州开元森泊素材"
            
            p.reconnect_all_assets(asset_root)
            
            # 再次检查
            still_missing = p.get_missing_assets()
            if not still_missing:
                print("✅ 完美！所有素材已找回，项目恢复健康状态。")
                p.save()
            else:
                print(f"⚠️ 依然缺少 {len(still_missing)} 个素材，请确认存放路径。")
        else:
            print("✅ 运气真好！该工程没有丢失任何素材。")
            
    except Exception as e:
        print(f"❌ 导入失败: {e}")

if __name__ == "__main__":
    run_friendly_import()
