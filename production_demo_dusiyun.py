
import os
import sys
import time

# 注入 JyWrapper 路径
skill_root = r"f:\Desktop\kaifa\jianying-editor-skill\.agent\skills\jianying-editor"
sys.path.insert(0, os.path.join(skill_root, "scripts"))

from jy_wrapper import JyProject

def run_production_flow():
    # 1. 定义模板和新项目
    template_name = "酒店宣传模板"
    customer_name = "杜思芸_20s_定制版"
    new_project_name = f"{customer_name}_{int(time.time())}"
    
    # 2. 定义新素材路径 (取其中一个作为主要替换物料)
    new_assets_dir = r"f:\Desktop\kaifa\jianying-editor-skill\杭州森泊酒店\杭州开元森泊素材\0128\阿星2单1条\20260128 杜思芸 20s"
    main_video = os.path.join(new_assets_dir, "CJ4A6514.MP4")
    scene_video = os.path.join(new_assets_dir, "CJ4A6529.MP4")
    
    # 定义通用的修复路径 (用于解决模板拷贝过来的红字)
    common_asset_root = r"f:\Desktop\kaifa\jianying-editor-skill\杭州森泊酒店\杭州开元森泊素材"

    print(f"🚀 [生产上线] 启动批量剪辑流程...")
    print(f"[*] 目标客户: {customer_name}")
    
    try:
        # 步骤 A: 安全克隆模板 (不污染母版)
        print(f"\n[*] 步骤 1: 正在克隆 Master 模板 '{template_name}'...")
        p = JyProject.from_template(template_name, new_project_name)
        
        # 步骤 B: 基础建设 - 自动修复模板在当前电脑的红字
        print(f"[*] 步骤 2: 正在执行环境适配 (重连本地公用素材)...")
        p.reconnect_all_assets(common_asset_root)
        
        # 步骤 C: 深度替换 - 将模板中的占位符换成该客户的私人素材
        print(f"[*] 步骤 3: 正在执行定制化替换 (Semantic Replacement)...")
        
        # 尝试替换模板中的“开幕森泊”或者是第一个镜头
        # 我们使用语义插槽名称或路径关键字进行替换
        res1 = p.replace_material_by_name("开幕森泊", main_video)
        res2 = p.replace_material_by_path("水乐园环绕", scene_video)
        
        if res1 or res2:
            print(f"[+] 替换成功！已根据客户素材更新草稿。")
        else:
            print("⚠️ 未找到精确匹配的占位符名，尝试通过路径关键字模糊匹配替换第一个 MP4 片段...")
            p.replace_material_by_path(".mp4", main_video)

        # 步骤 D: 保存
        p.save()
        print(f"\n✅ [大功告成] 项目已交付: {new_project_name}")
        print(f"📂 存放位置: {p.root}\\{new_project_name}")
        print("-" * 50)
        print("💡 您现在可以打开剪映，看到为您定制的 '杜思芸' 专属视频版本了！")

    except Exception as e:
        print(f"❌ 流程中断: {e}")

if __name__ == "__main__":
    run_production_flow()
