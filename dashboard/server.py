import os
import sys
import json
import subprocess
import time
from flask import Flask, jsonify, send_from_directory, request

# 注入 JyWrapper 路径
if getattr(sys, 'frozen', False):
    # 打包模式下，scripts 被直接打包在根层级
    scripts_path = os.path.join(sys._MEIPASS, "scripts")
    # 设置模板和静态资源目录
    template_folder = os.path.join(sys._MEIPASS, 'dashboard', 'templates')
    static_folder = os.path.join(sys._MEIPASS, 'dashboard', 'static')
else:
    # 源码模式下
    skill_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    scripts_path = os.path.join(skill_root, ".agent", "skills", "jianying-editor", "scripts")
    template_folder = 'templates'
    static_folder = 'static'

sys.path.insert(0, scripts_path)

try:
    from jy_wrapper import JyProject, get_all_drafts, get_default_drafts_root
    from web_recorder import record_web_animation
except ImportError as e:
    print(f"❌ 关键错误: 找不到剪映驱动脚本或录制组件 ({e})")
    print(f"当前 Python 路径: {sys.path}")
    if not getattr(sys, 'frozen', False):
        sys.exit(1)

# 统一初始化 Flask，仅此一次
app = Flask(__name__, static_folder=static_folder, template_folder=template_folder)

@app.route('/api/recorder/start', methods=['POST'])
def start_gui_recorder():
    """调起 Tkinter 屏幕录制助手"""
    if getattr(sys, 'frozen', False):
        # 打包环境下，recorder.py 在 sys._MEIPASS/tools/...
        recorder_script = os.path.join(sys._MEIPASS, "tools", "recording", "recorder.py")
    else:
        # 开发环境下
        skill_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        recorder_script = os.path.join(skill_root, ".agent", "skills", "jianying-editor", "tools", "recording", "recorder.py")
    
    if not os.path.exists(recorder_script):
        return jsonify({"status": "error", "message": f"找不到录屏组件: {recorder_script}"}), 404
        
    try:
        # 异步启动，不阻塞 Flask
        subprocess.Popen([sys.executable, recorder_script])
        return jsonify({"status": "success", "message": "录屏助手已启动，请查看系统任务栏。"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/record', methods=['POST'])
def record_animation():
    """录制网页动画"""
    data = request.json
    url = data.get('url')
    # 默认保存在当前目录下的 video_cache 中
    output_name = data.get('output_name', f"web_vfx_{int(time.time())}.webm")
    
    # 确保缓存目录存在
    cache_dir = os.path.join(os.getcwd(), "video_cache")
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
        
    output_path = os.path.join(cache_dir, output_name)
    
    try:
        success = record_web_animation(url, output_path)
        if success:
            return jsonify({
                "status": "success", 
                "path": output_path,
                "message": f"录制成功！文件已保存至: {output_path}"
            })
        else:
            return jsonify({"status": "error", "message": "录制失败，请检查 URL 是否有效或环境依赖。"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/')
def index():
    return send_from_directory('templates', 'index.html')

@app.route('/.well-known/<path:path>')
def silent_well_known(path):
    """静默处理浏览器探测请求，避免日志 404"""
    return "", 204

@app.route('/api/drafts')
def list_drafts():
    root = get_default_drafts_root()
    drafts = get_all_drafts(root)
    return jsonify({
        "status": "success",
        "drafts_root": root,
        "drafts": drafts
    })

@app.route('/api/draft/<name>')
def get_draft_detail(name):
    try:
        # 加载项目并生成深度报告
        p = JyProject(name, overwrite=False)
        report = p.save() # save() 现在返回完整的 report
        return jsonify(report)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/reconnect', methods=['POST'])
def reconnect_assets():
    data = request.json
    project_name = data.get('name')
    asset_root = data.get('asset_root')
    
    if not project_name or not asset_root:
        return jsonify({"status": "error", "message": "Missing params"}), 400
        
    try:
        p = JyProject(project_name, overwrite=False)
        count = p.reconnect_all_assets(asset_root)
        p.save()
        return jsonify({"status": "success", "fixed_count": count})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/media')
def serve_media():
    path = request.args.get('path')
    if not path or not os.path.exists(path):
        return "File not found", 404
    
    # 获取 mimetype
    import mimetypes
    mime_type, _ = mimetypes.guess_type(path)
    
    return send_from_directory(os.path.dirname(path), os.path.basename(path), mimetype=mime_type)

@app.route('/api/shutdown', methods=['POST'])
def shutdown():
    """安全关闭服务"""
    print("👋 收到关闭请求，正在退出程序...")
    import threading
    # 延迟 0.5 秒退出，确保前端能收到成功的响应
    threading.Timer(0.5, lambda: os._exit(0)).start()
    return jsonify({"status": "success", "message": "服务已关闭，您可以安全关闭此页面。"})

if __name__ == '__main__':
    print("🚀 JianYing Insight Dashboard starting on http://127.0.0.1:5000")
    app.run(port=5000, debug=True)
