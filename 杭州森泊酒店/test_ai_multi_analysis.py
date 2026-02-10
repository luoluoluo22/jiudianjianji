import os
import sys
import json
from pathlib import Path

# 1. 环境初始化
SKILL_API = r"f:\Desktop\kaifa\jianying-editor-skill\.agent\skills\antigravity-api-skill"
sys.path.append(os.path.join(SKILL_API, "libs"))

try:
    from api_client import AntigravityClient
except ImportError as e:
    print(f"[-] 依赖库加载失败: {e}")
    sys.exit(1)

def test_multi_video_analysis(folder_path):
    client = AntigravityClient()
    model = "gemini-3-pro"

    # 获取视频列表 (陈桑桑素材包，共3段)
    videos = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.lower().endswith(('.mp4', '.mov'))]
    videos.sort()

    print(f"[*] 启动 AI 联合分析测试...")
    print(f"[*] 素材池 ({len(videos)}段): {[os.path.basename(v) for v in videos]}")
    print(f"[*] 目标：从这 {len(videos)} 段素材中挑选出【正好 4 段】互不重叠的 3s 片段。")
    print("-" * 50)

    file_names_str = ", ".join([os.path.basename(v) for v in videos])
    prompt = (
        f"作为专业的短视频剪辑师，请从这几个视频中挑选出【正好 4 个】最适合酒店营销的 3s 片段：{file_names_str}。\n"
        "要求：\n"
        "1. 必须避开起步前的静止不动，选择动作最连贯、有互动的瞬间。\n"
        "2. 片段间内容尽量不重复。由于视频总数较少，请从内容丰富的长视频中挑选不同时间点的两个片段以凑齐 4 个。\n"
        "⚠️严格按 JSON 格式输出列表：[{\"file_name\": \"文件名\", \"start\": \"3s\", \"text\": \"理由\"}, ...]"
    )

    messages = [{"role": "user", "content": prompt}]

    try:
        # 同时传入 3 个文件的路径
        response = client.chat_completion(messages, model=model, file_paths=videos)

        content = ""
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith("data: "):
                    data_str = line_str[6:]
                    if data_str.strip() == "[DONE]": break
                    try:
                        data = json.loads(data_str)
                        delta = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                        if delta: content += delta
                    except: pass

        # 解析并打印结果
        clean_json = content.strip().strip("```json").strip("```").strip()
        results = json.loads(clean_json)

        print(f"\n✅ AI 决策结果 (已选中 {len(results)} 个片段):")
        for i, res in enumerate(results):
            print(f"   【片段 {i+1}】")
            print(f"    - 文件: {res.get('file_name')}")
            print(f"    - 起点: {res.get('start')}")
            print(f"    - 理由: {res.get('text')}")

        if len(results) == 4:
            print("\n✨ 测试成功：AI 已成功完成 3 选 4 的智能抽吸逻辑。")
        else:
            print(f"\n⚠️ 测试结果不完全：AI 返回了 {len(results)} 个片段，而非 4 个。")

    except Exception as e:
        print(f"\n❌ 测试运行失败: {e}")

if __name__ == "__main__":
    TARGET_FOLDER = r"F:\Desktop\kaifa\jianying-editor-skill\杭州森泊酒店\杭州开元森泊素材\0128\阿琪5单5条\20260128陈桑桑20s"
    test_multi_video_analysis(TARGET_FOLDER)
