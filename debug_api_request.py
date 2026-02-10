import os
import sys
import json
import traceback

# 注入路径
base_dir = os.path.dirname(os.path.abspath(__file__))
skill_api = os.path.join(base_dir, ".agent", "skills", "antigravity-api-skill", "libs")
if skill_api not in sys.path:
    sys.path.insert(0, skill_api)

try:
    from api_client import AntigravityClient
except ImportError:
    print("[-] 无法加载 AntigravityClient，请检查路径")
    sys.exit(1)

def debug_test():
    client = AntigravityClient()
    # 模拟一个可能包含中文或乱码的文件名路径 (取一个实际存在的文件)
    test_video = None
    # 尝试寻找一个 mp4 文件
    for root, dirs, files in os.walk(base_dir):
        for f in files:
            if f.lower().endswith(".mp4"):
                test_video = os.path.join(root, f)
                break
        if test_video: break

    if not test_video:
        print("[-] 未找到任何测试视频文件")
        return

    print(f"[*] 测试视频: {test_video}")
    print(f"[*] 目标 URL: {client.base_url}")
    
    prompt = "请描述这个视频的内容。"
    messages = [{"role": "user", "content": prompt}]
    
    try:
        print("[*] 正在发起 chat_completion 请求...")
        # 我们手动执行部分逻辑来定位错误
        response = client.chat_completion(messages, model="gemini-3-flash", file_paths=[test_video])
        
        if response is None:
            print("[-] Request returned None (likely caught internal exception)")
            return

        print("[+] 请求成功，正在流式读取结果:")
        content = ""
        for line in response.iter_lines():
            if line:
                print(f"DEBUG LINE: {line.decode('utf-8', errors='ignore')}")
    except Exception as e:
        print("\n" + "!"*40)
        print(f"🔥 捕获到错误: {type(e).__name__}: {e}")
        print("!"*40)
        traceback.print_exc()

if __name__ == "__main__":
    debug_test()
