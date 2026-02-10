import PyInstaller.__main__
import os
import sys

# 获取项目根目录
base_dir = os.path.dirname(os.path.abspath(__file__))

print(f"🚀 开始打包 JianYing Insight 可视化看板...")
print(f"📂 项目根目录: {base_dir}")

# 定义打包路径
references_dir = os.path.normpath(os.path.join(base_dir, ".agent", "skills", "jianying-editor", "references"))
scripts_dir = os.path.normpath(os.path.join(base_dir, ".agent", "skills", "jianying-editor", "scripts"))
tools_dir = os.path.normpath(os.path.join(base_dir, ".agent", "skills", "jianying-editor", "tools"))

# 定义打包参数
params = [
    'start_visualizer.py',                      # 主程序入口
    '--name=JianYing_Visualizer',               # 生成的文件名
    '--onefile',                                # 打包成单个可执行文件
    '--noconsole',                              # 恢复无服务器窗口模式，由网页按钮控制退出
    # 路径增强：告诉 PyInstaller 去哪里找本地模块源码
    f'--paths={references_dir}',
    f'--paths={scripts_dir}',
    f'--paths={tools_dir}',
    # 静态资源处理
    f'--add-data={os.path.join(base_dir, "dashboard/templates")};dashboard/templates',
    f'--add-data={references_dir};references',
    f'--add-data={scripts_dir};scripts',
    f'--add-data={tools_dir};tools',
    '--clean',
]

try:
    PyInstaller.__main__.run(params)
    print("\n" + "="*30)
    print("✅ 打包完成！")
    print(f"📦 可执行文件位于: {os.path.join(base_dir, 'dist', 'JianYing_Visualizer.exe')}")
    print("="*30)
except Exception as e:
    print(f"❌ 打包过程中出现错误: {e}")
