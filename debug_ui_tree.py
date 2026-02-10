import uiautomation as uia
import time

def deep_inspect_relink_window():
    print("[*] 正在执行无死角 UI 树扫描（深度 6）...")
    win = uia.WindowControl(searchDepth=1, Name="链接媒体")
    if not win.Exists(0):
        win = uia.WindowControl(searchDepth=1, ClassName="RelinkMediaView_QMLTYPE_1116")
    
    if not win.Exists(0):
        print("[-] 还是找不到窗口")
        return

    print(f"[+] 找到窗口: {win.Name}")
    
    def dump_children(parent, depth=0):
        if depth > 5: return
        for child in parent.GetChildren():
            suffix = f" (Name: '{child.Name}')" if child.Name else " (NoName)"
            print("  " * depth + f"- [{child.ControlTypeName}]{suffix} [Class: {child.ClassName}]")
            dump_children(child, depth + 1)

    dump_children(win)

if __name__ == "__main__":
    deep_inspect_relink_window()
