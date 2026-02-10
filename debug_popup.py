import uiautomation as uia

def dump_popup():
    win = uia.WindowControl(searchDepth=1, Name='环境检测')
    if not win.Exists(0):
        print("Popup '环境检测' not found.")
        return

    print(f"Dumping UI for: {win.Name}")
    for c, d in uia.WalkControl(win, maxDepth=8):
        name = c.Name
        desc = c.GetPropertyValue(30159)
        c_type = c.ControlTypeName
        if name or desc:
            print(f"{'  '*d} - Name: [{name}] | Desc: [{desc}] | Type: {c_type}")

if __name__ == '__main__':
    dump_popup()
