import os
import sys
import json
import re
from pathlib import Path

# --- 🚀 路径自适应初始化 ---
current_dir = os.path.dirname(os.path.abspath(__file__))
# 尝试寻找 skill 根目录
skill_root = next((p for p in [
    os.path.join(current_dir, ".agent", "skills", "jianying-editor"),
    os.path.join(current_dir, "skills", "jianying-editor"),
    os.path.abspath(".agent/skills/jianying-editor"),
    current_dir # 如果直接在 skill 目录下
] if os.path.exists(os.path.join(p, "scripts", "jy_wrapper.py"))), None)

if not skill_root:
    # 尝试从当前脚本路径向上找 (假设在 workspace 根目录)
    skill_root = os.path.join(os.getcwd(), ".agent", "skills", "jianying-editor")

skill_api = os.path.join(os.path.dirname(skill_root), "antigravity-api-skill")

sys.path.insert(0, os.path.join(skill_root, "scripts"))
sys.path.insert(0, os.path.join(skill_api, "libs"))

try:
    from jy_wrapper import JyProject
    from api_client import AntigravityClient
except ImportError as e:
    print(f"[-] 依赖库加载失败: {e}")
    sys.exit(1)

def parse_time_to_us(time_str, total_duration_s=None):
    """将 HH:MM:SS, MM:SS:FF 或 MM:SS 格式转换为微秒"""
    parts = list(map(float, time_str.split(':')))
    if len(parts) == 3:
        # 可能是 HH:MM:SS 也可能是 MM:SS:FF
        seconds = parts[0] * 3600 + parts[1] * 60 + parts[2]
        # 如果计算出来的秒数超过了视频总时长，且把第一位当分钟算没超过，则按 MM:SS:FF 算
        if total_duration_s and seconds > total_duration_s:
            alt_seconds = parts[0] * 60 + parts[1] + parts[2] / 30 # 假设 30 fps
            if alt_seconds <= total_duration_s:
                return int(alt_seconds * 1000000)
    elif len(parts) == 2:
        seconds = parts[0] * 60 + parts[1]
    else:
        seconds = parts[0]
    return int(seconds * 1000000)

def extract_speaking_segments(video_path, model="gemini-3-flash"):
    client = AntigravityClient()
    
    prompt = (
        "你是一名专业的视频剪辑助理。请深度分析这个视频，挑选出主持人【认真讲解衣服、展示面料细节、描述款式特点或搭配建议】的精彩说话片段。\n"
        "要求：\n"
        "1. 严格过滤掉开场白、回复评论、后台杂音等无关内容。只保留【核心讲解】部分。\n"
        "2. 【关键要求】：请确保每个片段的讲解逻辑完整。请分析讲解的开始和结束点，给出该讲解片段的持续时长（duration）。\n"
        "3. 每个片段的时长建议在 10s 到 20s 之间，以保证讲解不被截断。\n"
        "4. 总共挑选大约 8-10 个最核心的完整讲解片段，使成片总长控制在 2-3 分钟。\n"
        "5. 我只需要 JSON 数组格式，不要任何 Markdown 代码块包裹或解释文字。\n"
        "示例格式：\n"
        "[{\"start\": \"00:01:23\", \"duration\": 15, \"description\": \"详细介绍皮草面料的柔软度和光泽感\"}, ...]"
    )

    print(f"[*] 正在使用 {model} 分析视频说话片段: {os.path.basename(video_path)}")
    
    response = client.chat_completion([{"role": "user", "content": prompt}], model=model, file_paths=[video_path])
    
    if not response or response.status_code != 200:
        print(f"[-] AI 请求失败")
        return []

    content = ""
    for line in response.iter_lines():
        if not line: continue
        line_str = line.decode('utf-8')
        if line_str.startswith("data: "):
            data_str = line_str[6:]
            if data_str.strip() == "[DONE]": break
            try:
                data = json.loads(data_str)
                delta = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                if delta: content += delta
            except: pass

    # 清理可能存在的 Markdown 代码块
    clean_content = content.strip().strip("```json").strip("```").strip()
    print(f"[*] AI 原始输出: {clean_content}")
    try:
        segments = json.loads(clean_content)
        print(f"[+] 发现 {len(segments)} 个说话片段")
        return segments
    except Exception as e:
        print(f"[-] 解析 AI 结果失败: {e}\n原始内容: {content}")
        return []

def main():
    video_path = r"F:\Backup\Downloads\包姐轻生活20260101165054.ts"
    if not os.path.exists(video_path):
        print(f"[-] 找不到视频文件: {video_path}")
        return

    # 0. 获取视频总时长
    import subprocess
    total_duration_s = 0
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration', '-of', 'csv=p=0', video_path],
            capture_output=True, text=True, timeout=5
        )
        total_duration_s = float(result.stdout.strip()) if result.stdout.strip() else 0
    except: pass

    # 1. AI 分析片段
    segments = extract_speaking_segments(video_path)
    if not segments:
        print("[-] 未能找到说话片段。")
        return

    # 2. 创建剪映项目
    project_name = f"包姐说话片段提取_{os.path.basename(video_path)[:10]}"
    project = JyProject(project_name, overwrite=True)
    
    timeline_cursor = 0
    max_total_duration_us = 150 * 1000000 # 限制总长在 2.5 分钟左右
    
    for i, seg in enumerate(segments):
        start_time_str = seg.get("start", "00:00:00")
        # 优先使用 AI 指定的时长，如果没有则默认 15s 尝试保留更多内容
        duration_s = float(seg.get("duration", 15)) 
        duration_us = int(duration_s * 1000000)
        
        description = seg.get("description", "说话片段")
        
        if timeline_cursor + duration_us > max_total_duration_us:
            print(f"[*] 成片时长已接近上限，停止添加。当前总长: {timeline_cursor/1000000:.1f}s")
            break
            
        try:
            source_start_us = parse_time_to_us(start_time_str, total_duration_s=total_duration_s)
            print(f"[*] 添加片段: {start_time_str} ({duration_s}s) -> {source_start_us/1000000:.1f}s - {description}")
            
            # 添加视频片段
            project.add_media_safe(video_path, timeline_cursor, duration_us, source_start=source_start_us)
            
            # 添加字幕描述
            project.add_text_simple(description, timeline_cursor, duration_us, transform_y=-0.8)
            
            timeline_cursor += duration_us
        except Exception as e:
            print(f"[-] 处理片段失败: {seg}, 错误: {e}")

    project.save()
    print(f"\n[✅] 项目已保存: {project_name}")
    print(f"[*] 请在剪映专业版中打开查看效果。")

if __name__ == "__main__":
    main()
