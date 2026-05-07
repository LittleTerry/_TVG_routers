import os
import importlib
from pathlib import Path

# 获取当前目录
current_dir = Path(__file__).parent

# 自动导入所有 .py 文件（排除 __init__.py）
for file in current_dir.glob("*.py"):
    if file.name != "__init__.py":
        module_name = file.stem  # 文件名（不带 .py）
        importlib.import_module(f".{module_name}", package=__package__)

# ComfyUI 要求的导出
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}