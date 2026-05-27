"""
路由模块：rename — 手动重命名文件/文件夹
"""
import os
import logging
from fastapi import APIRouter, HTTPException

from core.file_ops.sidecars import move_sidecars
from shared import config_m

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/rename")
def rename_item(old_path: str, new_name: str):
    """手动重命名文件或文件夹"""
    logger.info(f"[rename] old_path={old_path}")
    logger.info(f"[rename] new_name={new_name}")
    logger.info(f"[rename] exists={os.path.exists(old_path)}")
    if not os.path.exists(old_path):
        # 尝试修复路径分隔符
        alt_path = old_path.replace("/", "\\")
        logger.info(f"[rename] 尝试替换分隔符: {alt_path} exists={os.path.exists(alt_path)}")
        if os.path.exists(alt_path):
            old_path = alt_path
        else:
            raise HTTPException(status_code=404, detail=f"Path not found: {old_path}")
    
    parent = os.path.dirname(old_path)
    new_path = os.path.join(parent, new_name)
    
    if os.path.exists(new_path):
        raise HTTPException(status_code=400, detail="Target name already exists")
    
    try:
        os.rename(old_path, new_path)
        
        # 同步 media_library.json
        library = config_m.load_library()
        changed = False
        if os.path.isdir(new_path):
            # 文件夹重命名：更新所有子文件的路径
            for v in library:
                fp = v.get("file_path", "")
                if fp.startswith(old_path + os.sep) or fp.startswith(old_path + "/"):
                    v["file_path"] = new_path + fp[len(old_path):]
                    base = config_m.config.scan_paths[0] if config_m.config.scan_paths else ""
                    if base:
                        rel = os.path.relpath(os.path.dirname(v["file_path"]), base)
                        v["folder_name"] = "" if rel == "." else rel
                    changed = True
            
            # movie 类型（单视频文件夹）：同时重命名视频文件和关联文件
            video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}
            try:
                items = os.listdir(new_path)
                videos = [f for f in items if os.path.isfile(os.path.join(new_path, f)) and os.path.splitext(f)[1].lower() in video_exts]
                subdirs = [f for f in items if os.path.isdir(os.path.join(new_path, f)) and not f.startswith('.')]
                if len(videos) == 1 and len(subdirs) == 0:
                    # 单视频文件夹：重命名视频文件为文件夹名 + 原扩展名
                    old_video = videos[0]
                    ext = os.path.splitext(old_video)[1]
                    if not ext:
                        pass  # 视频没有扩展名，跳过
                    else:
                        new_video = new_name + ext
                        if old_video != new_video:
                            old_vp = os.path.join(new_path, old_video)
                            new_vp = os.path.join(new_path, new_video)
                            if not os.path.exists(new_vp):
                                os.rename(old_vp, new_vp)
                                # 更新 library 中的文件路径和文件名
                                old_vp_norm = old_vp.replace("/", os.sep)
                                for v in library:
                                    vfp = v.get("file_path", "").replace("/", os.sep)
                                    if vfp == old_vp_norm:
                                        v["file_path"] = new_vp
                                        v["file_name"] = new_video
                                        changed = True
                                # 重命名关联文件（NFO、poster 等）
                                move_sidecars(old_vp, new_vp, os.rename)
            except OSError:
                pass
        else:
            # 文件重命名
            for v in library:
                if v.get("file_path") == old_path:
                    v["file_path"] = new_path
                    v["file_name"] = new_name
                    changed = True
                    break
            
            # 同时重命名对应的 .nfo / -poster.jpg 等关联文件
            move_sidecars(old_path, new_path, os.rename)
            
            # 单视频文件夹（仅 movie 类型）：同步重命名父文件夹
            # TV 类型绝不联动改文件夹名（多集共用一个文件夹）
            video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".rmvb", ".rm", ".flv", ".ts", ".m4v"}
            file_ext = os.path.splitext(new_name)[1].lower()
            if file_ext in video_exts:
                folder_path = os.path.dirname(new_path)
                # 检查文件夹类型：如果是 TV/season 类型，跳过
                folder_type = ""
                for v in library:
                    fp = v.get("file_path", "")
                    if fp.startswith(folder_path):
                        folder_type = v.get("folder_type", "")
                        break
                # 只有 movie 类型（或未分类的单视频文件夹）才同步改文件夹名
                is_tv = folder_type in ("tv", "season", "anime")
                if not is_tv:
                    try:
                        items = os.listdir(folder_path)
                        videos_in_folder = [f for f in items if os.path.isfile(os.path.join(folder_path, f)) and os.path.splitext(f)[1].lower() in video_exts]
                        subdirs_in_folder = [f for f in items if os.path.isdir(os.path.join(folder_path, f)) and not f.startswith('.')]
                        if len(videos_in_folder) == 1 and len(subdirs_in_folder) == 0:
                            new_folder_name = os.path.splitext(new_name)[0]
                            old_folder_name = os.path.basename(folder_path)
                            if old_folder_name != new_folder_name:
                                new_folder_path = os.path.join(os.path.dirname(folder_path), new_folder_name)
                                if not os.path.exists(new_folder_path):
                                    os.rename(folder_path, new_folder_path)
                                    for v in library:
                                        fp = v.get("file_path", "")
                                        if fp.startswith(folder_path + os.sep) or fp.startswith(folder_path + "/") or fp == new_path:
                                            v["file_path"] = new_folder_path + fp[len(folder_path):]
                                            base = config_m.config.scan_paths[0] if config_m.config.scan_paths else ""
                                            if base:
                                                rel = os.path.relpath(os.path.dirname(v["file_path"]), base)
                                                v["folder_name"] = "" if rel == "." else rel
                                            changed = True
                                    new_path = os.path.join(new_folder_path, new_name)
                    except OSError:
                        pass
        
        if changed:
            config_m.save_library(library)
        
        return {"status": "ok", "old_path": old_path, "new_path": new_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
