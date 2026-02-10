import asyncio
import os
import sys

# 强制控制台使用 UTF-8
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from playwright.async_api import async_playwright

async def test_record():
    # 确保路径正确
    abs_ui_path = os.path.abspath("cinematic_ui.html")
    ui_url = "file://" + abs_ui_path.replace("\\", "/")
    output_dir = os.path.abspath("debug_record")

    if not os.path.exists(abs_ui_path):
        print(f"Error: {abs_ui_path} not found")
        return

    os.makedirs(output_dir, exist_ok=True)

    print(f"Testing recording for: {ui_url}")
    async with async_playwright() as p:
        # 使用带窗口模式或更稳定的参数
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=output_dir,
            record_video_size={"width": 1920, "height": 1080}
        )
        page = await context.new_page()

        # 增加等待时间确保页面渲染
        await page.goto(ui_url, wait_until="networkidle")
        await asyncio.sleep(1)

        print("Action: Switch to Dashboard")
        await page.evaluate("window.showScene('dashboard')")
        await asyncio.sleep(4)

        # 获取生成的视频路径
        video_path = await page.video.path()
        await context.close()
        await browser.close()

        if video_path and os.path.exists(video_path):
            # 这里的关键是 Playwright 录制的是 .webm，我们需要确认它的大小
            size = os.path.getsize(video_path)
            print(f"Success! Video captured.")
            print(f"Path: {video_path}")
            print(f"Size: {size / 1024 / 1024:.2f} MB")

            # 将其重命名为 .mp4 供剪映识别
            final_path = os.path.join(output_dir, "test_output.mp4")
            if os.path.exists(final_path): os.remove(final_path)
            os.rename(video_path, final_path)
            print(f"Renamed to: {final_path}")
            return final_path
        else:
            print("Failed: No video file generated")
            return None

if __name__ == "__main__":
    asyncio.run(test_record())
