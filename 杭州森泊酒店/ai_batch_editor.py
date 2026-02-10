import os
import sys
import json
import shutil
import re
import time
from pathlib import Path

# --- 🚀 路径自适应初始化 ---
if getattr(sys, 'frozen', False):
    base_dir = sys._MEIPASS
else:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 动态定位 Skill 路径
SKILL_JY = os.path.join(base_dir, ".agent", "skills", "jianying-editor")
SKILL_API = os.path.join(base_dir, ".agent", "skills", "antigravity-api-skill")

# 注入 Python 搜索路径
sys.path.append(os.path.join(SKILL_JY, "scripts"))
sys.path.append(os.path.join(SKILL_API, "libs"))

try:
    from jy_wrapper import JyProject, get_default_drafts_root
    from api_client import AntigravityClient
    import pyJianYingDraft as draft
except ImportError as e:
    print(f"[-] 依赖库加载失败: {e}")

def get_video_duration(file_path):
    """获取视频物理时长 (微秒)"""
    try:
        mat = draft.VideoMaterial(file_path)
        return mat.duration
    except: return 0

def fix_json_pre_load(file_path, local_root, replacements, new_display_name):
    """
    终极预修复：彻底重定向任何形式的绝对路径，并强制重连。
    特别针对音频加入了云端 ID 清洗逻辑。
    """
    if not os.path.exists(file_path): return
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 记录 BGM 的素材 ID
    bgm_material_ids = []

    def walk_and_fix(obj):
        if isinstance(obj, dict):
            # 1. 移除之前的硬编码 BGM 处理，不再强制修改 bgm.mp3 路径
            pass

            for k, v in list(obj.items()):
                # 2. 拦截所有形式的绝对路径
                if k.lower() in ['path', 'file_path'] and isinstance(v, str) and (":" in v or "Desktop" in v or "##_material_" in v):
                    filename = os.path.basename(v) if "##" not in v else v
                    found_new_path = None
                    for old_name, new_path in replacements.items():
                        if old_name.lower() in filename.lower() or filename.lower() in old_name.lower():
                            found_new_path = new_path.replace("/", "\\")
                            break

                    if found_new_path:
                        obj[k] = found_new_path
                        if "local_material_id" in obj: obj["local_material_id"] = ""
                        if "material_name" in obj: obj["material_name"] = os.path.basename(found_new_path)
                    # 如果没找到匹配（非占位符素材），则保持原路径不变，不要暴力拼接 local_root

                # 3. 暴力更名
                elif isinstance(v, str) and "高梦雅" in v:
                    obj[k] = v.replace("高梦雅", new_display_name)

                walk_and_fix(v)
        elif isinstance(obj, list):
            for item in obj: walk_and_fix(item)

    walk_and_fix(data)
    if "draft_fold_path" in data:
        data["draft_fold_path"] = data["draft_fold_path"].replace("高梦雅", new_display_name)

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    return bgm_material_ids

