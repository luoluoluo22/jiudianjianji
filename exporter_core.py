# -*- coding: utf-8 -*-
import os
import sys
import time
import shutil
import ctypes
import traceback

# 尝试导入依赖
try:
    import uiautomation as uia
except ImportError:
    pass

class ControlFinder:
    """控件查找逻辑"""
    @staticmethod
    def desc_matcher(target_desc: str, exact: bool = False):
        target_desc = target_desc.lower()
        def matcher(control, depth):
            try:
                # 30159 = UIA_FullDescriptionPropertyId
                full_desc = control.GetPropertyValue(30159)
                if not full_desc: return False
                full_desc = full_desc.lower()
                return (target_desc == full_desc) if exact else (target_desc in full_desc)
            except:
                return False
        return matcher

class Exporter:
    def __init__(self, log_func=print, jianying_exe_path=None):
        self.log = log_func
        self.window = None
        self.jianying_exe_path = jianying_exe_path
        self._setup_dpi()

    def _setup_dpi(self):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
            self.log("[*] DPI: 系统级感知已开启")
        except:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
                self.log("[*] DPI: 基础感知已开启")
            except: pass

    def kill_jianying(self):
        """强制关闭所有剪映相关的进程，解决文件占用或草稿不刷新的问题"""
        self.log("[*] 正在尝试强制关闭剪映以释放文件占用...")
        import subprocess
        try:
            # 杀死主程序和可能的后台渲染进程
            subprocess.run(['taskkill', '/F', '/IM', 'JianyingPro.exe', '/T'], capture_output=True)
            time.sleep(2)
            self.log("[+] 剪映已关闭。")
        except Exception as e:
            self.log(f"   [!] 关闭剪映时出错: {e}")

    def connect(self, retry=True):
        """连接或激活窗口，如果未运行则尝试启动"""
        self.window = uia.WindowControl(searchDepth=1, Name='剪映专业版')
        if not self.window.Exists(0):
            export_win = uia.WindowControl(searchDepth=1, Name='导出')
            if export_win.Exists(0):
                self.window = export_win
            else:
                if retry:
                    # 如果提供了路径且窗口不存在，尝试启动进程
                    if self.jianying_exe_path and os.path.exists(self.jianying_exe_path):
                        self.log(f"[*] 检测到剪映未运行，正在尝试启动: {self.jianying_exe_path}")
                        import subprocess
                        subprocess.Popen(self.jianying_exe_path)
                        # 给启动留出时间
                        for i in range(15):
                            time.sleep(2)
                            self.log(f"   [!] 等待剪映启动并就绪 (第 {i+1} 轮)...")
                            self.window = uia.WindowControl(searchDepth=1, Name='剪映专业版')
                            if self.window.Exists(0): break
                        
                    if not self.window.Exists(0):
                        for i in range(5):
                            self.log(f"   [!] 正在尝试寻找/重新连接剪映窗口 (第 {i+1} 次)...")
                            time.sleep(2)
                            try:
                                self.window = uia.WindowControl(searchDepth=1, Name='剪映专业版')
                                if self.window.Exists(0): break
                                export_win = uia.WindowControl(searchDepth=1, Name='导出')
                                if export_win.Exists(0): 
                                    self.window = export_win
                                    break
                            except: pass
                
                if not self.window.Exists(0):
                    raise Exception("无法连接到剪映窗口，请确认剪映已打开或路径正确。")
        
        try:
            # 兼容性修复：仅在未聚焦时激活
            if not self.window.HasFocus():
                self.window.SetActive()
                self.window.SetTopmost(True)
                time.sleep(0.2)
                self.window.SetTopmost(False)
        except: pass

    def is_home_page(self):
        return "HomePage" in self.window.ClassName

    def is_edit_page(self):
        return "MainWindow" in self.window.ClassName

    def switch_to_home(self):
        self.log("[*] 正在切换回首页...")
        if self.is_home_page():
            return

        close_btn = self.window.GroupControl(searchDepth=1, ClassName="TitleBarButton", foundIndex=3)
        if close_btn.Exists(1):
            close_btn.Click(simulateMove=False)
        else:
            self.window.SendKeys('{Esc}')
        
        time.sleep(2)
        self.connect()
        if not self.is_home_page():
            raise Exception("无法返回首页")

    def dismiss_blocking_dialogs(self):
        """尝试关闭可能阻挡界面的弹窗 (环境检测、版本更新等)。特别处理：‘链接媒体’弹窗出现时直接报错中止。"""
        # 1. 优先检查致命弹窗 (出现即中止)
        critical_wins = ["链接媒体", "媒体丢失"]
        for name in critical_wins:
            try:
                win = uia.WindowControl(searchDepth=1, Name=name)
                if win.Exists(0):
                    raise Exception(f"❌ 检测到【{name}】弹窗！这意味着模版存在媒体丢失问题。程序已主动中止，请手动检查模版并重新连接媒体后再试。")
            except Exception as e:
                if "检测到" in str(e): raise e # 重新抛出我们的核心异常
                pass

        # 2. 处理可自动关闭的普通干扰弹窗
        dialogs = [
            {"Name": "环境检测", "CloseBtn": "确定"},
            {"Name": "提示", "CloseBtn": "确定"},
            {"Name": "更新", "CloseBtn": "以后再说"}
        ]
        for dlg in dialogs:
            try:
                win = uia.WindowControl(searchDepth=1, Name=dlg["Name"])
                if win.Exists(0):
                    self.log(f"   [!] 检测到干扰弹窗【{dlg['Name']}】，正在尝试关闭...")
                    close_btn = win.ButtonControl(Name=dlg["CloseBtn"])
                    if not close_btn.Exists(0):
                        close_btn = win.TextControl(Name=dlg["CloseBtn"])
                    
                    if close_btn.Exists(0):
                        close_btn.Click(simulateMove=False)
                    else:
                        win.SendKeys('{Esc}')
                    time.sleep(1)
            except: pass

    def open_draft(self, draft_name):
        self.log(f"[*] 正在查找草稿: {draft_name}")
        if not self.is_home_page():
            self.switch_to_home()

        # 处理首页弹窗
        self.dismiss_blocking_dialogs()

        target_desc = f"HomePageDraftTitle:{draft_name}"
        draft_card = None
        
        for _ in range(5): # 增加检索轮数
            draft_text = self.window.TextControl(searchDepth=6, Compare=ControlFinder.desc_matcher(target_desc, exact=True))
            if not draft_text.Exists(0):
                draft_text = self.window.TextControl(searchDepth=6, Name=draft_name)
            
            if draft_text.Exists(0):
                draft_card = draft_text.GetParentControl()
                break
            time.sleep(1)

        if not draft_card:
             raise Exception(f"未找到名为【{draft_name}】的草稿")

        draft_card.Click(simulateMove=False)
        
        self.log("[*] 等待加载编辑器 (最多60s)...")
        for i in range(60):
            time.sleep(1)
            try:
                self.connect(retry=False)
                if self.is_edit_page():
                    self.log(f"[*] 成功进入编辑页 (耗时 {i+1}s)。")
                    time.sleep(2)
                    return
            except: continue
        raise Exception("打开草稿超时")

    def run_export(self, draft_name, resolution="1080P", timeout=900):
        """执行导出核心流程 - 恢复稳定版逻辑并针对卡死进行最小化调整"""
        self.connect()
        self.dismiss_blocking_dialogs()
        self.open_draft(draft_name)

        # 再次检查编辑页弹窗
        time.sleep(1)
        self.dismiss_blocking_dialogs()

        # 1. 点击顶部导出按钮
        export_btn = self.window.TextControl(searchDepth=5, Compare=ControlFinder.desc_matcher("MainWindowTitleBarExportBtn"))
        if not export_btn.Exists(1):
            export_btn = self.window.TextControl(searchDepth=5, Name="导出")
        
        if not export_btn.Exists(0):
            raise Exception("找不到【导出】按钮")
            
        self.log("[*] 点击【导出】对话框...")
        export_btn.Click(simulateMove=False)
        time.sleep(1.5)
        self.connect(retry=False) 
        
        # 2. 嗅探真实路径 (移除分辨率设置动作以提高稳定性)
        real_export_file = None
        try:
            path_sib = self.window.TextControl(searchDepth=8, Compare=ControlFinder.desc_matcher("ExportPath"))
            if path_sib.Exists(1):
                path_ctrl = path_sib.GetSiblingControl(lambda ctrl: True)
                if path_ctrl:
                    real_export_file = path_ctrl.GetPropertyValue(30159)
                    self.log(f"[*] 捕捉到真实导出路径: {real_export_file}")
        except Exception as e:
            self.log(f"   [!] 细节配置自动处理跳过: {e}")
 
        # 3. 确认导出
        self.log("[*] 正在确认导出...")
        confirm_btn = self.window.TextControl(searchDepth=8, Compare=ControlFinder.desc_matcher("ExportOkBtn"))
        if not confirm_btn.Exists(0):
            confirm_btn = self.window.ButtonControl(Name="导出")
        
        if not confirm_btn.Exists(1):
             raise Exception("无法点击最终导出确认按钮")
 
        confirm_btn.Click(simulateMove=False)
 
        # 4. 等待导出完成 (针对卡死优化的改进逻辑)
        self.log("[*] 导出编码启动，进入监控阶段...")
        start_time = time.time()
        
        # 初始避让：等待 5 秒让剪映进入稳定渲染状态，之后再开始轮询
        time.sleep(5)

        while time.time() - start_time < timeout:
            try:
                # 尝试寻找“导出成功”窗口中的关闭按钮
                # 如果主窗口太忙，尝试找顶级弹窗
                target_win = self.window
                export_done_win = uia.WindowControl(searchDepth=1, Name="导出")
                if export_done_win.Exists(0):
                    target_win = export_done_win

                close_btn = target_win.TextControl(searchDepth=8, Compare=ControlFinder.desc_matcher("ExportSucceedCloseBtn"))
                if close_btn.Exists(0):
                    self.log("[*] ✅ 导出任务在 UI 层面已完成。")
                    close_btn.Click(simulateMove=False)
                    time.sleep(1)
                    # 任务完成后切换回首页
                    try:
                        self.switch_to_home()
                    except:
                        self.log("   [!] 导出后由于高负载无法返回首页，已跳过。")
                    return real_export_file
            except:
                pass # 忽略轮询期间的 UI 通信波动
            
            time.sleep(4) # 适中的轮询频率
            
        raise Exception("导出超时")

# 为了保持原 gui_launcher 调用兼容，提供这个静态封装
def run_export_with_log(draft_name, log_func=print):
    exp = Exporter(log_func=log_func)
    return exp.run_export(draft_name)
