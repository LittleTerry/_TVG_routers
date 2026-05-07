import os
import asyncio

from aiohttp import web
import folder_paths
import server

import logging

logger = logging.getLogger(__name__)

# 直接获取路由实例
routes = server.PromptServer.instance.routes

# ---------------------
# 工具函数 & 图标定义
# ---------------------
FILE_ICONS = {
    "image": "🖼️",
    "video": "🎞️",
    "audio": "🎵",
    "text": "📝",
    "unknown": "📄",
}

FOLDER_ICON = "📁"          # 非递归
FOLDER_ICON_RECUR = "📂"    # 递归模式

def detect_file_type(name: str) -> str:
    ext = os.path.splitext(name)[1].lower()
    if ext in {".3g2", ".3gp", ".amv", ".asf", ".avi", ".drc", ".flv", ".f4v", ".f4p", ".m4v", ".mkv", ".mov", ".qt", ".mp4", ".mpg", ".mpeg", ".mpe", ".mpv", ".m2v", ".mts", ".m2ts", ".ts", ".mxf", ".nsv", ".ogv", ".rm", ".rmvb", ".svi", ".viv", ".vob", ".webm", ".wmv", ".yuv"}:
        return "video"
    if ext in {".apng", ".astc", ".avif", ".bmp", ".dng", ".gif", ".heic", ".heif", ".ico", ".jfif", ".jpeg", ".jpg", ".ktx", ".pkm", ".png", ".svg", ".tif", ".tiff",  ".wbmp", ".webp"}:
        return "image"
    if ext in {".3gp", ".aa", ".aac", ".aax", ".act", ".aiff", ".alac", ".amr", ".ape", ".au", ".awb", ".dss", ".dvf", ".f4a", ".f4b", ".flac", ".gsm", ".iklax", ".ivs", ".m4a", ".m4b", ".mmf", ".movpkg", ".mp1", ".mp2", ".mp3", ".mpc", ".msv", ".nmf", ".ogg", ".oga", ".mogg", ".opus", ".ra", ".rf64", ".sln", ".tta", ".voc", ".vox", ".wav", ".wma", ".wv", ".webm", ".8svx"}:
        return "audio"
    if ext in {".txt", ".md", ".rst", ".log", ".csv", ".tsv", ".json", ".xml", ".yaml", ".yml", ".ini", ".cfg", ".htm", ".html", ".xhtml", ".mht", ".mhtml", ".pdf", ".epub", ".mobi", ".azw3", ".doc", ".docx", ".odt", ".rtf", ".wpd", ".xls", ".xlsx", ".ods", ".ppt", ".pptx", ".odp", ".tex", ".bib", ".mdown", ".markdown"}:
        return "text"
    return "unknown"

def match_extension(filename: str, extensions: list[str] | None) -> bool:
    if not extensions:
        return True
    ext = os.path.splitext(filename)[1].lstrip(".").lower()
    # 使用 NOEXT 表示无扩展名
    if not ext and "noext" in [e.lower() for e in extensions]:
        return True
    return ext.lower() in [e.lower() for e in extensions]

def safe_join(base_dir: str, subfolder: str) -> str:
    """安全拼接子目录路径，防止越界"""
    target = os.path.abspath(os.path.join(base_dir, subfolder))
    if os.path.commonpath([target, base_dir]) != os.path.abspath(base_dir):
        raise ValueError(f"Invalid subfolder path: {subfolder}")
    return target

def format_size(size: int) -> str:
    if size < 1024:
        return f"{size}B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f}KB"
    else:
        return f"{size / (1024 * 1024):.1f}MB"

# ---------------------
# 排序功能
# ---------------------
def sort_children(children: list[dict], field: str, order: str) -> list[dict]:
    reverse = order == "desc"
    def key_func(item):
        match field:
            case "name":
                return item["name"].lower()
            case "size":
                return item.get("size", item.get("_size", 0))
            case "ctime":
                return item.get("_ctime", 0)
            case "mtime":
                return item.get("_mtime", 0)
            case "type":
                return 0 if item["type"] == "folder" else 1
        return item["name"].lower()
    return sorted(children, key=key_func, reverse=reverse)

