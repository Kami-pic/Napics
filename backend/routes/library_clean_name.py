"""
路由模块：library_clean_name
从 library_crud.py 拆分 — 清洗名（检索名）的手动修改与重新生成

拆分原因：library_crud.py 越过 400 行红线。清洗名是一个自洽的功能域。
"""
import logging
import os
import re

from fastapi import APIRouter

from shared import config_m

logger = logging.getLogger(__name__)
router = APIRouter()

# 中日文字符（用于从 display 名里提取中文部分）
_CJK_PATTERN = r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]+'


def _apply_cn_part(item: dict, clean_name: str) -> None:
    """把 display 名里的中日文部分提取到 clean_name_cn"""
    cn_parts = re.findall(_CJK_PATTERN, clean_name)
    if cn_parts:
        item["clean_name_cn"] = "".join(cn_parts)


@router.post("/library/clean-name")
def set_clean_name(req: dict):
    """手动修改清洗名（manual 来源，最高优先级）

    支持字段：clean_name（display/cn）、clean_name_en（英文名）
    支持 is_folder=true 时按文件夹路径匹配其下所有视频
    """
    file_path = req.get("file_path", "")
    clean_name = req.get("clean_name", "")
    clean_name_en = req.get("clean_name_en")
    is_folder = req.get("is_folder", False)
    if not file_path:
        return {"status": "error", "message": "file_path required"}

    result = {"status": "not_found"}

    def _apply(library):
        nonlocal result

        if is_folder:
            folder_norm = file_path.replace("\\", "/").rstrip("/") + "/"
            updated = 0
            for v in library:
                v_folder = v.get("file_path", "").replace("\\", "/")
                if v_folder.startswith(folder_norm) or os.path.dirname(v_folder).replace("\\", "/") + "/" == folder_norm:
                    if clean_name_en is not None:
                        v["clean_name_en"] = clean_name_en
                        v["clean_name_source"] = "manual"
                        updated += 1
                    if clean_name:
                        v["clean_name"] = clean_name
                        v["clean_name_source"] = "manual"
                        _apply_cn_part(v, clean_name)
                        updated += 1
            if updated > 0:
                result = {"status": "ok", "updated": updated}
                return None
            # 文件夹下没有视频，尝试直接匹配
            for v in library:
                if v.get("file_path") == file_path:
                    if clean_name:
                        v["clean_name"] = clean_name
                        v["clean_name_source"] = "manual"
                        _apply_cn_part(v, clean_name)
                    if clean_name_en is not None:
                        v["clean_name_en"] = clean_name_en
                        v["clean_name_source"] = "manual"
                    result = {"status": "ok"}
                    return None
            result = {"status": "ok", "updated": 0}
            return False

        # 视频模式：精确匹配 file_path
        for v in library:
            if v.get("file_path") == file_path:
                if clean_name is not None:
                    v["clean_name"] = clean_name
                    v["clean_name_source"] = "manual" if clean_name else ""
                    if clean_name:
                        _apply_cn_part(v, clean_name)
                if clean_name_en is not None:
                    v["clean_name_en"] = clean_name_en
                    v["clean_name_source"] = "manual"
                result = {"status": "ok"}
                return None
        result = {"status": "not_found"}
        return False

    config_m.mutate_library(_apply)
    return result


@router.post("/library/clean-name/generate")
def generate_clean_name(req: dict):
    """按文件名自动生成搜索索引名（中文+英文），用户点按钮显式触发"""
    from clean_name_system import regenerate_clean_names

    file_path = req.get("file_path", "")
    if not file_path:
        return {"status": "error", "message": "file_path required"}

    result = {}

    def _regen(library):
        nonlocal result
        result = regenerate_clean_names(library, file_path, req.get("is_folder", False))
        return None if result["updated"] else False

    config_m.mutate_library(_regen)
    if result["updated"]:
        return {"status": "ok", **result}

    # 把失败原因说清楚：路径对不上和解析失败要分开，否则线上排查只能靠猜
    reason = result.get("reason", "")
    if reason == "not_in_library":
        message = f"媒体库里没有这条记录，路径可能不一致：{file_path}"
    elif reason == "unparsable":
        message = f"匹配到 {result.get('matched', 0)} 条记录，但从 NFO / 文件夹名 / 文件名都解析不出名称"
    else:
        message = "缺少 file_path"
    logger.warning(f"[clean-name/generate] 失败({reason}): {file_path}")
    return {"status": "failed", "message": message, **result}
