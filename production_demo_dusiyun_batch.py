
import os
import sys
import time

# 注入 JyWrapper 路径
skill_root = r"f:\Desktop\kaifa\jianying-editor-skill\.agent\skills\jianying-editor"
sys.path.insert(0, os.path.join(skill_root, "scripts"))

from jy_wrapper import JyProject

def run_batch_production_flow():
    # 1. 定义设定
    template_name = "酒店宣传模板"
    customer_name = "杜思芸_20s_精编版"
    new_project_name = f"{customer_name}_{int(time.time())}"
    
    # 客户私人素材目录 (非酒店部分)
    user_assets_dir = r"f:\Desktop\kaifa\jianying-editor-skill\杭州森泊酒店\杭州开元森泊素材\0128\阿星2单1条\20260128 杜思芸 20s"
    user_videos = [os.path.join(user_assets_dir, f) for f in os.listdir(user_assets_dir) if f.lower().endswith(".mp4")]
    
    # 公用素材根目录 (酒店固定部分)
    common_asset_root = r"f:\Desktop\kaifa\jianying-editor-skill\杭州森泊酒店\杭州开元森泊素材"

    print(f"🚀 [生产上线] 启动深度批量替换测试...")
    print(f"[*] 发现该客户私人素材: {len(user_videos)} 段")
    
    try:
        # 步骤 1: 安全克隆模板
        print(f"\n[*] 步骤 1: 克隆母版...")
        p = JyProject.from_template(template_name, new_project_name)
        
        # 步骤 2: 修复酒店固定物料 (如 Logo, BGM, 空镜)
        print(f"[*] 步骤 2: 自动找回酒店固定资产...")
        p.reconnect_all_assets(common_asset_root)
        
        # 步骤 3: 暴力批量填充 (将所有 PXMX 占位符替换为客户素材)
        print(f"[*] 步骤 3: 正在执行【非酒店部分】暴力替换...")
        
        # 我们使用 replace_material_by_path 的批量能力
        # 我们可以循环匹配不同的 PXMX 编号并填充不同的客户素材
        placeholders = ["PXMX0789", "PXMX0790", "PXMX0791", "PXMX0792"]
        
        for i, placeholder in enumerate(placeholders):
            if i < len(user_videos):
                target_video = user_videos[i]
                print(f"    ↘ 正在填充槽位 {placeholder} -> {os.path.basename(target_video)}")
                # 特别说明：这里直接按路径关键字匹配替换
                p.replace_material_by_path(placeholder, target_video)
        
        # 步骤 4: 语义替换封面 (如果需要特别指定某一段)
        # 比如把第一段素材强制换成 CJ4A6514.MP4
        # p.replace_material_by_name("开幕森泊", user_videos[0])

        # 步骤 5: 最终保存
        p.save()
        print(f"\n✅ [生产完成] {new_project_name} 已生成。")
        print(f"💡 逻辑：酒店固定空镜已自动重连，所有 PXMX 占位符已由杜思芸私人素材填补。")

    except Exception as e:
        print(f"❌ 流程中断: {e}")

if __name__ == "__main__":
    run_batch_production_flow()