# ---------------------
# ASCII 树生成器
# ---------------------
def generate_ascii_tree(
    node: dict,
    show_stats=True,
    prefix="",
    enable_icon=True,
    recursive=True,
    sort_field="name",
    sort_order="asc",
    link=True,
    dir_type="",
    subfolder_path=""
) -> str:
    children = sort_children(node.get("children", []), sort_field, sort_order)
    lines = []

    for idx, child in enumerate(children):
        is_last = idx == len(children) - 1
        connector = "└── " if is_last else "├── "

        # 文件夹名称加 /
        name = child["name"]
        if child["type"] == "folder":
            name += "/"

        # 图标部分（不可点击）
        icon = ""
        if enable_icon:
            if child["type"] == "folder":
                icon = FOLDER_ICON_RECUR if recursive else FOLDER_ICON
            else:
                t = detect_file_type(child["name"])
                icon = FILE_ICONS.get(t, "📄")
        icon_part = f"{icon} " if icon else ""

        # 文件名部分（可点击）
        if link and child["type"] == "file":
            file_url = f"/view?type={dir_type}&subfolder={subfolder_path}&filename={child['name']}"
            name_part = f'<a href="{file_url}" target="_blank">{child["name"]}</a>'
        else:
            name_part = child["name"]

        # 合并图标 + 文件名
        full_name = icon_part + name_part

        line = prefix + connector + full_name

        # 统计信息
        if show_stats:
            if child["type"] == "file":
                line += f" ({format_size(child['size'])})"
            else:
                if recursive:
                    line += f" ({child.get('_count', 0)} | {format_size(child.get('_size', 0))})"
                else:
                    line += " (? | ?B)"

        lines.append(line)

        # 递归处理文件夹
        if child["type"] == "folder" and child.get("children"):
            new_prefix = prefix + ("    " if is_last else "│   ")
            lines.extend(
                generate_ascii_tree(
                    child,
                    show_stats,
                    new_prefix,
                    enable_icon,
                    recursive,
                    sort_field,
                    sort_order,
                    link=link,
                    dir_type=dir_type,
                    subfolder_path=(subfolder_path + "/" + child["name"]).strip("/")
                ).splitlines()
            )

    return "\n".join(lines)


# ---------------------
# 高性能异步目录扫描
# ---------------------
async def scan_directory_async(
    path: str,
    recursive: bool = True,
    filter_type: str | None = None,
    extensions: list[str] | None = None,
) -> dict:
    """
    异步扫描目录，返回树形字典结构
    """
    node = {
        "name": os.path.basename(path) or path,
        "type": "folder",
        "children": [],
        "_count": 0,
        "_size": 0,
        "_ctime": os.stat(path).st_ctime,
        "_mtime": os.stat(path).st_mtime,
    }
    try:
        def scan_dir():
            entries = []
            with os.scandir(path) as it:
                for entry in it:
                    if entry.name.startswith("."):
                        continue
                    st = entry.stat(follow_symlinks=False)
                    entries.append({
                        "name": entry.name,
                        "is_dir": entry.is_dir(follow_symlinks=False),
                        "size": st.st_size if entry.is_file() else 0,
                        "path": entry.path,
                        "ctime": st.st_ctime,
                        "mtime": st.st_mtime,
                    })
            entries.sort(key=lambda e: e["name"].lower())
            return entries
        entries = await asyncio.to_thread(scan_dir)
    except (PermissionError, FileNotFoundError, OSError):
        return node
    tasks = []
    valid_entries = []
    for entry in entries:
        name = entry["name"]
        is_dir = entry["is_dir"]
        size = entry["size"]
        full_path = entry["path"]
        # 过滤
        if filter_type == "file" and is_dir:
            continue
        if filter_type == "folder" and not is_dir:
            continue
        if not is_dir and not match_extension(name, extensions):
            continue
        valid_entries.append(entry)
        if is_dir and recursive:
            tasks.append(scan_directory_async(full_path, recursive, filter_type, extensions))
        else:
            tasks.append(asyncio.sleep(0, result=size))
    results = await asyncio.gather(*tasks) if tasks else []
    for entry, res in zip(valid_entries, results):
        if entry["is_dir"]:
            if recursive:
                child_node = res
                node["children"].append({
                    "name": entry["name"],
                    "type": "folder",
                    "children": child_node.get("children", []),
                    "_count": child_node["_count"],
                    "_size": child_node["_size"],
                    "_ctime": entry["ctime"],
                    "_mtime": entry["mtime"],
                })
                node["_count"] += child_node["_count"]
                node["_size"] += child_node["_size"]
            else:
                node["children"].append({
                    "name": entry["name"],
                    "type": "folder",
                    "children": [],
                    "_count": 0,
                    "_size": 0,
                    "_ctime": entry["ctime"],
                    "_mtime": entry["mtime"],
                })
        else:
            node["children"].append({
                "name": entry["name"],
                "type": "file",
                "size": res,
                "_ctime": entry["ctime"],
                "_mtime": entry["mtime"],
            })
            node["_count"] += 1
            node["_size"] += res
    return node

