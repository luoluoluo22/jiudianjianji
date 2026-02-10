import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
import threading
import re
import traceback
import json
import shutil
import time
import pathlib
import argparse
import requests
import pymediainfo
import uiautomation as uia  # 补全 UI 自动化依赖
import psutil              # 补全进程管理依赖
import comtypes            # 补全 uiautomation 底层通信依赖
import threading
import uuid
import difflib
import platform
from datetime import datetime
import copy

# --- 1. 增强型环境初始化 ---
if getattr(sys, 'frozen', False):
    # 打包运行：base_dir 是临时解压目录，exe_dir 是 exe 所在的物理目录
    base_dir = sys._MEIPASS
    exe_dir = os.path.dirname(sys.executable)
    # [Fix] 修复 uiautomation 的 COM 依赖
    os.chdir(exe_dir) 
    try:
        import comtypes.client
        _ = comtypes.client.CreateObject
    except: pass
    os.environ['PATH'] = sys._MEIPASS + os.pathsep + os.environ.get('PATH', '')
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    exe_dir = base_dir

# --- 2. 持久化数据目录定义 (关键修改) ---
# 每个电脑的配置保存在: C:\Users\用户名\Documents\SenboVideoAssistant
user_home = os.path.expanduser("~")
persistent_data_root = os.path.join(user_home, "Documents", "SenboVideoAssistant")
if not os.path.exists(persistent_data_root):
    os.makedirs(persistent_data_root, exist_ok=True)

# 核心路径定义
script_dir = os.path.join(base_dir, "杭州森泊酒店")
skill_jy_scripts = os.path.join(base_dir, ".agent", "skills", "jianying-editor", "scripts")
skill_jy_refs = os.path.join(base_dir, ".agent", "skills", "jianying-editor", "references")
skill_api = os.path.join(base_dir, ".agent", "skills", "antigravity-api-skill", "libs")

# 将路径注入 sys.path
for p in [skill_jy_refs, skill_jy_scripts, skill_api, script_dir, base_dir]:
    if os.path.exists(p) and p not in sys.path:
        sys.path.insert(0, p)

# 现在安全地导入核心库
load_success = False
load_error = None

try:
    import pyJianYingDraft as draft
    from ai_batch_editor import AIVideoEditor
    load_success = True
except Exception as e:
    load_error = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"

class Logger:
    """Redirects stdout to the GUI log window."""
    def __init__(self, log_func):
        self.log_func = log_func
    def write(self, message):
        if message.strip():
            self.log_func(message.strip())
    def flush(self):
        pass

