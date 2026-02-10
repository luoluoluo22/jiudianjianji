import PyInstaller.__main__
import os
import sys

# 获取项目根目录
base_dir = os.path.dirname(os.path.abspath(__file__))

print(f"🚀 开始打包 JianYing AI 自动化剪辑系统 (GUI)...")
print(f"📂 项目根目录: {base_dir}")

# 定义依赖路径
deps = [
    os.path.join(base_dir, "杭州森泊酒店"),
    os.path.join(base_dir, ".agent", "skills", "jianying-editor", "references"),
    os.path.join(base_dir, ".agent", "skills", "jianying-editor", "scripts"),
    os.path.join(base_dir, ".agent", "skills", "antigravity-api-skill", "libs"),
]

# 验证路径是否存在
valid_paths = [p for p in deps if os.path.exists(p)]
path_args = [f'--paths={p}' for p in valid_paths]

# 资源文件 (add-data)
# Windows 下分隔符是 ;
datas = [
    f'--add-data={os.path.join(base_dir, "杭州森泊酒店")};杭州森泊酒店',
    f'--add-data={os.path.join(base_dir, ".agent")};.agent',
]

# 定义打包参数
params = [
    'gui_launcher.py',                          # 主程序入口
    '--name=JianYing_Auto_Editor',              # 生成的文件名
    '--onefile',                                # 打包成单个可执行文件
    '--noconsole',                              # 无控制台窗口
    '--hidden-import=uiautomation',             # 强制导入隐式依赖
    '--hidden-import=comtypes',
    '--hidden-import=psutil',
    '--hidden-import=pymediainfo',
    '--icon=NONE',                              # 暂时不设置图标
    '--clean',
] + path_args + datas

try:
    PyInstaller.__main__.run(params)
    print("\n" + "="*30)
    print("✅ 打包完成！")
    print(f"📦 可执行文件位于: {os.path.join(base_dir, 'dist', 'JianYing_Auto_Editor.exe')}")
    print("="*30)
except Exception as e:
    print(f"❌ 打包过程中出现错误: {e}")
