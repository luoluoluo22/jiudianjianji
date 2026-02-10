
import os
import sys

# 注入路径
skill_root = r"f:\Desktop\kaifa\jianying-editor-skill\.agent\skills\jianying-editor"
sys.path.insert(0, os.path.join(skill_root, "scripts"))

from jy_wrapper import JyProject

def test_external_import_and_fix():
    # 1. 外部模板路径 (用户刚刚拷贝过来的)
    external_template = r"f:\Desktop\kaifa\jianying-editor-skill\杭州森泊酒店\杭州森泊工程模版"
    
    # 2. 我们要把他导入并命名为官方工作区的名字
    official_name = "森泊正式生产模板_V1"
    
    # 3. 这是一个包含素材的实际存放根目录 (用于修复路径)
    asset_root = r"f:\Desktop\kaifa\jianying-editor-skill\杭州森泊酒店\杭州开元森泊素材"

    print(f"[*] 步骤 1: 正在将外部工程导入剪映工作区...")
    try:
        # 物理导入
        p = JyProject.import_external_draft(external_template, new_name=official_name)
        
        print(f"[+] 导入成功！当前工程: {p.name}")
        
        print(f"\n[*] 步骤 2: 正在执行全局路径重连 (解决拷贝后的红字问题)...")
        # 自动扫描并匹配文件名
        fixed_count = p.reconnect_all_assets(asset_root)
        
        if fixed_count > 0:
            p.save()
            print(f"✅ 修复成功！共找回 {fixed_count} 个素材。项目现在已在剪映中就绪。")
        else:
            print("⚠️ 未发现需要修复的失效素材。")
            
    except Exception as e:
        print(f"❌ 操作失败: {e}")

if __name__ == "__main__":
    test_external_import_and_fix()