class App:
    def to_portable_path(self, path):
        """将绝对路径转换为便携相对路径"""
        if not path: return ""
        try:
            abs_p = os.path.abspath(path)
            if abs_p.startswith(base_dir):
                return "./" + os.path.relpath(abs_p, base_dir).replace("\\", "/")
        except: pass
        return path

    def from_portable_path(self, path):
        """将便携路径还原为当前环境的绝对路径"""
        if not path: return ""
        if path.startswith("./"):
            return os.path.abspath(os.path.join(base_dir, path))
        return path

    def _parse_folder_info(self, folder_name):
        """解析文件夹名称中的日期、姓名、时长和后缀"""
        # 增强版正则：支持各种符号和空格分割
        # 1. 尝试匹配 8 位日期开头
        pattern = r"^(\d{8})?\s*(.*?)\s*(\d+[sS])?\s*(\d+)?$"
        match = re.search(pattern, folder_name)
        
        if match and (match.group(1) or match.group(3) or match.group(4)):
            return {
                "date": match.group(1) or "",
                "name": (match.group(2) or folder_name).strip("_ -"),
                "duration": match.group(3) or "",
                "suffix": match.group(4) or ""
            }
        
        # 保底逻辑：实在匹配不到结构，就认为全家都是名字，尝试提取末尾数字作后缀
        suffix_match = re.search(r"(\d+)$", folder_name)
        return {
            "date": "", "name": folder_name, "duration": "",
            "suffix": suffix_match.group(1) if suffix_match else ""
        }

    def _auto_detect_jianying(self):
        """暴力搜索剪映常用路径"""
        common_paths = [
            os.path.join(os.environ.get("LOCALAPPDATA", ""), r"JianyingPro\Apps\JianyingPro.exe"),
            r"C:\Program Files\JianyingPro\JianyingPro.exe",
            r"D:\Program Files\JianyingPro\JianyingPro.exe",
        ]
        # 尝试从注册表或快捷方式获取 (简化版直接搜路径)
        for p in common_paths:
            if os.path.exists(p): return p
        return ""

    def _load_initial_config(self):
        """加载初始配置和模版列表 (基于当前的 self.config_path)"""
        self.suppress_save = True
        try:
            # 1. 设置默认值
            self.api_key = ""
            self.base_url = "http://127.0.0.1:8090/v1"
            self.default_model = "gemini-3-flash"
            self.last_source_dir = ""
            self.last_output_dir = os.path.join(os.path.expanduser("~"), "Desktop")
            self.jianying_exe_path = r"C:\Users\Administrator\AppData\Local\JianyingPro\Apps\JianyingPro.exe"
            self.window_geometry = "1050x850" 
            self.templates_root = os.path.join(base_dir, "杭州森泊酒店", "杭州森泊工程模版")
            self.ai_prompt = (
                "避开起步静止。挑选人物进行中的片段，比如正在下楼，正在往前走，正在微笑等，避免录制前的静止不动画面。"
            )
            self.last_templates = [] # 现在支持多选
            self.last_template = ""  # 兼容旧版本
            self.name_format = "%Y%m%d-{name}-交付版"
            self.folder_format = "杭州开元森泊——%Y%m%d"
            self.draft_name_format = "AI_{name}_{template}" # 新增：草稿名称格式
            self.is_batch_mode = False # 记忆：是否勾选了批量模式
            self.last_batch_root = ""  # 记忆：上一次使用的批量根目录
            self.templates_selections = {} # {template_name: [selected_ids]}
            
            # --- 新增：Quicker 导出配置 ---
            self.use_quicker = False
            self.quicker_action_id = "ef7ec6e0-884c-472c-8834-411c6097f793"
            self.quicker_exe_path = r"C:\Program Files\Quicker\QuickerStarter.exe"
    
            # 2. 从文件加载覆盖
            print(f"[DEBUG] Loading config from: {self.config_path}")
            if os.path.exists(self.config_path):
                try:
                    with open(self.config_path, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
                        self.api_key = config_data.get("api_key", self.api_key)
                        self.base_url = config_data.get("base_url", self.base_url)
                        self.default_model = config_data.get("default_chat_model", self.default_model)
                        self.last_source_dir = self.from_portable_path(config_data.get("last_source_dir", ""))
                        self.last_output_dir = self.from_portable_path(config_data.get("last_output_dir", self.last_output_dir))
                        
                        # 优先使用配置的剪映路径，若无效则尝试自探测
                        saved_jy = config_data.get("jianying_exe_path", "")
                        if saved_jy and os.path.exists(saved_jy):
                            self.jianying_exe_path = saved_jy
                        else:
                            detected = self._auto_detect_jianying()
                            if detected: self.jianying_exe_path = detected
    
                        self.window_geometry = config_data.get("window_geometry", self.window_geometry)
                        self.templates_root = self.from_portable_path(config_data.get("templates_root", self.templates_root))
                        self.last_template = config_data.get("last_template", self.last_template)
                        self.last_templates = config_data.get("last_templates", [])
                        if not self.last_templates and self.last_template:
                            self.last_templates = [self.last_template]
                        self.name_format = config_data.get("name_format", self.name_format)
                        self.folder_format = config_data.get("folder_format", self.folder_format)
                        self.draft_name_format = config_data.get("draft_name_format", self.draft_name_format) # 从配置加载
                        self.is_batch_mode = config_data.get("is_batch_mode", False)
                        self.last_batch_root = self.from_portable_path(config_data.get("last_batch_root", ""))
                        self.templates_selections = copy.deepcopy(config_data.get("templates_selections", {}))
                        if "ai_prompt" in config_data:
                            self.ai_prompt = config_data["ai_prompt"]
                        
                        # 加载 Quicker 配置
                        self.use_quicker = config_data.get("use_quicker", False)
                        self.quicker_action_id = config_data.get("quicker_action_id", self.quicker_action_id)
                except Exception as e:
                    print(f"Error reading config file: {e}")
            
            self._refresh_templates()
        except Exception as e:
            print(f"Error loading config: {e}")
            self.templates_selections = {}
            self._refresh_templates()

    def _refresh_templates(self):
        """扫描当前模板根目录下的可用工程并生成复选框"""
        self.available_templates = []
        if os.path.exists(self.templates_root):
            for item in os.listdir(self.templates_root):
                if os.path.isdir(os.path.join(self.templates_root, item)):
                    self.available_templates.append(item)
        if not self.available_templates:
            self.available_templates = ["(未找到模板)"]
        
        if hasattr(self, 'tpl_list_inner'):
            for widget in self.tpl_list_inner.winfo_children():
                widget.destroy()
            self.template_checkboxes = {}
            
            for tpl in self.available_templates:
                var = tk.BooleanVar(value=(tpl in self.last_templates))
                # 勾选时不仅刷新片段解析，还要刷新配置下拉框
                cb = tk.Checkbutton(self.tpl_list_inner, text=tpl, variable=var, font=self.label_font,
                                   command=self._on_template_checked)
                cb.pack(anchor="w", padx=5)
                self.template_checkboxes[tpl] = var
            
            self._update_config_dropdown()
            self._bind_mousewheel(self.tpl_list_canvas)

    def _bind_mousewheel(self, widget):
        """为组件绑定鼠标滚轮滚动支持"""
        def _on_mousewheel(event):
            # Windows/MacOS 逻辑
            if event.delta:
                widget.yview_scroll(int(-1 * (event.delta / 120)), "units")
            # Linux 支持
            elif event.num == 4:
                widget.yview_scroll(-1, "units")
            elif event.num == 5:
                widget.yview_scroll(1, "units")
        
        # 绑定到 Canvas 本身及其所有子组件
        widget.bind_all("<MouseWheel>", _on_mousewheel)
        widget.bind_all("<Button-4>", _on_mousewheel)
        widget.bind_all("<Button-5>", _on_mousewheel)

    def _on_template_checked(self):
        """当模板勾选状态改变时"""
        self._update_config_dropdown()
        self._update_template_segments()

    def _update_config_dropdown(self):
        """刷新‘已选模板微调’的下拉框内容"""
        if not hasattr(self, 'cur_cfg_tpl_combo'): return
        checked = [tpl for tpl, var in self.template_checkboxes.items() if var.get()]
        self.cur_cfg_tpl_combo['values'] = checked
        if checked:
            if self.cur_cfg_tpl_var.get() not in checked:
                self.cur_cfg_tpl_combo.set(checked[0])
                self._update_template_segments(checked[0])
        else:
            self.cur_cfg_tpl_combo.set("")
            self._update_template_segments(None)

    def __init__(self, root):
        self.root = root
        self.root.title("森泊旅拍视频 AI 自动化剪辑系统 v1.0")
        self.is_running = False
        self.suppress_save = False 
        self.task_queue = [] 
        
        # 配置文件现在全部放在持久化目录
        self.profiles_dir = os.path.join(persistent_data_root, "profiles")
        if not os.path.exists(self.profiles_dir): 
            os.makedirs(self.profiles_dir)
            # 首次运行：如果打包目录下有默认配置，可以拷过来作为初始值
            bundle_profiles = os.path.join(base_dir, "profiles")
            if os.path.exists(bundle_profiles):
                for f in os.listdir(bundle_profiles):
                    shutil.copy(os.path.join(bundle_profiles, f), self.profiles_dir)
        
        # 记录“最后使用的酒店名”的主配置文件
        self.master_config_path = os.path.join(persistent_data_root, "master_config.json")
        last_profile = "default"
        if os.path.exists(self.master_config_path):
            try:
                with open(self.master_config_path, 'r', encoding='utf-8') as f:
                    last_profile = json.load(f).get("last_profile", "default")
            except: pass
        
        self.config_path = os.path.join(self.profiles_dir, f"{last_profile}.json")
        if not os.path.exists(self.config_path):
            self.config_path = os.path.join(self.profiles_dir, "default.json")
            if not os.path.exists(self.config_path):
                # 尝试从打包资源中的默认配置加载
                old_p = os.path.join(base_dir, ".agent", "skills", "antigravity-api-skill", "libs", "data", "config.json")
                if os.path.exists(old_p): shutil.copy(old_p, self.config_path)
                else: 
                    with open(self.config_path, 'w', encoding='utf-8') as f: json.dump({}, f)

        self.current_profile_name = os.path.basename(self.config_path).replace(".json", "")
        self._load_initial_config()
        self.root.geometry(self.window_geometry) 
        self.root.minsize(1000, 750) 
        self.root.configure(bg="#f5f5f5")
        
        # 监听窗口关闭事件以保存位置
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # 样式配置
        self.header_font = ("Microsoft YaHei", 16, "bold")
        self.label_font = ("Microsoft YaHei", 10)
        self.log_font = ("Consolas", 10)

        self._setup_ui()
        self.suppress_save = False # 初始化完成后，允许保存
        
        # 核心修复：UI 创建后立即刷新一次模板列表和勾选状态
        self._refresh_templates()

        # 绑定点击监听
        self.name_fmt_var.trace_add("write", self.on_fmt_change)
        self.path_var.trace_add("write", self.on_fmt_change)
        self.folder_fmt_var.trace_add("write", self.on_fmt_change)
        self.draft_name_fmt_var.trace_add("write", self.on_fmt_change)

        # 初始刷新预览
        self._update_name_preview()

        # 启动即检查加载状态
        if load_error:
            self.log(f"⚠️ 系统组件加载异常:\n{load_error}")

        # 11. 补拍报告持久化路径和初始加载
        self.reshoot_history_path = os.path.join(base_dir, "profiles", "reshoot_history.json")
        try:
            self._load_reshoot_history()
        except Exception as e:
            print(f"[!] 延迟加载补拍记录失败: {e}")

        # 设置默认 Tab
        self.active_tab = "run"
        self.switch_tab("templates")

        # --- UI 辅助方法 ---
    # --- 环境辅助方法 ---
    def _refresh_profiles_list(self):
        """刷新 profiles 文件夹下的 json 列表"""
        files = [f.replace(".json", "") for f in os.listdir(self.profiles_dir) if f.endswith(".json")]
        if "default" not in files:
            # 确保有一个默认配置
            default_p = os.path.join(self.profiles_dir, "default.json")
            if os.path.exists(self.config_path): shutil.copy(self.config_path, default_p)
            files.append("default")
        self.profile_combo['values'] = files
        
    def _on_profile_selected(self, event=None):
        name = self.profile_var.get()
        new_path = os.path.join(self.profiles_dir, f"{name}.json")
        
        self.log(f"[DEBUG] Attempting to switch profile to: {name} | Path: {new_path}")
        
        if os.path.exists(new_path):
            self.log(f"[*] 切换酒店预设: {name}")
            
            # 全程禁止保存，防止变量逐个更新时触发其中途保存导致数据错乱
            self.suppress_save = True
            try:
                # 永久切换当前配置路径，实现彻底隔离
                self.config_path = new_path
                self.current_profile_name = name
                
                # 显式清空旧状态，防止残留
                self.templates_selections = {}
                
                self._load_initial_config()
                # 再次强制禁止，因为 _load_initial_config 内部可能会将其设为 False
                self.suppress_save = True
                
                self.log(f"[DEBUG] Loaded config for {name}. Selections: {list(self.templates_selections.keys())}")
                
                # 手动同步 UI 变量 (防止配置残留)
                self.api_key_var.set(self.api_key)
                self.base_url_var.set(self.base_url)
                self.model_var.set(self.default_model)
                self.path_var.set(self.last_source_dir)
                self.output_dir_var.set(self.last_output_dir)
                self.jy_path_var.set(self.jianying_exe_path)
                self.tpl_root_var.set(self.templates_root)
                self.name_fmt_var.set(self.name_format)
                self.folder_fmt_var.set(self.folder_format)
                self.draft_name_fmt_var.set(self.draft_name_format)
                
                # 同步 Quicker 变量
                self.use_quicker_var.set(self.use_quicker)
                self.quicker_id_var.set(self.quicker_action_id)
                
                self.batch_mode_var.set(self.is_batch_mode)
                self.batch_path_var.set(self.last_batch_root)
                
                self.prompt_text.delete("1.0", "end")
                self.prompt_text.insert("1.0", self.ai_prompt)

                # 记录最后使用的酒店到 master 文件
                try:
                    with open(self.master_config_path, 'w', encoding='utf-8') as f:
                        json.dump({"last_profile": name}, f)
                except: pass
                
                # 刷新预览
                self._update_name_preview()
                
                if hasattr(self, 'cur_cfg_tpl_combo'):
                    self.cur_cfg_tpl_combo.set('') 
                self._refresh_templates()

                # 刷新批量模式状态和探测结果 (关键修复：切换配置文件后立即刷新UI和扫描)
                self._toggle_batch_mode()
                if self.batch_mode_var.get():
                    # 延时一点点确保 UI 更新完成
                    self.root.after(50, self._discover_and_show_clients)
                
            finally:
                self.suppress_save = False # 只有在一切就绪后才允许保存
        else:
            self.log(f"[ERROR] 找不到配置文件: {new_path}")
            messagebox.showerror("错误", f"找不到配置文件:\n{new_path}")

    def _save_current_profile(self):
        """覆盖保存当前选中的酒店配置 (隔离保存)"""
        self._save_config_immediate()
        self.log(f"[✅] 配置已保存至当前预设: {self.current_profile_name}")

    def _create_new_profile(self):
        """基于当前配置新建酒店预设"""
        from tkinter import simpledialog
        name = simpledialog.askstring("新建酒店预设", "请输入酒店/客户名称:")
        if name:
            new_path = os.path.join(self.profiles_dir, f"{name}.json")
            # 先给当前文件存个档
            self._save_config_immediate()
            # 复制一份到新文件
            shutil.copy(self.config_path, new_path)
            # 切换状态
            self.config_path = new_path
            self.current_profile_name = name
            self.profile_var.set(name)
            self._on_profile_selected() # 触发刷新
            self._refresh_profiles_list()
            self.log(f"[✅] 已为您新建酒店预设: {name}")

    def _delete_current_profile(self):
        """删除当前选中的酒店配置 (保留 default)"""
        name = self.current_profile_name
        if name == "default":
            messagebox.showwarning("警告", "无法删除默认配置 (default)！")
            return
            
        if not messagebox.askyesno("确认删除", f"确定要删除预设 [{name}] 及其所有配置吗？\n此操作不可恢复！"):
            return

        try:
            # 1. 删除文件
            if os.path.exists(self.config_path):
                os.remove(self.config_path)
            
            # 2. 切换回 default
            self.profile_var.set("default")
            self._on_profile_selected() # 触发切换逻辑
            self._refresh_profiles_list() # 刷新列表
            self.log(f"[🗑️] 已删除酒店预设: {name}")
            
        except Exception as e:
            messagebox.showerror("错误", f"删除失败: {e}")

    def _init_tab_queue(self):
        """任务队列 Tab"""
        f = tk.Frame(self.content_container, bg="#f5f5f5")
        self.tab_frames["queue"] = f
        
        header_f = tk.Frame(f, bg="#f5f5f5")
        header_f.pack(fill="x", pady=5)
        tk.Label(header_f, text="🚀 待生产任务列表", font=self.label_font, bg="#f5f5f5", fg="#2c3e50").pack(side="left")
        
        btn_f = tk.Frame(header_f, bg="#f5f5f5")
        btn_f.pack(side="right")
        tk.Button(btn_f, text="🗑️ 清空队列", command=self._clear_queue, bg="#95a5a6", fg="white", font=("Arial", 9)).pack(side="left", padx=5)
        
        # 列表区
        list_frame = tk.Frame(f, bg="white", bd=1, relief="sunken")
        list_frame.pack(fill="both", expand=True, pady=10)
        
        self.queue_list_canvas = tk.Canvas(list_frame, bg="white", highlightthickness=0)
        self.queue_list_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.queue_list_canvas.yview)
        self.queue_list_inner = tk.Frame(self.queue_list_canvas, bg="white")
        
        self.queue_list_canvas.create_window((0,0), window=self.queue_list_inner, anchor="nw")
        self.queue_list_canvas.configure(yscrollcommand=self.queue_list_scroll.set)
        
        self.queue_list_canvas.pack(side="left", fill="both", expand=True)
        self.queue_list_scroll.pack(side="right", fill="y")
        self._bind_mousewheel(self.queue_list_canvas)
        
        self.queue_empty_label = tk.Label(self.queue_list_inner, text="队列为空，请在‘运行中心’点击‘加入任务队列’", fg="gray", bg="white", pady=20)
        self.queue_empty_label.pack(fill="x")
        
    def add_current_to_queue(self, silent=False):
        """将当前面板的所有配置打包为一个 Task 对象"""
        # 获取基础信息
        mode = "batch" if self.batch_mode_var.get() else "single"
        path = self.batch_path_var.get() if mode == "batch" else self.path_var.get()
        
        if not path or not os.path.exists(path):
            if not silent: messagebox.showwarning("提示", "请先选择有效的素材路径再加入队列")
            return

        name = os.path.basename(path)
        selected_tpls = [tpl for tpl, var in self.template_checkboxes.items() if var.get()]
        if not selected_tpls:
            if not silent: messagebox.showwarning("提示", "请至少勾选一个模板")
            return

        # 打包快照
        task = {
            "id": datetime.now().strftime("%H%M%S"),
            "name": name,
            "mode": mode,
            "path": path,
            "templates": selected_tpls,
            "templates_selections": copy.deepcopy(self.templates_selections),
            "model": self.model_var.get(),
            "prompt": self.prompt_text.get("1.0", "end-1c"),
            "jy_path": self.jy_path_var.get(),
            "out_root": self.output_dir_var.get(),
            "name_fmt": self.name_fmt_var.get(),
            "folder_fmt": self.folder_fmt_var.get(),
            "draft_fmt": self.draft_name_fmt_var.get(),
            "tpl_root": self.tpl_root_var.get(),
            "use_quicker": self.use_quicker_var.get(),
            "quicker_id": self.quicker_id_var.get()
        }
        
        self.task_queue.append(task)
        self._refresh_queue_ui()
        if not silent: 
            self.log(f"[➕] 已将任务 '{name}' 加入调度队列。")
            self.switch_tab("queue")

    # --- 新增的多店分发逻辑 (修正版: 严格对应) ---
    def _show_multi_profile_dialog(self):
        """弹出多选对话框，可视化展示各店配置状态"""
        profiles = [f.replace(".json", "") for f in os.listdir(self.profiles_dir) if f.endswith(".json") and f != "default.json"]
        if not profiles:
            messagebox.showinfo("提示", "没有找到任何酒店预设文件")
            return

        win = tk.Toplevel(self.root)
        win.title("多店批量任务提交 (根据各店记忆的素材路径)")
        win.geometry("950x600")
        
        # 顶部控制区
        top_f = tk.Frame(win, pady=10, padx=10)
        top_f.pack(fill="x")
        
        tk.Label(top_f, text="✅ 请勾选要加入队列的任务:", font=("Microsoft YaHei", 12, "bold")).pack(anchor="w")
        tk.Label(top_f, text="说明: 程序将直接读取每个酒店预设中【上次保存的素材路径】来创建任务。", fg="#7f8c8d", font=("Arial", 10)).pack(anchor="w", pady=(5,0))
        
        # 列表区
        canvas = tk.Canvas(win, bg="white")
        frame = tk.Frame(canvas, bg="white")
        scrollbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        scrollbar.pack(side="right", fill="y", pady=10)
        canvas.create_window((0,0), window=frame, anchor="nw")
        
        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        
        # 表头
        header = tk.Frame(frame, bg="#ecf0f1", pady=8)
        header.pack(fill="x")
        tk.Label(header, text="启用", width=6, bg="#ecf0f1", font=("Arial", 9, "bold")).pack(side="left")
        tk.Label(header, text="酒店/预设名称", width=20, anchor="w", bg="#ecf0f1", font=("Arial", 9, "bold")).pack(side="left")
        tk.Label(header, text="该酒店绑定的素材路径 (自动读取配置)", width=55, anchor="w", bg="#ecf0f1", font=("Arial", 9, "bold")).pack(side="left")
        tk.Label(header, text="状态", width=12, bg="#ecf0f1", font=("Arial", 9, "bold")).pack(side="left")

        check_vars = {}
        
        current_mode = "batch" if self.batch_mode_var.get() else "single"
        mode_text = "批量目录" if current_mode == "batch" else "单客户目录"

        for pname in profiles:
            p_path = os.path.join(self.profiles_dir, f"{pname}.json")
            try:
                with open(p_path, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
            except: cfg = {}
            
            # 读取该配置记忆的路径
            saved_key = "last_batch_root" if current_mode == "batch" else "last_source_dir"
            saved_path_raw = self.from_portable_path(cfg.get(saved_key, ""))
            saved_tpl_count = len(cfg.get("last_templates", []))
            
            row = tk.Frame(frame, bg="white", pady=8)
            row.pack(fill="x", side="top")
            
            # 路径有效性检查
            path_valid = bool(saved_path_raw and os.path.exists(saved_path_raw))
            tpl_valid = saved_tpl_count > 0
            is_ready = path_valid and tpl_valid
            
            # 勾选 (默认: 如果就绪则勾选)
            var = tk.BooleanVar(value=is_ready)
            check_vars[pname] = var
            
            state = "normal" if is_ready else "disabled"
            cb = tk.Checkbutton(row, variable=var, bg="white", state=state)
            cb.pack(side="left", padx=5)
            
            # 名称
            tk.Label(row, text=pname, width=20, anchor="w", font=("Microsoft YaHei", 10, "bold"), bg="white", fg="#2c3e50").pack(side="left")
            
            # 路径展示
            path_color = "#27ae60" if path_valid else "#e74c3c"
            path_text = saved_path_raw if saved_path_raw else f"(未配置 {mode_text})"
            if len(path_text) > 60: path_text = "..." + path_text[-57:]
            
            tk.Label(row, text=path_text, width=60, anchor="w", fg=path_color, bg="white", font=("Consolas", 9)).pack(side="left")
            
            # 状态提示
            status_text = "就绪 ✅"
            status_fg = "#27ae60"
            if not path_valid:
                status_text = "路径无效 ❌" 
                status_fg = "#c0392b"
            elif not tpl_valid:
                status_text = "未选模版 ⚠️"
                status_fg = "#f39c12"
                
            tk.Label(row, text=status_text, width=12, fg=status_fg, bg="white", font=("Microsoft YaHei", 9)).pack(side="left")
            
            tk.Frame(frame, height=1, bg="#f0f0f0").pack(fill="x")

        def on_confirm():
            selected = [p for p, v in check_vars.items() if v.get()]
            if not selected: 
                messagebox.showwarning("提示", "未选择任何配置")
                return
            
            self._batch_add_profiles_to_queue(selected)
            win.destroy()
            
        btn_frame = tk.Frame(win, pady=15, bg="#ecf0f1")
        btn_frame.pack(fill="x")
        
        tk.Label(btn_frame, text=f"当前模式: {mode_text}", bg="#ecf0f1", fg="#7f8c8d").pack(side="top", pady=(0,5))
        tk.Button(btn_frame, text="🚀 确认提交任务", command=on_confirm, bg="#3498db", fg="white", font=("Microsoft YaHei", 12, "bold"), height=2, width=30).pack()

    def _batch_add_profiles_to_queue(self, profile_names):
        mode = "batch" if self.batch_mode_var.get() else "single"
        success_count = 0
        
        for pname in profile_names:
            json_path = os.path.join(self.profiles_dir, f"{pname}.json")
            if not os.path.exists(json_path): continue
            
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                
                # 读取各自的路径
                saved_key = "last_batch_root" if mode == "batch" else "last_source_dir"
                task_path = self.from_portable_path(cfg.get(saved_key, ""))
                
                if not task_path or not os.path.exists(task_path):
                    self.log(f"[跳过] {pname}: 记忆的素材路径无效 -> {task_path}")
                    continue

                saved_tpls = cfg.get("last_templates", [])
                if not saved_tpls:
                    self.log(f"[跳过] {pname}: 未保存选中的模板")
                    continue
                
                # 构造 task
                task = {
                    "id": f"{datetime.now().strftime('%H%M%S')}_{pname}",
                    "name": f"[{pname}] {os.path.basename(task_path)}", 
                    "client_name": None, 
                    "mode": mode,
                    "path": task_path,
                    
                    "templates": saved_tpls,
                    "templates_selections": cfg.get("templates_selections", {}),
                    "model": cfg.get("default_chat_model", self.default_model),
                    "prompt": cfg.get("ai_prompt", self.ai_prompt),
                    "jy_path": cfg.get("jianying_exe_path", self.jianying_exe_path),
                    "out_root": self.from_portable_path(cfg.get("last_output_dir", self.last_output_dir)),
                    "tpl_root": self.from_portable_path(cfg.get("templates_root", self.templates_root)),
                    "name_fmt": cfg.get("name_format", self.name_format),
                    "folder_fmt": cfg.get("folder_format", self.folder_format),
                    "draft_fmt": cfg.get("draft_name_format", self.draft_name_format),
                }
                
                self.task_queue.append(task)
                success_count += 1
                
            except Exception as e:
                self.log(f"[错误] 读取配置 {pname} 失败: {e}")
        
        if success_count > 0:
            self._refresh_queue_ui()
            self.switch_tab("queue")
            self.log(f"✅ 已批量添加 {success_count} 个多店任务 (各店使用各自路径)！")

    def _refresh_queue_ui(self):
        if not hasattr(self, 'queue_list_inner'): return
        for w in self.queue_list_inner.winfo_children(): w.destroy()
        
        if not self.task_queue:
            tk.Label(self.queue_list_inner, text="队列为空", fg="gray", bg="white", pady=20).pack(fill="x")
            return

        for i, task in enumerate(self.task_queue):
            item = tk.Frame(self.queue_list_inner, bg="white", pady=5)
            item.pack(fill="x", padx=10, pady=2)
            
            icon = "📂" if task['mode'] == 'batch' else "👤"
            txt = f"{i+1}. {icon} {task['name']} | 模板: {len(task['templates'])}个 | 引擎: {task['model']}"
            tk.Label(item, text=txt, font=self.label_font, bg="white", fg="#34495e").pack(side="left")
            
            tk.Button(item, text="❌", command=lambda idx=i: self._remove_task(idx), bg="white", fg="#e74c3c", bd=0).pack(side="right")
            tk.Frame(self.queue_list_inner, height=1, bg="#ecf0f1").pack(fill="x", padx=10)
        
        self.queue_list_inner.update_idletasks()
        self.queue_list_canvas.config(scrollregion=self.queue_list_canvas.bbox("all"))

    def _remove_task(self, idx):
        if 0 <= idx < len(self.task_queue):
            self.task_queue.pop(idx)
            self._refresh_queue_ui()

    def _clear_queue(self):
        self.task_queue = []
        self._refresh_queue_ui()

    def stop_task(self):
        """设置标记位以停止任务"""
        if self.is_running:
            self.is_running = False
            self.log("\n[!] 正在终止当前生产进度并清理队列，请稍候...")
            self.stop_btn.configure(state="disabled")

    # --- 原 UI 布局逻辑 ---
    def _setup_ui(self):
        """改版为侧边栏导航布局"""
        # --- 主容器 ---
        self.main_container = tk.Frame(self.root, bg="#f5f5f5")
        self.main_container.pack(fill="both", expand=True)

        # --- 左侧导航栏 ---
        self.nav_frame = tk.Frame(self.main_container, bg="#2c3e50", width=160)
        self.nav_frame.pack(side="left", fill="y")
        self.nav_frame.pack_propagate(False)

        tk.Label(self.nav_frame, text="Antigravity", font=("Arial", 14, "bold"), fg="#3498db", bg="#2c3e50", pady=20).pack()
        
        # --- 酒店预设切换 (Profile Selector) ---
        prof_f = tk.Frame(self.nav_frame, bg="#2c3e50", padx=10, pady=10)
        prof_f.pack(fill="x")
        tk.Label(prof_f, text="🏨 酒店预设切换:", font=("Microsoft YaHei", 9), fg="#bdc3c7", bg="#2c3e50").pack(anchor="w")
        
        self.profile_var = tk.StringVar(value=self.current_profile_name)
        self.profile_combo = ttk.Combobox(prof_f, textvariable=self.profile_var, state="readonly", font=("Arial", 9))
        self.profile_combo.pack(fill="x", pady=5)
        self.profile_combo.bind("<<ComboboxSelected>>", self._on_profile_selected)
        self._refresh_profiles_list()

        btn_prof_f = tk.Frame(prof_f, bg="#2c3e50")
        btn_prof_f.pack(fill="x")
        tk.Button(btn_prof_f, text="💾 保存", command=self._save_current_profile, bg="#27ae60", fg="white", bd=0, font=("Microsoft YaHei", 8)).pack(side="left", expand=True, fill="x", padx=1)
        tk.Button(btn_prof_f, text="🆕 新建", command=self._create_new_profile, bg="#3498db", fg="white", bd=0, font=("Microsoft YaHei", 8)).pack(side="left", expand=True, fill="x", padx=1)
        tk.Button(btn_prof_f, text="🗑️ 删除", command=self._delete_current_profile, bg="#e74c3c", fg="white", bd=0, font=("Microsoft YaHei", 8)).pack(side="left", expand=True, fill="x", padx=1)
        
        tk.Frame(self.nav_frame, height=1, bg="#34495e").pack(fill="x", pady=10)
        
        self.nav_buttons = {}
        tabs = [
            ("templates", "📂 素材与模板"),
            ("ai", "🤖 AI 配置"),
            ("output", "🎯 输出设置"),
            ("queue", "📋 任务队列"),
            ("run", "🚀 运行中心"),
            ("reshoot", "⚠️ 补拍报告")
        ]
        
        for tab_id, tab_name in tabs:
            btn = tk.Button(self.nav_frame, text=tab_name, font=self.label_font, 
                           bg="#2c3e50", fg="#ecf0f1", bd=0, padx=20, pady=15, anchor="w",
                           activebackground="#34495e", activeforeground="white",
                           command=lambda t=tab_id: self.switch_tab(t))
            btn.pack(fill="x")
            self.nav_buttons[tab_id] = btn

        # --- 右侧内容区 ---
        self.right_frame = tk.Frame(self.main_container, bg="#f5f5f5")
        self.right_frame.pack(side="right", fill="both", expand=True)

        # 头部标题
        self.tab_title_var = tk.StringVar(value="素材与模板配置")
        header = tk.Frame(self.right_frame, bg="white", height=50)
        header.pack(fill="x")
        tk.Label(header, textvariable=self.tab_title_var, font=self.header_font, bg="white", fg="#2c3e50", padx=20).pack(side="left", pady=10)

        # 内容容器 (用于切换各面板)
        self.content_container = tk.Frame(self.right_frame, bg="#f5f5f5", padx=20, pady=10)
        self.content_container.pack(fill="both", expand=True)

        # 初始化所有 Tab 面板
        self.tab_frames = {}
        self._init_tab_global()
        self._init_tab_templates()
        self._init_tab_output()
        self._init_tab_queue()
        self._init_tab_run()
        self._init_tab_reshoot()

    def switch_tab(self, tab_id):
        """切换面板"""
        for tid, frame in self.tab_frames.items():
            if tid == tab_id:
                frame.pack(fill="both", expand=True)
                self.nav_buttons[tid].config(bg="#3498db", fg="white")
                title_map = {
                    "ai": "🤖 AI 接口与剪辑策略", 
                    "templates": "📂 素材文件夹与模板多选", 
                    "output": "🎯 输出路径与格式化", 
                    "run": "🚀 生产线实时状态",
                    "reshoot": "⚠️ 补拍报告 - 素材时长不足清单"
                }
                self.tab_title_var.set(title_map.get(tid, ""))
            else:
                frame.pack_forget()
                self.nav_buttons[tid].config(bg="#2c3e50", fg="#ecf0f1")
        self.active_tab = tab_id

    def _init_tab_global(self):
        f = tk.Frame(self.content_container, bg="#f5f5f5")
        self.tab_frames["ai"] = f
        
        # 1. API 配置
        api_frame = tk.LabelFrame(f, text=" AI 接口配置 ", font=self.label_font, padx=10, pady=10)
        api_frame.pack(fill="x", pady=(0, 10))
        
        tk.Label(api_frame, text="API Key:").grid(row=0, column=0, sticky="w")
        self.api_key_var = tk.StringVar(value=self.api_key)
        tk.Entry(api_frame, textvariable=self.api_key_var, show="*", width=30).grid(row=0, column=1, padx=5)

        tk.Label(api_frame, text="模型:").grid(row=0, column=2, sticky="w", padx=(20,0))
        self.model_var = tk.StringVar(value=self.default_model)
        self.model_combo = ttk.Combobox(api_frame, textvariable=self.model_var, state="readonly", width=15)
        self.model_combo['values'] = ["gemini-3-pro", "gemini-3-flash"]
        self.model_combo.grid(row=0, column=3, padx=5)

        tk.Label(api_frame, text="Base URL:").grid(row=1, column=0, sticky="w", pady=5)
        self.base_url_var = tk.StringVar(value=self.base_url)
        tk.Entry(api_frame, textvariable=self.base_url_var, width=54).grid(row=1, column=1, columnspan=3, padx=5, sticky="w")

        # 2. 剪映路径
        env_frame = tk.LabelFrame(f, text=" 环境路径 ", font=self.label_font, padx=10, pady=10)
        env_frame.pack(fill="x", pady=10)
        
        tk.Label(env_frame, text="剪映主程序:").grid(row=0, column=0, sticky="w")
        self.jy_path_var = tk.StringVar(value=self.jianying_exe_path)
        tk.Entry(env_frame, textvariable=self.jy_path_var, width=54).grid(row=0, column=1, padx=5)
        tk.Button(env_frame, text="浏览", command=self.select_jy_exe).grid(row=0, column=2)

        # 3. Prompt
        prompt_frame = tk.LabelFrame(f, text=" AI 剪辑增强提示词 (Prompt) ", font=self.label_font, padx=10, pady=10)
        prompt_frame.pack(fill="both", expand=True, pady=10)
        
        # 用户自定义部分
        tk.Label(prompt_frame, text="✏️ 用户自定义策略 (可编辑):", font=("Arial", 9, "bold"), fg="#2980b9").pack(anchor="w")
        self.prompt_text = scrolledtext.ScrolledText(prompt_frame, height=6, font=self.log_font)
        self.prompt_text.pack(fill="x", pady=(0, 10))
        self.prompt_text.insert("1.0", self.ai_prompt)

        # 系统强制约束部分 (置灰只读)
        tk.Label(prompt_frame, text="🔒 系统核心强制约束 (自动追加):", font=("Arial", 9, "bold"), fg="#7f8c8d").pack(anchor="w")
        self.sys_prompt_text = scrolledtext.ScrolledText(prompt_frame, height=5, font=self.log_font, bg="#f0f0f0", fg="gray")
        self.sys_prompt_text.pack(fill="x")
        
        self.sys_constraints_template = (
            "【系统格式指令】:\n"
            "1. 为每个片段提供: reason(理由), description(内容), duration(时长)。\n"
            "2. duration: 根据内容精彩程度分配不同时长 (1.5-4秒)，不要均分!\n"
            "   - 精彩片段: 3-4秒 | 简单片段: 1.5-2秒 | 总和约 {total_duration} 秒\n"
            "3. 严格按此格式输出: \n"
            "   {{\n"
            "    \"segments\": [\n"
            "      {{\n"
            "        \"file_name\": \"C0001.MP4\", \n"
            "        \"start\": \"2.5s\", \n"
            "        \"duration\": \"3.0s\",  // 根据内容丰富度灵活设置\n"
            "        \"reason\": \"...挑选理由...\",\n"
            "        \"description\": \"...素材大意...\"\n"
            "      }},\n"
            "      ...\n"
            "    ]\n"
            "   }}"
        )
        self._update_sys_prompt_display(0) # 初始显示

    def _init_tab_templates(self):
        f = tk.Frame(self.content_container, bg="#f5f5f5")
        self.tab_frames["templates"] = f

        # 上部：模板库根目录设置 (从全局移入)
        lib_frame = tk.Frame(f, bg="#f5f5f5")
        lib_frame.pack(fill="x", pady=(0, 10))
        tk.Label(lib_frame, text="模板库路径:", font=self.label_font, bg="#f5f5f5").pack(side="left")
        self.tpl_root_var = tk.StringVar(value=self.templates_root)
        tk.Entry(lib_frame, textvariable=self.tpl_root_var, font=self.label_font).pack(side="left", fill="x", expand=True, padx=10)
        tk.Button(lib_frame, text="选择库目录", command=self.select_templates_folder, bg="#95a5a6", fg="white").pack(side="right")

        # ===== 批量处理模式切换 =====
        batch_mode_frame = tk.Frame(f, bg="#f5f5f5")
        batch_mode_frame.pack(fill="x", pady=(0, 10))
        
        self.batch_mode_var = tk.BooleanVar(value=self.is_batch_mode)
        self.batch_mode_check = tk.Checkbutton(
            batch_mode_frame, 
            text="📂 批量处理模式 (从父目录自动发现所有客户素材文件夹)", 
            variable=self.batch_mode_var, 
            font=("Microsoft YaHei", 10, "bold"), 
            fg="#8e44ad", bg="#f5f5f5",
            command=self._toggle_batch_mode
        )
        self.batch_mode_check.pack(side="left")
        
        # 批量模式说明
        self.batch_hint_label = tk.Label(
            batch_mode_frame, 
            text="", 
            font=("Arial", 9), fg="#7f8c8d", bg="#f5f5f5"
        )
        self.batch_hint_label.pack(side="left", padx=10)

        # --- 新增：元数据解析提示 ---
        tip_frame = tk.Frame(f, bg="#e8f4fd", bd=0) # 浅蓝色提示框
        tip_frame.pack(fill="x", pady=5)
        tk.Label(tip_frame, text="💡 智能识别建议格式: 20260128黄茜20s1 (日期8位+姓名+时长s+后缀1/2)\n💡 进阶建议: 若模版包含音效/特效绑定，建议在剪映中选中它们并点击'智能组合'，自动化更精准。", 
                 font=("Microsoft YaHei", 9), bg="#e8f4fd", fg="#2980b9", padx=10, pady=5, justify="left").pack(side="left")

        # 客户文件夹选择 (单个模式)
        self.single_path_frame = tk.Frame(f, bg="#f5f5f5")
        self.single_path_frame.pack(fill="x", pady=5)
        tk.Label(self.single_path_frame, text="客户素材文件夹:", font=self.label_font, bg="#f5f5f5").pack(side="left")
        self.path_var = tk.StringVar(value=self.last_source_dir)
        tk.Entry(self.single_path_frame, textvariable=self.path_var, font=self.label_font).pack(side="left", fill="x", expand=True, padx=10)
        tk.Button(self.single_path_frame, text="选择客户素材", command=self.select_folder, bg="#3498db", fg="white").pack(side="right")
        
        # 批量模式路径选择器 (初始隐藏)
        self.batch_path_frame = tk.Frame(f, bg="#f5f5f5")
        tk.Label(self.batch_path_frame, text="批量素材根目录:", font=self.label_font, bg="#f5f5f5").pack(side="left")
        self.batch_path_var = tk.StringVar(value=self.last_batch_root)
        tk.Entry(self.batch_path_frame, textvariable=self.batch_path_var, font=self.label_font).pack(side="left", fill="x", expand=True, padx=10)
        tk.Button(self.batch_path_frame, text="选择根目录", command=self.select_batch_folder, bg="#8e44ad", fg="white").pack(side="right", padx=5)
        tk.Button(self.batch_path_frame, text="🔍 探测", command=self._discover_and_show_clients, bg="#27ae60", fg="white").pack(side="right")
        
        # 批量探测结果展示区 (初始隐藏)
        self.batch_result_frame = tk.Frame(f, bg="#f5f5f5")
        self.batch_result_label = tk.Label(self.batch_result_frame, text="", font=self.label_font, fg="#16a085", bg="#f5f5f5", wraplength=700, justify="left")
        self.batch_result_label.pack(fill="x")

        # 中部：模板批量选择
        tpl_sel_frame = tk.LabelFrame(f, text=" 1. 勾选本次要生产的模板 (支持多选) ", font=self.label_font, padx=10, pady=10)
        tpl_sel_frame.pack(fill="x", pady=5)
        
        self.tpl_list_canvas = tk.Canvas(tpl_sel_frame, height=120, highlightthickness=0)
        self.tpl_list_scroll = ttk.Scrollbar(tpl_sel_frame, orient="vertical", command=self.tpl_list_canvas.yview)
        self.tpl_list_inner = tk.Frame(self.tpl_list_canvas)
        self.tpl_list_canvas.create_window((0,0), window=self.tpl_list_inner, anchor="nw")
        self.tpl_list_canvas.configure(yscrollcommand=self.tpl_list_scroll.set)
        self.tpl_list_canvas.pack(side="left", fill="both", expand=True)
        self.tpl_list_scroll.pack(side="right", fill="y")
        self.tpl_list_inner.bind("<Configure>", lambda e: self.tpl_list_canvas.configure(scrollregion=self.tpl_list_canvas.bbox("all")))
        self.template_checkboxes = {}

        # 下部：具体片段配置 (Tab里嵌套配置)
        seg_manage_frame = tk.LabelFrame(f, text=" 2. 已选模板素材微调 (关键步骤) ", font=self.label_font, padx=10, pady=10, fg="#e67e22")
        seg_manage_frame.pack(fill="both", expand=True, pady=5)
        
        # 增加一个下拉框来选择“当前正在配置哪个模板的素材”
        choice_frame = tk.Frame(seg_manage_frame, pady=5)
        
        # 应用初始可见性同步
        self._toggle_batch_mode()
        # 如果是批量模式且有路径，初始化时自动探测一次
        if self.is_batch_mode and self.last_batch_root:
            self.root.after(100, self._discover_and_show_clients)
        choice_frame.pack(fill="x")
        tk.Label(choice_frame, text="当前配置模板:", font=self.label_font, fg="#d35400").pack(side="left")
        self.cur_cfg_tpl_var = tk.StringVar()
        self.cur_cfg_tpl_combo = ttk.Combobox(choice_frame, textvariable=self.cur_cfg_tpl_var, state="readonly", font=self.label_font)
        self.cur_cfg_tpl_combo.pack(side="left", fill="x", expand=True, padx=10)
        self.cur_cfg_tpl_combo.bind("<<ComboboxSelected>>", lambda e: self._update_template_segments(self.cur_cfg_tpl_var.get()))

        # 片段解析展示区
        self.tpl_info_frame = tk.Frame(seg_manage_frame) 
        self.tpl_info_frame.pack(fill="both", expand=True)

        self.tpl_canvas = tk.Canvas(self.tpl_info_frame, highlightthickness=0)
        self.tpl_scroll = ttk.Scrollbar(self.tpl_info_frame, orient="vertical", command=self.tpl_canvas.yview)
        self.tpl_inner_frame = tk.Frame(self.tpl_canvas)
        self.tpl_canvas.create_window((0,0), window=self.tpl_inner_frame, anchor="nw")
        self.tpl_canvas.configure(yscrollcommand=self.tpl_scroll.set)
        self.tpl_canvas.pack(side="left", fill="both", expand=True)
        self.tpl_scroll.pack(side="right", fill="y")
        self.tpl_inner_frame.bind("<Configure>", lambda e: self.tpl_canvas.configure(scrollregion=self.tpl_canvas.bbox("all")))
        
        # 绑定鼠标滚轮
        self._bind_mousewheel(self.tpl_canvas)

    def _init_tab_output(self):
        f = tk.Frame(self.content_container, bg="#f5f5f5")
        self.tab_frames["output"] = f
        
        out_frame = tk.LabelFrame(f, text=" 📂 导出路径自动化配置 ", font=self.label_font, padx=15, pady=15)
        out_frame.pack(fill="x")

        # --- 新增：变量组合建议提示 ---
        var_tip_f = tk.Frame(f, bg="#fcf3cf", bd=0) 
        var_tip_f.pack(fill="x", pady=(5, 10))
        tk.Label(var_tip_f, text="💡 推荐组合: {orig_date}_{name}_{duration}_{suffix} (对应: 20260128_黄茜_20s_1)", 
                 font=("Microsoft YaHei", 9), bg="#fcf3cf", fg="#b7950b", padx=10, pady=5).pack(side="left")

        # 合并感更强的布局
        row_root = tk.Frame(out_frame)
        row_root.pack(fill="x", pady=5)
        tk.Label(row_root, text="导出根目录:", width=12, anchor="w").pack(side="left")
        self.output_dir_var = tk.StringVar(value=self.last_output_dir)
        tk.Entry(row_root, textvariable=self.output_dir_var).pack(side="left", fill="x", expand=True, padx=5)
        tk.Button(row_root, text="浏览...", command=self.select_output_folder).pack(side="left")

        # 辅助函数：创建可复制的变量提示
        def create_copyable_hint(parent, text):
            # 使用只读 Entry 替代 Label 使其可复制
            e = tk.Entry(parent, font=("Arial", 8), fg="#7f8c8d", bd=0, bg="#f5f5f5", width=65)
            e.insert(0, text)
            e.config(state="readonly")
            return e

        # 1. 子目录配置
        row_folder = tk.Frame(out_frame)
        row_folder.pack(fill="x", pady=(5, 0))
        tk.Label(row_folder, text="子目录(格式):", width=12, anchor="w").pack(side="left")
        self.folder_fmt_var = tk.StringVar(value=self.folder_format)
        tk.Entry(row_folder, textvariable=self.folder_fmt_var).pack(side="left", fill="x", expand=True, padx=5)
        create_copyable_hint(row_folder, "变量: {name}姓名, {orig_date}原始日期, {duration}时长, {suffix}后缀, %Y%m%d今日").pack(side="left")
        
        # 子目录预览
        self.folder_preview_var = tk.StringVar()
        tk.Label(out_frame, textvariable=self.folder_preview_var, font=("Consolas", 8), fg="#7f8c8d", anchor="w").pack(fill="x", padx=(95, 0), pady=(0, 5))

        # 2. 文件名配置
        row_file = tk.Frame(out_frame)
        row_file.pack(fill="x", pady=(5, 0))
        tk.Label(row_file, text="文件名(格式):", width=12, anchor="w").pack(side="left")
        self.name_fmt_var = tk.StringVar(value=self.name_format)
        tk.Entry(row_file, textvariable=self.name_fmt_var).pack(side="left", fill="x", expand=True, padx=5)
        create_copyable_hint(row_file, "变量: {name}姓名, {orig_date}原始日期, {duration}时长, {suffix}后缀, %Y%m%d今日").pack(side="left")
        
        # 文件名预览
        self.file_preview_var = tk.StringVar()
        tk.Label(out_frame, textvariable=self.file_preview_var, font=("Consolas", 8), fg="#7f8c8d", anchor="w").pack(fill="x", padx=(95, 0), pady=(0, 5))

        # 3. 草稿名配置
        row_draft = tk.Frame(out_frame)
        row_draft.pack(fill="x", pady=(5, 0))
        tk.Label(row_draft, text="草稿名(格式):", width=12, anchor="w").pack(side="left")
        self.draft_name_fmt_var = tk.StringVar(value=self.draft_name_format)
        tk.Entry(row_draft, textvariable=self.draft_name_fmt_var).pack(side="left", fill="x", expand=True, padx=5)
        create_copyable_hint(row_draft, "变量: {name}姓名, {template}模板名, {orig_date}原始日期, {duration}时长, {suffix}后缀, %Y%m%d今日").pack(side="left")
        
        # 草稿名预览
        self.draft_preview_var = tk.StringVar()
        tk.Label(out_frame, textvariable=self.draft_preview_var, font=("Consolas", 8), fg="#7f8c8d", anchor="w").pack(fill="x", padx=(95, 0), pady=(0, 5))
        
        preview_frame = tk.LabelFrame(f, text=" 📋 最终生产路径预览 (交付文件) ", font=self.label_font, padx=10, pady=10, fg="#2c3e50")
        preview_frame.pack(fill="x", pady=20)
        self.output_name_var = tk.StringVar()
        tk.Entry(preview_frame, textvariable=self.output_name_var, font=self.log_font, fg="#16a085", state="readonly", bd=0, bg="#f5f5f5").pack(fill="x")

        # --- 新增：Quicker 导出设置区 ---
        q_frame = tk.LabelFrame(f, text=" ⚡ Quicker 强化导出 (解决 UI 卡死) ", font=self.label_font, padx=15, pady=10, fg="#8e44ad")
        q_frame.pack(fill="x", pady=5)
        
        row_q1 = tk.Frame(q_frame)
        row_q1.pack(fill="x")
        self.use_quicker_var = tk.BooleanVar(value=self.use_quicker)
        tk.Checkbutton(row_q1, text="启用 Quicker 动作接手导出 (推荐)", variable=self.use_quicker_var, 
                       font=("Microsoft YaHei", 9, "bold"), fg="#8e44ad", command=self._save_config_immediate).pack(side="left")
        
        row_q2 = tk.Frame(q_frame)
        row_q2.pack(fill="x", pady=5)
        tk.Label(row_q2, text="动作 ID:", width=10, anchor="w").pack(side="left")
        self.quicker_id_var = tk.StringVar(value=self.quicker_action_id)
        tk.Entry(row_q2, textvariable=self.quicker_id_var, width=45).pack(side="left", padx=5)
        tk.Label(row_q2, text="注: 需安装 Quicker 客户端", font=("Arial", 8), fg="gray").pack(side="left")

    def _init_tab_run(self):
        f = tk.Frame(self.content_container, bg="#f5f5f5")
        self.tab_frames["run"] = f
        
        # 顶部工具栏
        top_bar = tk.Frame(f, bg="#f5f5f5", pady=10)
        top_bar.pack(fill="x")
        
        tk.Label(top_bar, text="快速操作:", font=("Microsoft YaHei", 10, "bold"), bg="#f5f5f5").pack(side="left", padx=(5,10))
        
        self.add_multi_btn = tk.Button(top_bar, text="🌐 批量添加多店/多任务", font=("Microsoft YaHei", 10),
                                     bg="#8e44ad", fg="white", height=1, padx=10, command=self._show_multi_profile_dialog)
        self.add_multi_btn.pack(side="left")

        # 按钮容器
        btn_frame = tk.Frame(f, bg="#f5f5f5")
        btn_frame.pack(fill="x", pady=(0, 20))

        self.add_queue_btn = tk.Button(btn_frame, text="➕ 加入任务队列", font=("Microsoft YaHei", 11),
                                     bg="#3498db", fg="white", height=2, command=self.add_current_to_queue)
        self.add_queue_btn.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.start_btn = tk.Button(btn_frame, text="🚀 开启全量生产", font=("Microsoft YaHei", 11, "bold"),
                                   bg="#27ae60", fg="white", height=2, command=self.start_thread)
        self.start_btn.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.stop_btn = tk.Button(btn_frame, text="🛑 停止", font=("Microsoft YaHei", 11, "bold"),
                                  bg="#e74c3c", fg="white", height=2, state="disabled", command=self.stop_task)
        self.stop_btn.pack(side="right", fill="x", expand=True)

        # 当前任务结果
        res_frame = tk.LabelFrame(f, text=" AI 选片快照 ", font=self.label_font, padx=10, pady=5)
        res_frame.pack(fill="x", pady=(0, 10))
        self.ai_res_area = tk.Text(res_frame, height=6, font=self.log_font, bg="#f9f9f9", fg="#2980b9", state="disabled")
        self.ai_res_area.pack(fill="x")

        # 实时日志
        log_frame = tk.LabelFrame(f, text=" 执行日志 ", font=self.label_font, padx=10, pady=10)
        log_frame.pack(fill="both", expand=True)
        self.log_area = scrolledtext.ScrolledText(log_frame, state="disabled", font=self.log_font, bg="#1e1e1e", fg="#dcdcdc")
        self.log_area.pack(fill="both", expand=True)

    def _init_tab_reshoot(self):
        """初始化补拍报告 Tab"""
        f = tk.Frame(self.content_container, bg="#f5f5f5")
        self.tab_frames["reshoot"] = f
        
        # 顶部说明和操作按钮
        top_frame = tk.Frame(f, bg="#f5f5f5")
        top_frame.pack(fill="x", pady=(0, 10))
        
        tk.Label(top_frame, text="以下素材因时长不足被自动截断，建议补拍或更换素材：", 
                font=self.label_font, bg="#f5f5f5", fg="#e74c3c").pack(side="left")
        
        tk.Button(top_frame, text="🗑️ 清空列表", command=self._clear_reshoot_list, 
                 bg="#95a5a6", fg="white", font=("Arial", 9)).pack(side="right", padx=5)
        tk.Button(top_frame, text="📋 导出报告", command=self._export_reshoot_report, 
                 bg="#3498db", fg="white", font=("Arial", 9)).pack(side="right")
        
        # 报告列表区域
        list_frame = tk.LabelFrame(f, text=" 📹 补拍清单 ", font=self.label_font, padx=10, pady=10)
        list_frame.pack(fill="both", expand=True)
        
        self.reshoot_text = scrolledtext.ScrolledText(list_frame, font=self.log_font, 
                                                       bg="#fff9e6", fg="#8b4513", state="disabled", cursor="arrow")
        self.reshoot_text.pack(fill="both", expand=True)
        
        # 配置超链接标签
        self.reshoot_text.tag_config("path_link", foreground="#2980b9", underline=True)
        self.reshoot_text.tag_bind("path_link", "<Button-1>", self._on_path_click)
        self.reshoot_text.tag_bind("path_link", "<Enter>", lambda e: self.reshoot_text.config(cursor="hand2"))
        self.reshoot_text.tag_bind("path_link", "<Leave>", lambda e: self.reshoot_text.config(cursor="arrow"))
        
        # 统计信息
        self.reshoot_count_var = tk.StringVar(value="当前无补拍记录")
        tk.Label(f, textvariable=self.reshoot_count_var, font=("Arial", 10), 
                fg="#7f8c8d", bg="#f5f5f5").pack(anchor="w", pady=5)
        
        # 存储所有补拍记录
        self.reshoot_records = []

    def _on_path_click(self, event):
        """点击路径链接打开文件夹"""
        # 获取点击位置处的标签
        try:
            index = self.reshoot_text.index(f"@{event.x},{event.y}")
            tags = self.reshoot_text.tag_names(index)
            for tag in tags:
                if tag.startswith("path:"):
                    path = tag[5:]
                    if os.path.exists(path):
                        os.startfile(path)
                    return
        except:
            pass
    
    def _clear_reshoot_list(self):
        """清空补拍列表"""
        self.reshoot_records = []
        if os.path.exists(self.reshoot_history_path):
            try: os.remove(self.reshoot_history_path)
            except: pass
        self.reshoot_text.configure(state="normal")
        self.reshoot_text.delete(1.0, "end")
        self.reshoot_text.configure(state="disabled")
        self.reshoot_count_var.set("当前无补拍记录")

    def _save_reshoot_history(self):
        """保存补拍记录到本地"""
        try:
            os.makedirs(os.path.dirname(self.reshoot_history_path), exist_ok=True)
            with open(self.reshoot_history_path, 'w', encoding='utf-8') as f:
                json.dump(self.reshoot_records, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[!] 保存历史补拍记录失败: {e}")

    def _load_reshoot_history(self):
        """从本地加载补拍历史"""
        if not os.path.exists(self.reshoot_history_path): return
        try:
            with open(self.reshoot_history_path, 'r', encoding='utf-8') as f:
                records = json.load(f)
                # 重新分类渲染 (复用已有的逻辑)
                # 由于 records 已经是混合顺序，我们这里简单平铺
                temp_records = records
                self.reshoot_records = [] # 清空并在渲染时重新填充
                
                # 简单的分组渲染逻辑：按客户分组
                from collections import defaultdict
                groups = defaultdict(list)
                for r in temp_records:
                    groups[r.get("client", "未知")].append(r)
                
                for client, items in groups.items():
                    # 这里有一个问题，add_reshoot_warning 期望的是 warning 列表
                    # 我们直接手动渲染以保证精准
                    self._render_record_group(client, items)
                    
        except Exception as e:
            print(f"[!] 加载历史补拍记录失败: {e}")

    def _render_record_group(self, client, items):
        """手动渲染一组记录到 UI，并保持交互性"""
        self.reshoot_text.configure(state="normal")
        self.reshoot_text.insert("end", f"\n{'='*40}\n")
        self.reshoot_text.insert("end", f"📦 客户: {client} (历史记录)\n")
        
        # 尝试从第一条记录提取详情
        first = items[0]
        fpath = first.get("path", "")
        draft = first.get("draft", "未知")
        
        if fpath:
            self.reshoot_text.insert("end", "   📂 素材路径: ")
            ps = self.reshoot_text.index("end-1c")
            self.reshoot_text.insert("end", f"{fpath}\n")
            pe = self.reshoot_text.index("end-1c")
            self.reshoot_text.tag_add("path_link", ps, pe)
            self.reshoot_text.tag_add(f"path:{fpath}", ps, pe)
        
        self.reshoot_text.insert("end", f"   🎬 草稿名称: {draft}\n")
        self.reshoot_text.insert("end", f"{'-'*40}\n")
        
        for r in items:
            self.reshoot_records.append(r)
            if r.get("type") == "material_shortage":
                self.reshoot_text.insert("end", f"  ❗ [严重] 素材总数不足: 现有 {r.get('video_count')} / 需 {r.get('target_count')}\n")
            else:
                self.reshoot_text.insert("end", f"  📹 {r.get('file', '未知')}\n")
                self.reshoot_text.insert("end", f"     需要: {r.get('requested', 0)}s | 可用: {r.get('available', 0)}s | 差: {r.get('shortage', 0)}s\n")
        
        self.reshoot_text.configure(state="disabled")
        self.reshoot_count_var.set(f"共 {len(self.reshoot_records)} 条补拍记录")
    
    def _export_reshoot_report(self):
        """导出补拍报告到文件"""
        if not self.reshoot_records:
            messagebox.showinfo("提示", "当前没有补拍记录")
            return
        
        from tkinter import filedialog
        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
            title="保存补拍报告"
        )
        if filepath:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("========== 素材补拍报告 ==========\n")
                f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"共 {len(self.reshoot_records)} 条记录\n\n")
                
                for i, rec in enumerate(self.reshoot_records):
                    if rec.get("type") == "material_shortage":
                        f.write(f"{i+1}. [❗素材不足警告] 客户: {rec.get('client')}\n")
                        f.write(f"   路径: {rec.get('path')}\n")
                        f.write(f"   素材数: {rec.get('video_count')} | 模版需要: {rec.get('target_count')}\n\n")
                    else:
                        f.write(f"{i+1}. [📹 时长不足] 客户: {rec.get('client', '未知')}\n")
                        f.write(f"   文件: {rec.get('file', '未知')}\n")
                        f.write(f"   需要: {rec.get('requested', 0)}s, 可用: {rec.get('available', 0)}s, 差: {rec.get('shortage', 0)}s\n")
                        f.write(f"   起始点: {rec.get('start', 0)}s, 素材总时长: {rec.get('total', 0)}s\n\n")
            
            messagebox.showinfo("成功", f"补拍报告已保存到:\n{filepath}")
    
    def add_reshoot_warning(self, client_name: str, folder_path: str, draft_name: str, warnings: list):
        """添加补拍警告到报告列表"""
        if not warnings:
            return
        
        self.reshoot_text.configure(state="normal")
        
        # 添加客户分隔标题
        self.reshoot_text.insert("end", f"\n{'='*40}\n")
        self.reshoot_text.insert("end", f"📦 客户: {client_name}\n")
        
        # 插入可点击路径
        self.reshoot_text.insert("end", "   📂 素材路径: ")
        path_start = self.reshoot_text.index("end-1c")
        self.reshoot_text.insert("end", f"{folder_path}\n")
        path_end = self.reshoot_text.index("end-1c")
        self.reshoot_text.tag_add("path_link", path_start, path_end)
        self.reshoot_text.tag_add(f"path:{folder_path}", path_start, path_end)
        
        self.reshoot_text.insert("end", f"   🎬 草稿名称: {draft_name}\n")
        self.reshoot_text.insert("end", f"{'-'*40}\n")
        
        for warn in warnings:
            record = {
                "type": "duration_shortage",
                "client": client_name,
                "path": folder_path,
                "draft": draft_name,
                "file": warn.get("file", ""),
                "requested": warn.get("requested", 0),
                "available": warn.get("available", 0),
                "shortage": warn.get("shortage", 0),
                "start": warn.get("start", 0),
                "total": warn.get("total", 0)
            }
            self.reshoot_records.append(record)
            
            self.reshoot_text.insert("end", f"  📹 {warn.get('file', '未知')}\n")
            self.reshoot_text.insert("end", f"     需要: {warn.get('requested', 0)}s | 可用: {warn.get('available', 0)}s | 差: {warn.get('shortage', 0)}s\n")
            self.reshoot_text.insert("end", f"     起始点: {warn.get('start', 0)}s | 素材总时长: {warn.get('total', 0)}s\n\n")
        
        self.reshoot_text.see("end")
        self.reshoot_text.configure(state="disabled")
        
        # 更新统计
        self.reshoot_count_var.set(f"共 {len(self.reshoot_records)} 条补拍记录")
        self._save_reshoot_history()

    def add_client_material_shortage_warning(self, client_name: str, folder_path: str, draft_name: str, video_count: int, target_count: int):
        """添加素材总数不足的严重警告到报告最上方"""
        self.reshoot_text.configure(state="normal")
        
        # 始终插入在最前面 (1.0)
        marker = "1.0"
        self.reshoot_text.insert(marker, f"{'-'*60}\n")
        self.reshoot_text.insert(marker, f"   可能结果: AI 将强制重复使用素材或导致画面缺失，请务必核查！\n")
        self.reshoot_text.insert(marker, f"   发现视频: {video_count} 个 | 模版需要: {target_count} 个\n")
        self.reshoot_text.insert(marker, f"   🎬 草稿名称: {draft_name}\n")
        
        self.reshoot_text.insert(marker, "   📂 路径: ")
        path_start = self.reshoot_text.index(marker)
        self.reshoot_text.insert(marker, f"{folder_path}\n")
        path_end = self.reshoot_text.index(marker) # 这里的逻辑稍显复杂，因为是倒序插入，但 tag 还是按绝对 index 给
        
        # 对于 1.0 插入，由于是倒序，我们换一种顺序
        self.reshoot_text.delete("1.0", "end") # 简单处理：重新构建头部
        
        full_msg_head = (
            f"❗ [严重警告] 客户素材不足！\n"
            f"   客户: {client_name}\n"
        )
        self.reshoot_text.insert("1.0", full_msg_head)
        
        self.reshoot_text.insert("end", "   📂 路径: ")
        path_start = self.reshoot_text.index("end-1c")
        self.reshoot_text.insert("end", f"{folder_path}\n")
        path_end = self.reshoot_text.index("end-1c")
        self.reshoot_text.tag_add("path_link", path_start, path_end)
        self.reshoot_text.tag_add(f"path:{folder_path}", path_start, path_end)
        
        self.reshoot_text.insert("end", f"   🎬 草稿名称: {draft_name}\n")
        self.reshoot_text.insert("end", f"   发现视频: {video_count} 个 | 模版需要: {target_count} 个\n")
        self.reshoot_text.insert("end", f"   可能结果: AI 将强制重复使用素材或导致画面缺失，请务必核查！\n")
        self.reshoot_text.insert("end", f"{'-'*60}\n")

        self.reshoot_text.configure(state="disabled")
        
        # 存入记录
        self.reshoot_records.insert(0, {
            "type": "material_shortage",
            "client": client_name,
            "path": folder_path,
            "draft": draft_name,
            "video_count": video_count,
            "target_count": target_count
        })
        self.reshoot_count_var.set(f"共 {len(self.reshoot_records)} 条补拍记录")
        self._save_reshoot_history()

    def log(self, message):
        """线程安全的日志打印"""
        self.log_area.configure(state="normal")
        self.log_area.insert("end", f"{message}\n")
        self.log_area.see("end")
        self.log_area.configure(state="disabled")
        self.root.update_idletasks()

    def select_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.path_var.set(path)
            self._update_name_preview()
    
    def select_batch_folder(self):
        """选择批量处理的根目录"""
        path = filedialog.askdirectory(title="选择包含多个客户素材的根目录")
        if path:
            self.batch_path_var.set(path)
            self._save_config_immediate()
            # 自动探测
            self._discover_and_show_clients()
    
    def _toggle_batch_mode(self):
        """切换批量处理模式的UI显示"""
        if self.batch_mode_var.get():
            # 进入批量模式
            self.single_path_frame.pack_forget()
            self.batch_path_frame.pack(fill="x", pady=5, after=self.batch_mode_check.master)
            self.batch_result_frame.pack(fill="x", pady=5, after=self.batch_path_frame)
            self.batch_hint_label.config(text="请选择包含多个客户文件夹的父目录")
        else:
            # 退出批量模式
            self.batch_path_frame.pack_forget()
            self.batch_result_frame.pack_forget()
            self.single_path_frame.pack(fill="x", pady=5, after=self.batch_mode_check.master)
            self.batch_hint_label.config(text="")
        
        self._save_config_immediate()
    
    def _discover_client_folders(self, root_path: str) -> list:
        """
        智能发现客户素材文件夹。
        识别规则：包含 MP4/MOV 视频文件的最深层级文件夹
        返回：[(folder_path, client_name), ...]
        """
        client_folders = []
        video_exts = ('.mp4', '.mov', '.MP4', '.MOV')
        
        for dirpath, dirnames, filenames in os.walk(root_path):
            # 检查该目录下是否有视频文件
            has_video = any(f.endswith(video_exts) for f in filenames)
            if has_video:
                # 提取客户名、日期、时长等信息
                folder_name = os.path.basename(dirpath)
                info = self._parse_folder_info(folder_name)
                
                # 统计视频文件数量
                video_count = sum(1 for f in filenames if f.endswith(video_exts))
                
                client_folders.append({
                    'path': dirpath,
                    'name': info["name"],
                    'orig_date': info["date"],
                    'duration': info["duration"],
                    'suffix': info["suffix"],
                    'folder': folder_name,
                    'video_count': video_count
                })
        
        return client_folders
    
    def _discover_and_show_clients(self):
        """探测并展示发现的客户文件夹"""
        root_path = self.batch_path_var.get().strip()
        if not root_path or not os.path.exists(root_path):
            messagebox.showwarning("提示", "请先选择有效的批量素材根目录")
            return
        
        clients = self._discover_client_folders(root_path)
        if not clients:
            self.batch_result_label.config(
                text="⚠️ 未在该目录下发现任何包含视频的客户文件夹", 
                fg="#e74c3c"
            )
        else:
            preview_lines = [f"✅ 已发现 {len(clients)} 个客户素材文件夹:"]
            for i, c in enumerate(clients[:10]):  # 最多显示前10个
                info_bits = []
                if c['orig_date']: info_bits.append(f"日期:{c['orig_date']}")
                if c['duration']: info_bits.append(f"时长:{c['duration']}")
                if c['suffix']: info_bits.append(f"后缀:{c['suffix']}")
                info_str = f" [{' '.join(info_bits)}]" if info_bits else ""
                preview_lines.append(f"   {i+1}. {c['name']}{info_str} ({c['video_count']}个视频) - {c['folder']}")
            if len(clients) > 10:
                preview_lines.append(f"   ... 还有 {len(clients) - 10} 个未显示")
            
            self.batch_result_label.config(
                text="\n".join(preview_lines), 
                fg="#16a085"
            )
            self._discovered_clients = clients  # 缓存结果

    def _update_name_preview(self):
        """根据格式更新预览路径 (规范化绝对路径)"""
        path = self.path_var.get()
        out_root = self.output_dir_var.get()
        fmt_name = self.name_fmt_var.get()
        fmt_folder = self.folder_fmt_var.get()
        fmt_draft = self.draft_name_fmt_var.get()
        
        info = {"date": "", "name": "", "duration": "", "suffix": ""}
        if path:
            folder_name = os.path.basename(path)
            info = self._parse_folder_info(folder_name)
        
        # 只有在完全没有路径信息时才使用 Mock 数据
        if not path and not info["date"] and not info["suffix"] and not info["duration"]:
            info = {"date": "20260128", "name": "王小明", "duration": "20s", "suffix": "1"}
        
        # 确保 preview 始终有基本显示名
        client_name = info["name"] if info["name"] else "新客户"
        
        try:
            now = datetime.now()
            
            # 1. 子目录预览
            subfolder = fmt_folder.replace("{name}", client_name)
            subfolder = subfolder.replace("{orig_date}", info["date"]).replace("{duration}", info["duration"]).replace("{suffix}", info["suffix"])
            subfolder = now.strftime(subfolder) # 允许strftime处理日期部分
            self.folder_preview_var.set(f"预览: {subfolder}")

            # 2. 文件名预览
            filename = fmt_name.replace("{name}", client_name)
            filename = filename.replace("{orig_date}", info["date"]).replace("{duration}", info["duration"]).replace("{suffix}", info["suffix"])
            filename = now.strftime(filename) # 允许strftime处理日期部分
            if not filename.lower().endswith(".mp4"): filename += ".mp4"
            self.file_preview_var.set(f"预览: {filename}")

            # 3. 草稿名预览
            target_tpl = getattr(self, 'last_template', "测试模版")
            draftname = fmt_draft.replace("{name}", client_name).replace("{template}", target_tpl)
            draftname = draftname.replace("{orig_date}", info["date"]).replace("{duration}", info["duration"]).replace("{suffix}", info["suffix"])
            draftname = now.strftime(draftname) # 允许strftime处理日期部分
            self.draft_preview_var.set(f"预览: {draftname}")
            
            # 4. 最终路径汇总
            full_path = os.path.join(out_root, subfolder, filename)
            if out_root:
                full_path = os.path.abspath(full_path)
            self.output_name_var.set(os.path.normpath(full_path))
        except Exception as e:
            self.output_name_var.set(f"格式语法错误或路径无效: {e}")
            self.folder_preview_var.set("格式错误")
            self.file_preview_var.set("格式错误")
            self.draft_preview_var.set("格式错误")

    # 监听格式变化
    def on_fmt_change(self, *args):
        self._update_name_preview()

    def select_output_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.output_dir_var.set(path)
            # 立即保存，增强记忆深度
            self._save_config_immediate()

    def _save_config_immediate(self):
        """立即保存当前 UI 配置到文件"""
        if self.suppress_save:
            return
        print(f"[DEBUG] Saving config to: {self.config_path}")
        if os.path.exists(os.path.dirname(self.config_path)):
            try:
                config_data = {}
                config_data["last_source_dir"] = self.to_portable_path(self.path_var.get().strip())
                config_data["last_output_dir"] = self.to_portable_path(self.output_dir_var.get().strip())
                config_data["jianying_exe_path"] = self.jy_path_var.get().strip()
                config_data["api_key"] = self.api_key_var.get().strip()
                config_data["base_url"] = self.base_url_var.get().strip()
                config_data["default_chat_model"] = self.model_var.get().strip()
                config_data["ai_prompt"] = self.prompt_text.get("1.0", "end-1c").strip()
                config_data["window_geometry"] = self.root.winfo_geometry()
                config_data["templates_root"] = self.to_portable_path(self.tpl_root_var.get().strip())
                config_data["name_format"] = self.name_fmt_var.get().strip()
                config_data["folder_format"] = self.folder_fmt_var.get().strip()
                config_data["draft_name_format"] = self.draft_name_fmt_var.get().strip() # 保存草稿命名格式
                config_data["is_batch_mode"] = self.batch_mode_var.get() # 记录批量模式开关
                config_data["last_batch_root"] = self.to_portable_path(self.batch_path_var.get().strip()) # 记录批量根目录
                
                # 保存所有选中的模板
                selected_tpls = [tpl for tpl, var in self.template_checkboxes.items() if var.get()]
                config_data["last_templates"] = selected_tpls
                if selected_tpls:
                    config_data["last_template"] = selected_tpls[0]
                
                config_data["templates_selections"] = self.templates_selections
                print(f"[DEBUG] Saving templates_selections: {self.templates_selections}")
                
                # 保存 Quicker 设置
                config_data["use_quicker"] = self.use_quicker_var.get()
                config_data["quicker_action_id"] = self.quicker_id_var.get().strip()
                
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    json.dump(config_data, f, indent=4)
                print(f"[SERVER LOG] Config saved successfully: {os.path.basename(self.config_path)}")
            except Exception as e:
                print(f"[ERROR] Save failed: {e}")

    def select_templates_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.tpl_root_var.set(path)
            self.templates_root = path
            self._refresh_templates()
            self._save_config_immediate()

    def _update_template_segments(self, target_tpl=None):
        """动态解析选中模板中的视频片段并展示复选框"""
        if not hasattr(self, 'tpl_inner_frame'): return
        
        # 如果没传具体的，看最后一个勾选的
        if not target_tpl:
            selected = [t for t, v in self.template_checkboxes.items() if v.get()]
            if selected: target_tpl = selected[-1]
            else: target_tpl = None

        # 更新配置记忆
        selected_tpls = [tpl for tpl, var in self.template_checkboxes.items() if var.get()]
        self.last_templates = selected_tpls
        self._save_config_immediate()

        if not target_tpl:
            for widget in self.tpl_inner_frame.winfo_children(): widget.destroy()
            tk.Label(self.tpl_inner_frame, text="请勾选或选择一个模板进行解析", fg="gray").pack(pady=10)
            return

        self.last_template = target_tpl # 记录当前正在配置的模板
        
        # 1. 清空旧的组件
        for widget in self.tpl_inner_frame.winfo_children():
            widget.destroy()
        self.placeholder_check_vars = {}
            
        tpl_path = os.path.join(self.tpl_root_var.get(), target_tpl)
        if not os.path.exists(tpl_path):
            tk.Label(self.tpl_inner_frame, text="工程路径不存在", fg="red").pack(pady=10)
            return

        try:
            # 引入分析引擎
            if script_dir not in sys.path: sys.path.insert(0, script_dir)
            from ai_batch_editor import AIVideoEditor
            
            segments = AIVideoEditor.get_template_info(tpl_path)
            if not segments:
                tk.Label(self.tpl_inner_frame, text="未能解析出有效的视频片段", fg="orange").pack(pady=10)
                return

            # 尝试获取该模板先前的勾选记忆
            prev_selections = self.templates_selections.get(target_tpl, None)

            for seg in segments:
                # 默认逻辑
                lname = seg['name'].lower()
                is_placeholder = True
                if any(x in lname for x in ["logo", "brand", "intro", "outro", "片尾", "固定"]):
                    is_placeholder = False
                
                # 如果有记忆，则优先使用记忆
                if prev_selections is not None:
                    is_placeholder = (seg['id'] in prev_selections)
                
                var = tk.BooleanVar(value=is_placeholder)
                cb = tk.Checkbutton(self.tpl_inner_frame, 
                                   text=f"[{seg['duration']}] {seg['name']}", 
                                   variable=var, font=self.label_font,
                                   command=self._auto_adjust_prompt_count)
                cb.pack(anchor="w", padx=5)
                # 记录段落标识，增加 source_duration记录以便准确计算总和
                self.placeholder_check_vars[seg['id']] = (seg['name'], var, seg['duration'], seg.get('source_duration', 0))
            
            self._auto_adjust_prompt_count()
            
        except Exception as e:
            self.log(f"   [!] 模板解析出错: {e}")
            tk.Label(self.tpl_inner_frame, text=f"解析失败: {str(e)}", fg="red").pack()

    def _auto_adjust_prompt_count(self):
        """根据勾选数量自动调整 AI 提示词"""
        # 收集当前所有选中的 ID
        selected_ids = [sid for sid, info in self.placeholder_check_vars.items() if info[1].get()]
        current_tpl = getattr(self, 'last_template', None)
        if current_tpl:
            self.templates_selections[current_tpl] = selected_ids
            self._save_config_immediate() # 实时记忆勾选状态

        selected_count = len(selected_ids)

        # 计算总时长 (使用素材原始时长，解决变速偏差)
        total_dur = 0.0
        for sid in selected_ids:
            # 取元组第4位记录的 source_duration (秒)
            try:
                total_dur += self.placeholder_check_vars[sid][3]
            except: pass
        
        self.current_total_source_dur = total_dur
        self.current_selected_count = selected_count

        # 更新系统提示词显示
        self._update_sys_prompt_display(total_dur)

        if selected_count > 0:
            current_prompt = self.prompt_text.get("1.0", "end-1c")
            # 1. 尝试正则替换数量: "挑选出 X 个" 或 "正好 X 个"
            new_prompt = re.sub(r"挑(选出)?\s*\d+\s*个", f"挑\\1 {selected_count} 个", current_prompt)
            new_prompt = re.sub(r"正好\s*\d+\s*个", f"正好 {selected_count} 个", new_prompt)
            
            # 2. 尝试正则替换总时长: "总时长约 X 秒" 或 "总计 X s"
            new_prompt = re.sub(r"总和约\s*\d+(\.\d+)?\s*秒", f"总和约 {round(total_dur, 1)} 秒", new_prompt)
            new_prompt = re.sub(r"总和约\s*\d+(\.\d+)?\s*s", f"总和约 {round(total_dur, 1)}s", new_prompt)

            if new_prompt != current_prompt:
                self.prompt_text.delete("1.0", "end")
                self.prompt_text.insert("1.0", new_prompt)

    def _update_sys_prompt_display(self, total_dur):
        """更新系统提示词界面的显示内容"""
        if not hasattr(self, 'sys_prompt_text'): return
        self.sys_prompt_text.configure(state="normal")
        self.sys_prompt_text.delete("1.0", "end")
        content = self.sys_constraints_template.format(total_duration=round(total_dur, 1))
        self.sys_prompt_text.insert("1.0", content)
        self.sys_prompt_text.configure(state="disabled")

    def on_close(self):
        """关闭窗口时的处理"""
        self._save_config_immediate()
        self.root.destroy()

    def select_jy_exe(self):
        path = filedialog.askopenfilename(filetypes=[("可执行文件", "*.exe"), ("所有文件", "*.*")])
        if path:
            self.jy_path_var.set(path)

    def start_thread(self):
        # 根据批量模式决定处理方式
        if self.batch_mode_var.get():
            # 批量模式
            root_path = self.batch_path_var.get().strip()
            if not root_path or not os.path.exists(root_path):
                messagebox.showwarning("提示", "请先选择有效的批量素材根目录！")
                return
            
            # 如果还没探测过，先探测
            self.log_area.configure(state="normal")
            self.log_area.delete(1.0, "end")
            self.log_area.configure(state="disabled")

        if self.is_running: return # Prevent multiple starts

        # 如果队列为空，且当前面板有配置，自动把当前的加进去
        if not self.task_queue:
            self.add_current_to_queue(silent=True)
            if not self.task_queue: return

        self.is_running = True
        self.start_btn.configure(state="disabled", bg="gray")
        self.add_queue_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        # ... (日志清理略)
        threading.Thread(target=self._main_logic_thread_entry, daemon=True).start()

    def _main_logic_thread_entry(self):
        """后台逻辑主入口：遍历任务队列"""
        try:
            if not self.task_queue:
                self.log("[-] 队列为空，无任务可执行。")
                return

            total_tasks = len(self.task_queue)
            for tidx, task in enumerate(self.task_queue):
                if not self.is_running: break
                
                self.log(f"\n{'#'*50}\n[💼] 正在执行任务 {tidx+1}/{total_tasks}: {task['name']}\n{'#'*50}")
                
                if task['mode'] == 'batch':
                    clients = self._discover_client_folders(task['path'])
                    if not clients:
                        self.log(f"[-] 任务 {task['name']} 终止: 未发现有效客户文件夹")
                    else:
                        # process_batch 的逻辑
                        for cidx, client_info in enumerate(clients):
                            if not self.is_running: break
                            self.log(f"\n📦 [{cidx+1}/{len(clients)}] 准备素材: {client_info['name']}")
                            self._process_single_client(client_info['path'], client_info['name'], task=task)
                else:
                    self._process_single_client(task['path'], task.get('client_name', "新客户"), task=task)

            self.log(f"\n[🏁] 全部 {total_tasks} 个队列任务已处理完毕。")
            
        except Exception as e:
            self.log(f"🔥 队列执行崩溃: {e}")
            traceback.print_exc()
        finally:
            self.is_running = False
            self.start_btn.configure(state="normal", bg="#27ae60")
            self.add_queue_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")
            self._discovered_clients = None
            # 任务跑完后可选：self.task_queue = [] 建议保留让用户手动清空

    # _export_consumer_worker 已移除，回归单行逻辑

    def _process_single_client(self, folder: str, client_name: str = None, task: dict = None):
        """
        处理单个客户 (执行层)。
        支持从 task 对象中读取独立配置，实现多配置串联。
        """
        # --- 1. 获取并准备参数 (优先从 task 读取，否则读 UI 变量) ---
        if task:
            new_model = task.get('model', self.model_var.get())
            new_prompt_template = task.get('prompt', self.prompt_text.get("1.0", "end-1c"))
            new_jy_path = task.get('jy_path', self.jy_path_var.get())
            out_root = task.get('out_root', self.output_dir_var.get())
            name_fmt = task.get('name_fmt', self.name_fmt_var.get())
            folder_fmt = task.get('folder_fmt', self.folder_fmt_var.get())
            draft_fmt = task.get('draft_fmt', self.draft_name_fmt_var.get())
            tpl_root = task.get('tpl_root', self.tpl_root_var.get())
            # 这里的 template_checkboxes 状态和 selections 是关键
            target_selections = task.get('templates_selections', self.templates_selections)
            # 获取该任务要跑的所有模板名
            selected_tpls = task.get('templates', [tpl for tpl, var in self.template_checkboxes.items() if var.get()])
            use_quicker = task.get('use_quicker', self.use_quicker_var.get())
            quicker_id = task.get('quicker_id', self.quicker_id_var.get())
        else:
            new_model = self.model_var.get().strip()
            new_prompt_template = self.prompt_text.get("1.0", "end-1c").strip()
            new_jy_path = self.jy_path_var.get().strip()
            out_root = self.output_dir_var.get().strip()
            name_fmt = self.name_fmt_var.get().strip()
            folder_fmt = self.folder_fmt_var.get().strip()
            draft_fmt = self.draft_name_fmt_var.get().strip()
            tpl_root = self.tpl_root_var.get().strip()
            target_selections = self.templates_selections
            selected_tpls = [tpl for tpl, var in self.template_checkboxes.items() if var.get()]
            use_quicker = self.use_quicker_var.get()
            quicker_id = self.quicker_id_var.get()

        from datetime import datetime
        now = datetime.now()
        
        # 将 stdout 重定向
        sys.stdout = Logger(self.log)
        
        from ai_batch_editor import AIVideoEditor
        
        # --- 智能识别客户名与额外信息 ---
        folder_base = os.path.basename(folder)
        info = self._parse_folder_info(folder_base)
        
        if not client_name or client_name == "新客户":
            client_name = info["name"] if info["name"] else "未知客户"

        # 设置日期目录
        try:
            # 修改解析顺序：先替换占位符，再执行 strftime。防止 strftime 破坏占位符。
            subfolder_name = folder_fmt.replace("{name}", client_name)
            subfolder_name = subfolder_name.replace("{orig_date}", info["date"] or "").replace("{duration}", info["duration"] or "").replace("{suffix}", info["suffix"] or "")
            subfolder_name = now.strftime(subfolder_name)
        except Exception as e:
            self.log(f" [!] 子目录格式解析异常: {e}")
            subfolder_name = f"{now.strftime('%Y%m%d')}-{client_name}"
            
        final_out_dir = os.path.join(out_root, subfolder_name)
        os.makedirs(final_out_dir, exist_ok=True)

        self.log(f"[*] 客户: {client_name}, 输出目录: {final_out_dir}")
        
        if not selected_tpls:
            self.log(" [!] 警告: 未选中任何模板，跳过该客户")
            return

        # 智能模板适配逻辑
        videos_in_folder = [f for f in os.listdir(folder) if f.lower().endswith(('.mp4', '.mov'))]
        video_count = len(videos_in_folder)
        
        if len(selected_tpls) > 1:
            self.log(f"[*] 智能适配模式... (素材数量: {video_count})")
            best_tpl = None
            min_diff = 999
            
            for tpl_name in selected_tpls:
                t_count = len(target_selections.get(tpl_name, []))
                diff = abs(video_count - t_count)
                if diff < min_diff:
                    min_diff = diff
                    best_tpl = tpl_name
            
            if best_tpl:
                self.log(f"[*] 智能匹配: '{best_tpl}'")
                selected_tpls = [best_tpl]

        # --- 2. 逻辑引擎准备 ---
        import exporter_core
        import uiautomation as uia
        if script_dir not in sys.path: sys.path.insert(0, script_dir)
        from ai_batch_editor import AIVideoEditor
        
        # 核心修复：后台线程必须初始化 COM 环境，且必须包裹住整个涉及 UI 操作的循环
        with uia.UIAutomationInitializerInThread():
            # 串行模式，直接初始化 Exporter
            exporter = exporter_core.Exporter(log_func=self.log, jianying_exe_path=new_jy_path)
            
            # 初始清理
            try:
                exporter.kill_jianying()
            except: pass

            # 预检
            if not any(f.lower().endswith(('.mp4', '.mov')) for f in os.listdir(folder)):
                raise ValueError(f"素材文件夹下未找到视频文件: {folder}")

            # --- 3. 循环处理模板 (单行串行逻辑) ---
            for idx, tpl_name in enumerate(selected_tpls):
                if not self.is_running:
                    break
                
                self.log(f"\n>>> 模板 {idx+1}/{len(selected_tpls)}: {tpl_name}")
                
                safe_tpl_name = re.sub(r'[^\w\u4e00-\u9fa5]', '_', tpl_name)
                
                # --- 生成草稿工程名称 ---
                draft_fmt = self.draft_name_fmt_var.get().strip()
                try:
                    # 处理日期变量与客户名、模板名
                    project_name = draft_fmt.replace("{name}", client_name).replace("{template}", safe_tpl_name)
                    project_name = project_name.replace("{orig_date}", info["date"] or "").replace("{duration}", info["duration"] or "").replace("{suffix}", info["suffix"] or "")
                    project_name = now.strftime(project_name)
                except Exception as e:
                    self.log(f" [!] 草稿命名格式错误: {e}, 使用默认格式")
                    project_name = f"AI_{client_name}_{safe_tpl_name}"
                
                # 记录原始导出文件名格式，用于后期处理
                try:
                    raw_filename = name_fmt.replace("{name}", client_name)
                    raw_filename = raw_filename.replace("{orig_date}", info["date"] or "").replace("{duration}", info["duration"] or "").replace("{suffix}", info["suffix"] or "")
                    raw_filename = now.strftime(raw_filename)
                except Exception as e:
                    self.log(f" [!] 文件名格式错误: {e}")
                    raw_filename = f"Video_{client_name}"

                if len(selected_tpls) > 1:
                    base, ext = os.path.splitext(raw_filename)
                    if not ext: ext = ".mp4"
                    out_filename = f"{base}_{safe_tpl_name}{ext}"
                else:
                    out_filename = raw_filename if raw_filename.lower().endswith(".mp4") else raw_filename + ".mp4"
                
                final_dest_file = os.path.join(final_out_dir, out_filename)
                self.log(f"   [目标路径]: {os.path.abspath(final_dest_file)}")

                # 获取配置片元
                target_sections_ids = target_selections.get(tpl_name, [])
                tpl_path = os.path.join(tpl_root, tpl_name)
                all_segs = AIVideoEditor.get_template_info(tpl_path)
                target_sections = [s['name'] for s in all_segs if s['id'] in target_sections_ids]
                target_count = len(target_sections)

                # --- 核心改进：预检素材数量 ---
                videos_in_folder = [f for f in os.listdir(folder) if f.lower().endswith(('.mp4', '.mov'))]
                video_count = len(videos_in_folder)
                if video_count < target_count:
                    self.log(f"   ⚠️ [警告] 客户素材总数({video_count})少于模版占位符({target_count})，已记录到补拍报告。")
                    self.add_client_material_shortage_warning(client_name, folder, project_name, video_count, target_count)

                # 计算该模板对应的素材总时长 (精确值并取整)
                current_total_dur = 0
                for seg in all_segs:
                    if seg['id'] in target_sections_ids:
                        current_total_dur += seg.get('source_duration', 0)
                current_total_dur = round(current_total_dur, 1)

                # 运行剪辑
                editor = AIVideoEditor(project_name, 
                                      client_name=client_name, 
                                      template_name=tpl_name, 
                                      template_root=tpl_root,
                                      model=new_model)
                
                if not self.is_running: break
                
                ai_results = editor.run(folder, 
                                       custom_prompt=new_prompt_template, 
                                       target_sections=target_sections,
                                       total_duration=current_total_dur)
                
                if not ai_results:
                    self.log(f" [!] 模板 {tpl_name} 生产失败，跳过导出")
                    continue

                # 更新AI选片展示
                self.ai_res_area.configure(state="normal")
                self.ai_res_area.insert("end", f"--- {client_name} / {tpl_name} ---\n")
                
                current_segments = ai_results.get("segments", [])
                for i, res in enumerate(current_segments):
                    reason = res.get('reason', '无理由说明')
                    desc = res.get('description', '无内容描述')
                    self.ai_res_area.insert("end", f" {i+1}: {res.get('file_name')} ({res.get('start')})\n")
                    self.ai_res_area.insert("end", f"    📝 内容: {desc}\n")
                    self.ai_res_area.insert("end", f"    💡 理由: {reason}\n")
                
                self.ai_res_area.insert("end", "\n")
                self.ai_res_area.see("end")
                self.ai_res_area.configure(state="disabled")
                
                # 检查并添加补拍警告到报告 Tab
                reshoot_warnings = ai_results.get("reshoot_warnings", [])
                if reshoot_warnings:
                    self.add_reshoot_warning(client_name, folder, project_name, reshoot_warnings)
                    self.log(f"   ⚠️ 发现 {len(reshoot_warnings)} 个素材需要补拍，已记录到【补拍报告】")

                # --- 4. 立即执行导出 (串行逻辑) ---
                if not self.is_running: break
                self.log(f"[*] AI 分析完成，开始 UI 自动化导出: {project_name}")
                try:
                    if use_quicker:
                        self.log(f"[*] 🚀 正在调用 Quicker 动作接手导出...")
                        success = self._run_export_via_quicker(quicker_id, project_name, final_dest_file)
                        if success:
                            self.log(f"✅ Quicker 交付成功! 文件已保存至:\n   {os.path.abspath(final_dest_file)}")
                        else:
                            self.log(f"❌ Quicker 导出失败或超时。")
                    else:
                        captured_path = exporter.run_export(project_name)
                        if captured_path and os.path.exists(captured_path):
                            os.makedirs(os.path.dirname(final_dest_file), exist_ok=True)
                            if os.path.exists(final_dest_file): os.remove(final_dest_file)
                            shutil.move(captured_path, final_dest_file)
                            self.log(f"✅ 交付成功! 文件已保存至:\n   {os.path.abspath(final_dest_file)}")
                        else:
                            self.log(f"❌ 导出异常: 剪映导出完成后未能找到文件。")
                except Exception as ex:
                    self.log(f"⚠️ 导出出错: {ex}")
                finally:
                    # 每个任务完结后杀掉剪映，防止残留或干扰下一个项目
                    try: 
                        if not use_quicker: # 如果用了 quicker，尽量不要暴力杀，或者由 quicker 处理
                            exporter.kill_jianying()
                    except: pass

    def _run_export_via_quicker(self, action_id, draft_name, save_path, timeout=900):
        """
        通过 Quicker 外部动作接手导出逻辑
        参数格式: 草稿名|保存路径
        """
        import subprocess
        quicker_exe = self.quicker_exe_path
        if not os.path.exists(quicker_exe):
            self.log(f"❌ 找不到 QuickerStarter.exe，请检查路径: {quicker_exe}")
            return False
            
        # 统一路径格式为正斜杠，避免 Quicker 在解析参数时将反斜杠误认为转义符
        safe_save_path = save_path.replace("\\", "/")
        arg_str = f"{draft_name}|{safe_save_path}"
        # 修正命令格式: runaction:ID?Args
        cmd_arg = f"runaction:{action_id}?{arg_str}"
        
        try:
            self.log(f"[*] 启动 Quicker 动作: {action_id}")
            self.log(f"[*] 传递指令: {cmd_arg}")
            subprocess.Popen([quicker_exe, cmd_arg])
            
            # 监控文件生成
            start_time = time.time()
            self.log("[*] 等待 Quicker 导出结果 (监控目标文件生成)...")
            
            while time.time() - start_time < timeout:
                if not self.is_running: return False
                
                if os.path.exists(save_path):
                    # 检查文件大小是否还在增长 (判定是否导出结束)
                    last_size = os.path.getsize(save_path)
                    time.sleep(3)
                    if os.path.exists(save_path) and os.path.getsize(save_path) == last_size and last_size > 0:
                        self.log(f"✅ 检测到文件生成且大小趋于稳定，导出完成。")
                        return True
                
                time.sleep(5)
            
            self.log(f"❌ 等待 Quicker 导出超时 ({timeout}s)")
            return False
        except Exception as e:
            self.log(f"❌ 调用 Quicker 失败: {e}")
            return False

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
    root.mainloop()
