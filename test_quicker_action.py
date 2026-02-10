import subprocess
import os

def test_quicker_cmd():
    quicker_exe = r"C:\Program Files\Quicker\QuickerStarter.exe"
    action_id = "ef7ec6e0-884c-472c-8834-411c6097f793"
    save_path = r"F:/Desktop/test_output.mp4"
    
    arg_str = f"{draft_name}|{save_path}"
    
    print(f"[*] 准备启动 Quicker 动作: {action_id}")
    print(f"[*] 参数: {arg_str}")
    
    # 修正拼接：runaction:ID?Args
    cmd_arg = f"runaction:{action_id}?{arg_str}"
    cmd = [quicker_exe, cmd_arg]
    try:
        subprocess.Popen(cmd)
        print("✅ 指令已发送，请查看 Quicker 响应。")
    except Exception as e:
        print(f"❌ 运行失败: {e}")

if __name__ == "__main__":
    if os.path.exists(r"C:\Program Files\Quicker\QuickerStarter.exe"):
        test_quicker_cmd()
    else:
        print("❌ 未在默认路径找到 QuickerStarter.exe")
