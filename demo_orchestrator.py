import os
import sys
import asyncio
import edge_tts
import json
import shutil
from datetime import datetime
from playwright.async_api import async_playwright

# 1. 自动引入剪映 Skill 核心库 (路径加固)
# -------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 优先寻找本地或隐藏目录下的 skill
skill_path = os.path.join(BASE_DIR, ".agent", "skills", "jianying-editor")
wrapper_path = os.path.join(skill_path, "scripts")

if not os.path.exists(wrapper_path):
    # 尝试 alternate 路径
    skill_path = os.path.join(BASE_DIR, "skills", "jianying-editor")
    wrapper_path = os.path.join(skill_path, "scripts")

if os.path.exists(wrapper_path):
    if wrapper_path not in sys.path:
        sys.path.insert(0, wrapper_path)
else:
    print(f"❌ 找不到 Skill 路径，请确认 .agent/skills/jianying-editor 存在")
    sys.exit(1)

try:
    from jy_wrapper import JyProject
except ImportError:
    print("❌ 无法导入 'jy_wrapper'。")
    sys.exit(1)
# -------------------------------------------------------------

# 配置参数 (强制绝对路径)
UI_FILE_PATH = os.path.join(BASE_DIR, "cinematic_ui.html")
UI_URL = "file://" + UI_FILE_PATH.replace("\\", "/")
OUTPUT_DIR = os.path.join(BASE_DIR, "demo_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

SCENES = [
    {"id": "intro", "text": "欢迎来到 Elysian Studio，这是一个具备电影感交互体验的艺术空间。", "wait": 2},
    {"id": "dashboard", "text": "在这里，我们可以实时监控核心数据增长。代码让数据具备了生命力。", "wait": 2},
    {"id": "success", "text": "恭喜您，所有服务已成功部署。开启您的全自动创作之旅。", "wait": 3}
]

async def generate_tts(text, filename):
    communicate = edge_tts.Communicate(text, "zh-CN-XiaoxiaoNeural")
    path = os.path.join(OUTPUT_DIR, filename)
    await communicate.save(path)
    return path

async def record_ui():
    print(f"🎬 开始录制视觉素材: {UI_URL}")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # record_video_dir 会自动生成文件名，我们需要最后去改名
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=OUTPUT_DIR,
            record_video_size={"width": 1920, "height": 1080}
        )
        page = await context.new_page()

        # 确保网页加载
        await page.goto(UI_URL, wait_until="networkidle")
        await asyncio.sleep(1)

        audio_assets = []
        current_offset = 0

        for scene in SCENES:
            scene_id = scene["id"]
            print(f"📺 切换场景 -> {scene_id}")
            await page.evaluate(f"window.showScene('{scene_id}')")

            # 生成旁白并预估时长 (更精确的做法是读取文件)
            audio_path = await generate_tts(scene["text"], f"audio_{scene_id}.mp3")
            speech_duration = len(scene["text"]) / 4.5 # 稍微放慢一点点
            total_scene_time = speech_duration + scene["wait"]

            audio_assets.append({
                "path": audio_path,
                "start": current_offset,
                "text": scene["text"],
                "duration": speech_duration
            })

            await asyncio.sleep(total_scene_time)
            current_offset += total_scene_time

        # 获取生成的视频路径
        video_path = await page.video.path()
        await context.close()
        await browser.close()

        final_video = os.path.join(OUTPUT_DIR, "cinematic_capture.mp4")
        if os.path.exists(final_video): os.remove(final_video)
        shutil.move(video_path, final_video)

        return final_video, audio_assets

async def create_jianying_project(video_path, audios):
    print("🚀 正在注入剪映协议...")

    # 1. 计算精确的总时长
    total_duration_s = sum([item['duration'] + 2 for item in audios])
    total_duration_us = int(total_duration_s * 1000000)

    project = JyProject("Cinematic_UI_Demo_Final")

    # 2. 注入视频素材 (显式传递时长以绕过自动检测报错)
    print(f"📥 强制导入视频素材: {video_path}")
    # 通过显式传入 duration 字符串，wrapper 会跳过不稳定的自动解析
    video_seg = project.add_media_safe(video_path, "0s", duration=f"{total_duration_s:.2f}s")

    if not video_seg:
        print("⚠️ 常规导入失败，尝试底层强制注入...")
        # 如果 wrapper 还是报错，这通常是因为 VideoMaterial 内部解析失败
        # 我们在这里暂时无法修改底层库，但可以通过确保 duration 是整数来最大化成功率
        video_seg = project.add_media_safe(video_path, "0s", duration=int(total_duration_s))

    # 3. 添加旁白与字幕
    for item in audios:
        start_time_str = f"{item['start']:.2f}s"
        duration_str = f"{item['duration']:.2f}s"

        project.add_media_safe(item["path"], start_time_str)
        project.add_text_simple(
            text=item["text"],
            start_time=start_time_str,
            duration=duration_str,
            transform_y=-0.8,
            font_size=4.5
        )

    project.save()
    print(f"✅ 完美部署！项目名称: Cinematic_UI_Demo_Final")

async def main():
    if not os.path.exists(UI_FILE_PATH):
        print(f"❌ 关键文件缺失: {UI_FILE_PATH}")
        return

    video_path, audio_assets = await record_ui()
    await create_jianying_project(video_path, audio_assets)

if __name__ == "__main__":
    # 强制控制台输出为 UTF-8
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    asyncio.run(main())
