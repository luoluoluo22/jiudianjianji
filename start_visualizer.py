import os
import sys
import webbrowser
import threading
import time

# 注入路径
base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base_dir)

from dashboard.server import app

def open_browser():
    """在服务器启动后打开浏览器"""
    time.sleep(1.5)
    url = "http://localhost:5000"
    print(f"🌐 正在自动打开看板: {url}")
    webbrowser.open(url)

def start():
    print("🎨 JianYing Insight | 正在启动可视化插件...")
    
    # 启动浏览器线程
    threading.Thread(target=open_browser, daemon=True).start()
    
    # 启动服务器 (使用 localhost 提高兼容性)
    print("🚀 服务器已就绪，正在监听端口 5000...")
    try:
        app.run(host='0.0.0.0', port=5000, debug=False)
    except KeyboardInterrupt:
        print("\n👋 正在关闭可视化插件...")

if __name__ == "__main__":
    start()