# ---------------------
# API: 文件列表
# ---------------------
@routes.get("/fs/{type}/list")
async def fs_list(request):
    """
    type: input、output、temp
    ## 查询参数 (Query)
    - subfolder: 可选，相对于目录类型根目录的子目录路径。默认空。
    - ext: 可选，扩展名过滤，逗号分隔，如 'png,jpg,webp'，'noext' 表示无扩展名的文件。默认无过滤。
    """
    dir_type = request.match_info.get("type", None)
    base_dir = folder_paths.get_directory_by_type(dir_type)
    if not base_dir:
        return web.json_response({"error": f"Invalid directory type: {dir_type}"}, status=400)
    query = request.rel_url.query
    subfolder = query.get("subfolder", "").strip()
    try:
        target_dir = safe_join(base_dir, subfolder) if subfolder else base_dir
    except ValueError as ex:
        return web.json_response({"error": str(ex)}, status=403)
    if not os.path.exists(target_dir):
        return web.json_response({"error": f"No such subfolder: {subfolder}"}, status=404)
    ext_param = query.get("ext", "").strip()
    extensions = [e.strip().lower() for e in ext_param.split(",")] if ext_param else None
    tree = await scan_directory_async(target_dir, recursive=False, filter_type="file", extensions=extensions)
    filenames = [c["name"] for c in tree.get("children", []) if c["type"] == "file"]
    return web.json_response(filenames)

# ---------------------
# API: ASCII 树
# ---------------------
@routes.get("/fs/{type}/tree")
async def fs_tree(request):
    """
    type: input、output、temp
    ## 查询参数 (Query)
    - subfolder: 可选，相对于目录类型根目录的子目录路径。默认空。
    - recursive: 可选，是否递归扫描子目录。true/false。默认 true。
    - filter: 可选，类型过滤。'file' 或 'folder'。默认无过滤。
    - ext: 可选，扩展名过滤，逗号分隔，如 'png,jpg,webp'，'noext' 表示无扩展名的文件。默认无过滤。
    - sort: 可选，排序功能，支持 name/size/ctime/mtime/type。默认 name。
    - order: 可选，排序顺序，asc/desc。默认 asc。
    - show_stats: 可选，是否输出统计信息 (数量、大小)。true/false。默认 true。
    - icon: 可选，是否显示图标。true/false。默认 true。
    """
    dir_type = request.match_info.get("type", None)
    base_dir = folder_paths.get_directory_by_type(dir_type)
    if not base_dir:
        return web.json_response({"error": f"Invalid directory type: {dir_type}"}, status=400)
    query = request.rel_url.query
    subfolder = query.get("subfolder", "").strip()
    try:
        target_dir = safe_join(base_dir, subfolder) if subfolder else base_dir
    except ValueError as ex:
        return web.json_response({"error": str(ex)}, status=403)
    if not os.path.exists(target_dir):
        return web.json_response({"error": f"No such subfolder: {subfolder}"}, status=404)
    recursive = query.get("recursive", "true").lower() == "true"
    filter_type = query.get("filter")
    filter_type = filter_type if filter_type in ("file", "folder") else None
    ext_param = query.get("ext", "").strip()
    extensions = [e.strip().lower() for e in ext_param.split(",")] if ext_param else None
    show_stats = query.get("show_stats", "true").lower() == "true"
    icon = query.get("icon", "true").lower() == "true"
    link = query.get("link", "true").lower() == "true"
    sort_field = query.get("sort", "name").lower()
    sort_order = query.get("order", "asc").lower()
    if sort_field not in ("name", "size", "ctime", "mtime", "type"):
        sort_field = "name"
    if sort_order not in ("asc", "desc"):
        sort_order = "asc"
    tree = await scan_directory_async(target_dir, recursive, filter_type, extensions)
    root_name = dir_type if not subfolder else f"{dir_type}/{subfolder}"
    if show_stats:
        root_name = f"📂 {root_name}/ ({tree.get('_count', 0)} | {format_size(tree.get('_size', 0))})"
    content = root_name + "\n" + generate_ascii_tree(
        tree,
        show_stats,
        "",
        enable_icon=icon,
        recursive=recursive,
        sort_field=sort_field,
        sort_order=sort_order,
        link=link,
        dir_type=dir_type,
        subfolder_path=subfolder
    )
    if link:
        return web.Response(text=f"<pre>{content}</pre>", content_type="text/html")
    else:
        return web.Response(text=content, content_type="text/plain")