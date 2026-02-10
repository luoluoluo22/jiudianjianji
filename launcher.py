import os
import sys
import re
import shutil
import json
import traceback

# --- 1. EXE 环境路径自适应 ---
if getattr(sys, 'frozen', False):
    # 如果是打包后的 EXE 环境
    bundle_dir = sys._MEIPASS
else:
    # 如果是源代码开发环境
    bundle_dir = os.path.dirname(os.path.abspath(__file__))

# 探测 Skill 真实物理路径 (优先找同级，再找内部)
project_root = os.path.dirname(os.path.abspath(__file__))
skill_jy = os.path.join(project_root, ".agent", "skills", "jianying-editor", "scripts")
skill_api = os.path.join(project_root, ".agent", "skills", "antigravity-api-skill", "libs")

# 强制注入路径
sys.path.append(skill_jy)
sys.path.append(skill_api)

try:
    # 延迟加载核心逻辑
    from ai_batch_editor import AIVideoEditor
except ImportError as e:
    print(f"[-] 核心组件加载失败: {e}")
    input("按回车键退出...")
    sys.exit(1)

def main():
    print("="*60)
    print("      酒店旅拍视频 AI 自动化剪辑系统 v1.0")
    print("="*60)

    # 1. 交互式获取路径或通过命令行
    if len(sys.argv) > 1:
        input_folder = sys.argv[1]
    else:
        input_folder = input("\n👉 请将【客户素材文件夹】拖入此处并回车:\n").strip('"').strip("'")

    if not os.path.exists(input_folder):
        print(f"❌ 找不到文件夹: {input_folder}")
        input("\n按回车键退出...")
        return

    # 2. 自动提取客户名
    folder_name = os.path.basename(input_folder)
    name_match = re.search(r'[\u4e00-\u9fa5]{2,3}', folder_name)
    client_name = name_match.group(0) if name_match else "新客户"

    project_name = f"AI生产-{client_name}-完美成片"

    print(f"\n🚀 正在启动生产流水线...")
    print(f"   [👤] 客户: {client_name}")

    try:
        editor = AIVideoEditor(project_name, client_name=client_name)
        editor.run(input_folder)
        print(f"\n🎉 所有任务处理完毕！")
    except Exception:
        print(f"\n❌ 运行过程中出现错误:")
        traceback.print_exc()

    print("\n" + "="*60)
    input("✅ 处理结束。请确认剪映导出结果，按回车键关闭窗口...")

if __name__ == "__main__":
    main()
