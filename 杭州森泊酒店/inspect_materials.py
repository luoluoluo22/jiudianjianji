import os
import sys

# 1. 环境初始化
current_dir = os.path.dirname(os.path.abspath(__file__))
skill_root = os.path.abspath(r"f:\Desktop\kaifa\jianying-editor-skill\.agent\skills\jianying-editor")
sys.path.insert(0, os.path.join(skill_root, "scripts"))
sys.path.insert(0, os.path.join(skill_root, "references"))

from jy_wrapper import JyProject

TEMPLATE_NAME = "杭州开元森泊20S"
project = JyProject(TEMPLATE_NAME, overwrite=False, drafts_root=r"F:\Desktop\杭州森泊酒店\杭州森泊工程模版")

print(f"Materials object type: {type(project.script.materials)}")
print(f"Attributes of materials: {dir(project.script.materials)}")

vids = project.script.materials.videos
print(f"Number of videos in materials: {len(vids)}")
for i, v in enumerate(vids):
    print(f"Video {i}: name={getattr(v, 'material_name', 'N/A')}, path={getattr(v, 'path', 'N/A')}")