class AIVideoEditor:
    def __init__(self, project_name, client_name="陈桑桑", template_name="杭州开元森泊20S", template_root=None, model="gemini-3-pro"):
        self.client = AntigravityClient()
        self.model = model
        self.project_name = project_name
        self.client_name = client_name
        # 允许动态传入模版目录
        if template_root and os.path.exists(template_root):
            self.local_assets_root = template_root
        else:
            self.local_assets_root = os.path.join(base_dir, "杭州森泊酒店", "杭州森泊工程模版")
            
        self.template_dir = os.path.join(self.local_assets_root, template_name)
        self.drafts_root = get_default_drafts_root()
        self.dest_path = os.path.join(self.drafts_root, project_name)

    @staticmethod
    def get_template_info(template_dir):
        """解析模板，提取可替换的视频片段信息 (支持复合片段递归)"""
        content_path = os.path.join(template_dir, "draft_content.json")
        if not os.path.exists(content_path):
            return []
            
        try:
            with open(content_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            all_segments = []
            
            def scan_draft_data(draft_data, parent_name=""):
                """递归扫描草稿数据中的视频片段"""
                # 1. 建立当前层级的素材库映射
                materials = {}
                material_list = draft_data.get("materials", {})
                video_mats = material_list.get("videos", []) if isinstance(material_list, dict) else []
                for m in video_mats:
                    name = m.get("material_name") or os.path.basename(m.get("path", "Unknown"))
                    materials[m["id"]] = name
                
                # 2. 扫描轨道
                tracks = draft_data.get("tracks", [])
                for track in tracks:
                    if track.get("type") == "video" or track.get("track_type") == 0:
                        for seg in track.get("segments", []):
                            m_id = seg.get("material_id")
                            if m_id in materials:
                                target_dur_us = seg.get("target_timerange", {}).get("duration", 0)
                                source_dur_us = seg.get("source_timerange", {}).get("duration", target_dur_us)
                                if target_dur_us < 500000: continue
                                
                                speed_ratio = source_dur_us / target_dur_us if target_dur_us > 0 else 1.0
                                
                                # 将层级信息加入名称中，方便识别 (可选)
                                display_name = materials[m_id]
                                
                                all_segments.append({
                                    "id": seg["id"],
                                    "material_id": m_id,
                                    "name": display_name,
                                    "duration": f"{target_dur_us/1000000:.1f}s",
                                    "source_duration": source_dur_us / 1000000,
                                    "target_duration": target_dur_us / 1000000,
                                    "speed_ratio": round(speed_ratio, 2),
                                    "start_time": seg.get("target_timerange", {}).get("start", 0)
                                })
                
                # 3. 递归扫描复合片段 (materials -> drafts)
                draft_materials = material_list.get("drafts", []) if isinstance(material_list, dict) else []
                for d_mat in draft_materials:
                    nested_draft = d_mat.get("draft")
                    if nested_draft:
                        scan_draft_data(nested_draft, parent_name=d_mat.get("name", "复合片段"))

            # 执行递归扫描
            scan_draft_data(data)
            
            # 按时间轴起始点排序 (顶层排序)
            all_segments.sort(key=lambda x: x["start_time"])
            return all_segments
            
        except Exception as e:
            print(f"[-] 解析模板失败: {e}")
            import traceback
            traceback.print_exc()
            return []

    @staticmethod
    def parse_time_to_seconds(time_val):
        """解析多种时间格式为秒 (float)"""
        if not time_val: return 0.0
        ts = str(time_val).lower().strip()
        # 处理 00:03 格式
        if ":" in ts:
            parts = ts.split(":")
            if len(parts) == 2: # MM:SS
                return float(parts[0]) * 60 + float(parts[1])
            elif len(parts) == 3: # HH:MM:SS
                return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
        # 处理 5.2s 或 5.2 格式
        return float(ts.replace("s", ""))

    def analyze_assets(self, video_paths, custom_prompt=None, target_count=4, total_duration=10.0):
        """联合 AI 分析，根据需要替换的段落数请求 AI"""
        total_duration = round(float(total_duration), 1)
        print(f"[*] 正在执行多素材联合视觉分析 (模型: {self.model}, 目标段落数: {target_count}, 目标素材总长: {total_duration}s)...")
        file_map = {os.path.basename(p): p for p in video_paths}
        
        # 获取每个视频的实际时长 (使用 ffprobe 或从文件元数据)
        video_durations = {}
        for name, path in file_map.items():
            try:
                # 优先寻找打包内的 ffprobe
                ffprobe_path = 'ffprobe'
                if getattr(sys, 'frozen', False):
                    local_ffprobe = os.path.join(sys._MEIPASS, 'ffprobe.exe')
                    if os.path.exists(local_ffprobe): ffprobe_path = local_ffprobe

                import subprocess
                result = subprocess.run(
                    [ffprobe_path, '-v', 'quiet', '-show_entries', 'format=duration', '-of', 'csv=p=0', path],
                    capture_output=True, text=True, timeout=5
                )
                dur = float(result.stdout.strip()) if result.stdout.strip() else 0
                video_durations[name.lower()] = round(dur, 2)
            except Exception as e:
                print(f"   [!] 获取素材 {name} 时长失败: {e}")
                video_durations[name.lower()] = 0
        
        # 保存到实例变量供 run 方法后续使用
        self.video_durations = video_durations
        
        # 使用素材列表增强提示词 - 包含时长信息 (注意此处 lookup 也需转小写)
        if any(video_durations.values()):
            indexed_list = "\n".join([f"视频 #{i+1}: {name} (总时长: {video_durations.get(name.lower(), '未知')}秒)" for i, name in enumerate(file_map.keys())])
            duration_hint = "请注意每个视频的总时长，start + duration 不能超过该视频的总时长。"
        else:
            indexed_list = "\n".join([f"视频 #{i+1}: {name}" for i, name in enumerate(file_map.keys())])
            duration_hint = ""
        
        # 构造默认增强提示词 - 强调差异化时长分配
        final_default_prompt = (
            f"我为你按顺序上传了以下视频素材：\n{indexed_list}\n\n"
            f"请从这些视频中挑选出 {target_count} 个不同的精彩瞬间。\n"
            "【强制要求】：\n"
            "1. 在 file_name 字段中填入原始文件名（如 C2700.MP4）。\n"
            f"2. 段落数量必须严格等于 {target_count}。\n"
            "3. 增加 duration 字段，表示该片段建议使用的时长（秒）。\n"
            "4. 【重要】根据每个片段的精彩程度和内容丰富度分配不同的时长：\n"
            "   - 动作丰富、内容精彩的片段可以长一些 (3-4秒)\n"
            "   - 简单的片段可以短一些 (1.5-2秒)\n"
            "   - 不要均分！根据实际内容灵活分配\n"
            f"   - 所有片段 duration 总和约为 {total_duration} 秒\n"
            f"5. {duration_hint}\n"
            "6. 在 segments 中，为每个片段提供：\n"
            "   - reason: 挑选该片段的理由\n"
            "   - description: 该视频素材内容的描述\n"
            "   - duration: 建议使用时长（如 \"2.5s\"）\n"
            "直接输出 JSON: {\"segments\": [{\"file_name\": \"...\", \"start\": \"...\", \"duration\": \"...\", \"reason\": \"...\", \"description\": \"...\"}, ...]}"
        )
        
        # 2. 如果提供了自定义提示词（来自 GUI），也要注入素材信息
        if custom_prompt:
            prompt = custom_prompt
            if "{video_list}" in prompt:
                prompt = prompt.replace("{video_list}", indexed_list)
            elif "视频 #" not in prompt:
                prompt = f"素材列表如下：\n{indexed_list}\n\n" + prompt
            
            # 强制追加系统约束，确保格式正确
            prompt += (
                f"\n\n【系统格式化强制要求 (优先级最高)】:\n"
                f"1. 必须从中挑选出 {target_count} 个精彩片段。\n"
                f"2. file_name 必须是原始文件名。\n"
                f"3. 必须分配 duration，且所有片段 duration 的数学总和必须精确等于 {total_duration} 秒。\n"
                f"4. 严格校验：start + duration 必须小于该视频总时长减去 0.5 秒 (留出缓冲)。\n"
                f"5. 直接输出 JSON: {{\"segments\": [{{\"file_name\": \"...\", \"start\": \"...\", \"duration\": \"...\", \"reason\": \"...\", \"description\": \"...\"}}, ...]}}"
            )
        else:
            prompt = final_default_prompt

        print(f"[*] AI 提示词 (Prompt):\n{'-'*20}\n{prompt}\n{'-'*20}")
        try:
            response = self.client.chat_completion([{"role": "user", "content": prompt}], model=self.model, file_paths=video_paths)
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
            
            clean_content = content.strip().strip("```json").strip("```").strip()
            print(f"[*] AI 输入素材列表: {list(file_map.values())}")
            print(f"[*] AI 原始分析结果: {clean_content}")
            
            ai_data = json.loads(clean_content)
            results = ai_data.get("segments", []) if isinstance(ai_data, dict) else ai_data
            
            if not isinstance(results, list):
                raise ValueError("AI 返回格式非预期 JSON 结构")
            
            # 1. 预解析时长并转换为 float
            for res in results:
                res["duration"] = self.parse_time_to_seconds(res.get("duration", "0"))
                res["start"] = self.parse_time_to_seconds(res.get("start", "0"))

            # 2. 补齐数量 (如果 AI 少给了)
            while len(results) < target_count:
                results.append({"file_name": os.path.basename(video_paths[0]), "start": 0.0, "duration": 0.0, "reason": "补齐段落"})
            
            # 3. 动态时长调整逻辑 (确保数学总和精确等于目标 total_duration)
            sum_proposed = sum(r.get("duration", 0) for r in results[:target_count])
            diff = total_duration - sum_proposed

            if abs(diff) > 0.01:
                print(f"[*] AI 返回总时长 ({sum_proposed:.2f}s) 与目标 ({total_duration:.2f}s) 不符，正在动态调整 (差异: {diff:+.2f}s)...")
                if diff > 0:
                    # 时长不够：从后往前补 (用户要求：从后往前多截取一点)
                    remaining_to_add = diff
                    for res in reversed(results[:target_count]):
                        if remaining_to_add <= 0: break
                        fname = str(res.get("file_name", "")).lower()
                        # 获取该视频的总时长
                        total_dur = video_durations.get(fname, 999.0)
                        
                        # 计算当前能额外增加的最大值 (满足 0.5s 缓冲)
                        max_can_add = total_dur - 0.5 - (res["start"] + res["duration"])
                        add_this = min(remaining_to_add, max(0, max_can_add))
                        
                        if add_this > 0:
                            res["duration"] = round(res["duration"] + add_this, 2)
                            remaining_to_add -= add_this
                            print(f"   - 段落补时: {fname} 增加了 {add_this:.2f}s")
                    
                    # 如果所有素材都补满了还没够，强行加在最后一段（会触发后续的补拍提醒）
                    if remaining_to_add > 0.01:
                        results[target_count-1]["duration"] = round(results[target_count-1]["duration"] + remaining_to_add, 2)
                        print(f"   - [!] 素材物理时长已达上限，强制补入最后一段: {remaining_to_add:.2f}s (用于对齐模版)")
                else:
                    # 时长多了：平均扣减 (用户要求：平均每段素材少一点)
                    reduction = abs(diff) / target_count
                    for res in results[:target_count]:
                        actual_red = min(reduction, res["duration"] - 0.1) if res["duration"] > 0.1 else 0
                        res["duration"] = round(res["duration"] - actual_red, 2)
                    
                    # 残差补偿给第一段（确保最终和完全等于目标）
                    current_sum = sum(r["duration"] for r in results[:target_count])
                    residual = total_duration - current_sum
                    results[0]["duration"] = round(results[0]["duration"] + residual, 2)

            # 4. 建立有序列表用于索引匹配
            ordered_paths = video_paths 
            
            print("[*] AI 选片路径调试信息:")
            for i, res in enumerate(results):
                if i >= target_count: break # 截断多出的结果
                ai_filename = str(res.get("file_name", "")).lower()
                matched_path = None
                
                # 1. 尝试全词匹配
                for fname, fpath in file_map.items():
                    if ai_filename in fname.lower() or fname.lower() in ai_filename:
                        matched_path = fpath
                        break
                
                # 2. 索引匹配降级
                if not matched_path:
                    idx_match = re.search(r'(\d+)', ai_filename)
                    if idx_match:
                        idx = int(idx_match.group(1))
                        if "input_file" in ai_filename or "item" in ai_filename: 
                            if 0 <= idx < len(ordered_paths): matched_path = ordered_paths[idx]
                        else:
                            if 1 <= idx <= len(ordered_paths): matched_path = ordered_paths[idx-1]
                            elif 0 <= idx < len(ordered_paths): matched_path = ordered_paths[idx]
                
                res["path"] = matched_path or video_paths[0]
                print(f"    - 段落 {i+1} [AI标记: {ai_filename}]: 最终映射 -> {res['path']}")
                
            # 构造结果字典返回
            final_segments = results[:target_count]
            return {
                "segments": final_segments
            }
        except Exception as e:
            print(f"   [!] AI 分析失败或解析报错: {e}")
            # 兜底：循环选取素材
            fallback_segs = [{"path": video_paths[i % len(video_paths)], "start": "0s", "file_name": os.path.basename(video_paths[i % len(video_paths)]), "reason": "AI 分析失败", "description": "自动轮询素材兜底"} for i in range(target_count)]
            return {
                "segments": fallback_segs
            }

    @staticmethod
    def _apply_timing_recursive(draft_data, ai_clip_map, video_durations, reshoot_warnings):
        """
        递归应用裁剪并自动对齐（底层 JSON 字典操作，穿透复合片段）
        """
        # 1. 建立素材库映射
        m_list = draft_data.get("materials", {})
        all_mats = {}
        # 视频素材通常在 materials/videos
        videos = m_list.get("videos", []) if isinstance(m_list, dict) else []
        for m in videos:
            m_id = m["id"]
            m_name = (m.get("material_name") or os.path.basename(m.get("path", ""))).lower()
            m_dur = m.get("duration", 0) / 1000000
            all_mats[m_id] = {"name": m_name, "total_duration": m_dur}
        
        # 2. 对当前层轨道进行处理
        matched_count = 0
        tracks = draft_data.get("tracks", [])
        
        # 找到主视频轨道用于对齐 (通常是 track_type 为 0 的第一条)
        main_track = None
        for track in tracks:
            if track.get("type") == "video" or track.get("track_type") == 0:
                main_track = track
                break
        
        if main_track:
            time_shift_map = {}
            segments = main_track.get("segments", [])
            # 必须按时间轴顺序处理以进行对齐
            segments.sort(key=lambda s: s["target_timerange"]["start"])
            
            curr_pos = segments[0]["target_timerange"]["start"] if segments else 0
            for seg in segments:
                old_start = seg["target_timerange"]["start"]
                m_id = seg.get("material_id")
                m_info = all_mats.get(m_id)
                
                # 情况 A: 匹配到 AI 选片建议
                if m_info and m_info["name"] in ai_clip_map:
                    clip = ai_clip_map[m_info["name"]]
                    start_s = clip["start"]
                    dur_s = clip["duration"]
                    
                    total_s = video_durations.get(m_info["name"], m_info["total_duration"])
                    
                    # 校验起始点
                    actual_start_s = min(start_s, max(0, total_s - 0.1)) if total_s > 0 else start_s
                    seg["source_timerange"]["start"] = int(actual_start_s * 1000000)
                    
                    if dur_s and dur_s > 0:
                        # 保持原始变速比 (Source Duration / Target Duration)
                        old_src_dur = seg["source_timerange"]["duration"]
                        old_tgt_dur = seg["target_timerange"]["duration"]
                        speed_ratio = old_src_dur / old_tgt_dur if old_tgt_dur > 0 else 1.0
                        
                        avail = total_s - actual_start_s
                        actual_dur_s = min(dur_s, avail) if avail > 0 else dur_s
                        
                        if dur_s > avail + 0.01 and avail > 0:
                            reshoot_warnings.append({
                                "file": m_info["name"], "requested": dur_s, "available": round(avail, 1),
                                "shortage": round(dur_s - avail, 1), "start": actual_start_s, "total": round(total_s, 1)
                            })
                        
                        new_src_us = int(actual_dur_s * 1000000)
                        seg["source_timerange"]["duration"] = new_src_us
                        seg["target_timerange"]["duration"] = int(new_src_us / speed_ratio) if speed_ratio > 0 else new_src_us
                    
                    matched_count += 1
                
                # 应用对齐并计算下一个起始点
                time_shift_map[old_start] = curr_pos
                seg["target_timerange"]["start"] = curr_pos
                curr_pos += seg["target_timerange"]["duration"]
            
            # 对齐其它非主轨道 (音频、文字、特效等)
            for track in tracks:
                if track == main_track: continue
                # 注意：这里我们跳过嵌套草稿本身作为素材的轨道对齐，因为它们的内部已经处理了
                for seg in track.get("segments", []):
                    old_s = seg["target_timerange"]["start"]
                    if old_s in time_shift_map:
                        seg["target_timerange"]["start"] = time_shift_map[old_s]
                    else:
                        # 按最近锚点平移
                        past_anchors = [p for p in time_shift_map.keys() if p <= old_s]
                        if past_anchors:
                            anchor = max(past_anchors)
                            offset = time_shift_map[anchor] - anchor
                            seg["target_timerange"]["start"] += offset
                            
        # 3. 递归处理复合片段 (Nested Drafts)
        nested_drafts = m_list.get("drafts", []) if isinstance(m_list, dict) else []
        for d_mat in nested_drafts:
            if d_mat.get("draft"):
                matched_count += AIVideoEditor._apply_timing_recursive(d_mat["draft"], ai_clip_map, video_durations, reshoot_warnings)
                
        return matched_count

    def run(self, input_folder, custom_prompt=None, target_sections=None, total_duration=10.0):
        """运行生产流程"""
        input_folder = os.path.abspath(input_folder)
        videos = [os.path.join(input_folder, f) for f in os.listdir(input_folder) if f.lower().endswith(('.mp4', '.mov'))]
        videos.sort()
        if not videos: return []

        placeholder_names = target_sections or ["PXMX0789.MP4", "PXMX0790.MP4", "PXMX0791.MP4", "PXMX0792.MP4"]
        target_count = len(placeholder_names)

        # 1. 运行 AI 分析
        ai_data = self.analyze_assets(videos, custom_prompt=custom_prompt, target_count=target_count, total_duration=total_duration)
        actual_segments = ai_data.get("segments", [])

        print(f"[*] 1. 克隆品牌模板...")
        src_path = os.path.abspath(self.template_dir)
        dst_path = os.path.abspath(self.dest_path)
        if not os.path.exists(src_path): raise FileNotFoundError(f"找不到源模板目录: {src_path}")
        
        if src_path.lower() != dst_path.lower():
            if os.path.exists(dst_path): shutil.rmtree(dst_path, ignore_errors=True)
            shutil.copytree(src_path, dst_path)
        
        # 2. 建立 占位符 -> 本地素材 的重定向映射
        repl_map = {}
        for i, old_name in enumerate(placeholder_names):
            if i < len(actual_segments):
                repl_map[old_name] = actual_segments[i]["path"]

        print(f"[*] 2. 暴力执行路径重定向与 JSON 预处理...")
        bgm_ids = []
        for f_name in ["draft_content.json", "draft_meta_info.json", "draft_virtual_store.json"]:
            ids = fix_json_pre_load(os.path.join(self.dest_path, f_name), self.local_assets_root, repl_map, self.client_name)
            if f_name == "draft_content.json": bgm_ids = ids

        # 3. 核心：递归应用 AI 裁剪点 (直接在 JSON 文件中穿透复合片段)
        content_json_path = os.path.join(self.dest_path, "draft_content.json")
        with open(content_json_path, 'r', encoding='utf-8') as f:
            project_data = json.load(f)
            
        # 建立 AI 文件名 -> (start, duration) 的映射
        ai_clip_map = {}
        for seg_data in actual_segments:
            fname = (seg_data.get("file_name") or "").lower()
            start_s = self.parse_time_to_seconds(seg_data.get("start") or "0")
            dur_s = self.parse_time_to_seconds(seg_data.get("duration")) if seg_data.get("duration") else None
            ai_clip_map[fname] = {"start": start_s, "duration": dur_s}
        
        print(f"[*] AI 裁剪映射表: {ai_clip_map}")
        
        reshoot_warnings = []
        matched_count = self._apply_timing_recursive(project_data, ai_clip_map, self.video_durations, reshoot_warnings)
        
        # 写回 JSON 文件
        with open(content_json_path, 'w', encoding='utf-8') as f:
            json.dump(project_data, f, ensure_ascii=False)

        print(f"[*] 3. 加载项目并应用最终固化 (命中 {matched_count} 个段落)...")
        p = JyProject(self.project_name, drafts_root=self.drafts_root, overwrite=False)
        p.save()
        
        # 报告补拍警告
        if reshoot_warnings:
            print(f"\n⚠️ === 素材时长不足报告 (需补拍) ===")
            for warn in reshoot_warnings:
                print(f"   📹 {warn['file']}: 需要{warn['requested']}s, 实际可用{warn['available']}s (差{warn['shortage']}s)")
            ai_data["reshoot_warnings"] = reshoot_warnings
        
        print(f"\n✅ 自动化生产流程执行完毕。")
        return ai_data

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", nargs="?")
    args = parser.parse_args()
    input_folder = args.folder or r"F:\Desktop\kaifa\jianying-editor-skill\杭州森泊酒店\杭州开元森泊素材\0128\阿琪5单5条\20260128陈桑桑20s"
    folder_name = os.path.basename(input_folder)
    name_match = re.search(r'[\u4e00-\u9fa5]{2,3}', folder_name)
    client_name = name_match.group(0) if name_match else "新客户"
    project_name = f"AI生产-{client_name}-交付版"
    AIVideoEditor(project_name, client_name=client_name).run(input_folder)
