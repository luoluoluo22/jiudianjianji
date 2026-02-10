import os
import sys

# 1. 环境初始化
current_dir = os.path.dirname(os.path.abspath(__file__))
skill_root = os.path.abspath(r"f:\Desktop\kaifa\jianying-editor-skill\.agent\skills\jianying-editor")
sys.path.insert(0, os.path.join(skill_root, "scripts"))
sys.path.insert(0, os.path.join(skill_root, "references"))

try:
    import pyJianYingDraft as draft
    from pyJianYingDraft import TransitionType
    
    print("=== TransitionType Enum ===")
    for name, member in TransitionType.__members__.items():
        print(f"{name}: {member.value}")
except Exception as e:
    print(f"Error: {e}")
