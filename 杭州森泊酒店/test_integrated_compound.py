import os
import sys
import uuid

# 1. 环境初始化
skill_root = os.path.abspath(r"f:\Desktop\kaifa\jianying-editor-skill\.agent\skills\jianying-editor")
sys.path.insert(0, os.path.join(skill_root, "scripts"))

from jy_wrapper import JyProject

def demo_integrated_compound():
    """验证集成到 jy_wrapper 后的复合片段功能"""
    rand_id = str(uuid.uuid4())[:8]
    p_name = f"集成复合验证_{rand_id}"
    
    print(f"🎬 正在通过 JyProject 原生方法生成项目: {p_name}")
    try:
        # 主工程
        p_main = JyProject(p_name, overwrite=True)
        
        # 子工程 1: 文字片头
        p_intro = JyProject(f"Intro_{rand_id}", overwrite=True)
        p_intro.add_text_simple("集成版：复合片段 L1", font_size=8, transform_y=0.2)
        p_intro.add_text_simple("Sub-Project Content", font_size=4, transform_y=-0.2)
        
        # 子工程 2: 嵌套递归测试 (可选)
        
        # 使用新集成的原生方法注入
        p_main.add_compound_project(p_intro, "原生封装组件")
        
        # 也可以在同一轨道继续追加内容
        p_main.add_text_simple("--- 主工程原生文字 ---", start_time="5s", duration="2s")
        
        p_main.save()
        print(f"🚀 集成验证成功！项目名: {p_name}")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"❌ 运行报错: {e}")

if __name__ == "__main__":
    demo_integrated_compound()
