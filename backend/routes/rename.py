"""
路由模块：rename — 手动重命名文件/文件夹
"""
import os
import re
import logging
from fastapi import APIRouter, HTTPException

from core.file_ops.sidecars import move_sidecars
from shared import config_m, guard_path

logger = logging.getLogger(__name__)
router = APIRouter()


# 季目录名（与 routes/library_tree.py 里 _SEASON_DIR_PAT 同口径）
_SEASON_DIR_RE = re.compile(
    r'(?:S\d+|第\d+季|第[一二三四五六七八九十]+季|Season\s*\d+|特别篇|SP|OVA|OAD|剧[場场]版|Specials?)',
    re.I,
)
# 集号标记：把一个目录改成带集号的名字，一定是错的
_EPISODE_MARK_RE = re.compile(r'(?:S\d+E\d+|\bEP?\d+\b|第\d+[集话話])', re.I)


_TV_FOLDER_TYPES = ("tv", "season", "anime")


def _folder_rename_blocked(folder_path: str, new_file_name: str, library: list) -> bool:
    """改文件名时，是否**禁止**把它所在的文件夹一起改成同名。

    联动改名本来只对 movie 的单片封装夹成立，判据是「目录内 1 个视频 0 个子目录」。
    漏网的是**只有 1 集的季目录**（新番刚下第一集）—— 它同样满足那个判据，于是
    季目录被改成集文件名，看上去就是「文件夹名变成乱码」。

    原来唯一的保护是读 media_library.json 里的 `folder_type`，而这个字段
    **从来没被写进库**（只在 library_tree 建树时现算），所以恒为空、保护形同不存在。
    这里保留那条（万一以后真写进库就能生效），另加三条可判定的判据。任一命中就不联动。
    """
    # 1. 库里记着这个目录属于剧集类。
    #    startswith 必须带分隔符，否则 `…\某片` 会命中兄弟目录 `…\某片2` 的条目。
    for v in library:
        fp = v.get("file_path", "")
        if fp.startswith(folder_path + os.sep) or fp.startswith(folder_path + "/"):
            if (v.get("folder_type") or "") in _TV_FOLDER_TYPES:
                return True
            break

    # 2. 用户手动把这个目录标成了剧集类
    try:
        import organizer

        if (organizer._load_folder_type_override(folder_path) or "") in _TV_FOLDER_TYPES:
            return True
    except Exception:
        pass

    # 3. 目录名本身像季目录 / 特典目录
    if _SEASON_DIR_RE.search(os.path.basename(folder_path)):
        return True

    # 4. 新文件名带集号：把一个目录改成带集号的名字一定是错的
    if _EPISODE_MARK_RE.search(os.path.splitext(new_file_name)[0]):
        return True

    return False


def _sync_folder_name(v: dict):
    """file_path 改过之后同步 folder_name。

    原来这里写死 `scan_paths[0]` 且不加虚拟库名前缀。文件不在第一个扫描路径下时
    `os.path.relpath` 会算出 `..\\..\\第二个扫描路径\\电影\\某片` —— 目录树完全按
    folder_name 重建，`..` 于是变成一个节点名，用户看到的就是外层文件夹名变成
    一串看不懂的东西。算不出来时**保留原值**，宁可旧值过期也不要写一个坏值。
    """
    import library_paths

    folder_name = library_paths.compute_folder_name(v.get("file_path", ""), config_m.config)
    if folder_name is not None:
        v["folder_name"] = folder_name


@router.post("/rename")
def rename_item(old_path: str, new_name: str):
    """手动重命名文件或文件夹"""
    guard_path(old_path, "重命名")
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
    
    # new_name 只取最后一段。前端改文件夹名时传的是**整条新路径**
    # （ShadowNameSection 拼的 `parentDir + "\\" + newName`），而下面把 new_name
    # 当文件名用了好几处 —— 最坑的是 `os.path.join(new_path, new_name + ext)`：
    # Windows 的 join 遇到绝对路径直接返回后者，视频于是被 rename 出封装夹、
    # 落到合集目录里，封装夹变成空壳。这个接口的语义本来就是「改名」而不是
    # 「移动」，取 basename 同时也挡住了路径穿越。
    new_name = os.path.basename(new_name.replace("/", os.sep).rstrip("\\/")) or new_name

    parent = os.path.dirname(old_path)
    new_path = os.path.join(parent, new_name)

    if os.path.exists(new_path):
        raise HTTPException(status_code=400, detail="Target name already exists")
    
    try:
        os.rename(old_path, new_path)

        # 同步 media_library.json。
        # 整段持锁：这里的文件系统操作（rename / listdir）都是毫秒级，
        # 而临界区必须覆盖 load → 改 → save，只锁 save 挡不住丢更新。
        with config_m.library_lock:
            library = config_m.load_library()
            changed = False
            if os.path.isdir(new_path):
                # 文件夹重命名：更新所有子文件的路径
                for v in library:
                    fp = v.get("file_path", "")
                    if fp.startswith(old_path + os.sep) or fp.startswith(old_path + "/"):
                        v["file_path"] = new_path + fp[len(old_path):]
                        _sync_folder_name(v)
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
                    if not _folder_rename_blocked(folder_path, new_name, library):
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
                                                _sync_folder_name(v)
                                                changed = True
                                        new_path = os.path.join(new_folder_path, new_name)
                        except OSError:
                            pass

            if changed:
                config_m.save_library(library)

        return {"status": "ok", "old_path": old_path, "new_path": new_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
