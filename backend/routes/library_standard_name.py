"""
路由模块：library_standard_name — 标准名（影子名）的按路径重新生成

与 library_clean_name.py 的 /library/clean-name/generate 对称：
前者管检索名，这里管标准名，两个按钮走同一套取名逻辑（scan_name_filler）。
"""
import logging

from fastapi import APIRouter

from shared import config_m

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/media/shadow-name/generate")
def generate_standard_name(req: dict):
    """按 NFO 重算标准名，用户点按钮显式触发。

    is_folder=true 时对该目录下所有视频逐条重算（番剧要整季一起，
    单集重算意义不大）。手填过的（source=manual）跳过不动。
    """
    from scan_name_filler import regenerate_standard_names

    path = req.get("path") or req.get("file_path") or ""
    is_folder = bool(req.get("is_folder", False))
    if not path:
        return {"status": "error", "message": "path required"}

    result = {}

    def _regen(library):
        nonlocal result
        result = regenerate_standard_names(library, path, is_folder)
        return None if result["updated"] else False

    config_m.mutate_library(_regen)

    if result.get("updated"):
        return {"status": "ok", **result}

    # 把「一条都没匹配到」和「匹配到了但都跳过 / 算不出名字」分开报，
    # 否则用户只能看到一个没有信息量的失败提示
    if not result.get("matched"):
        message = f"媒体库里没有这个路径下的视频：{path}"
    elif result.get("skipped") == result.get("matched"):
        message = f"{result['matched']} 个视频的标准名都是手填的，未改动"
    else:
        message = f"匹配到 {result.get('matched', 0)} 个视频，但从 NFO 与检索名都算不出标准名"
    logger.warning(f"[shadow-name/generate] 未更新: {path} -> {result}")
    return {"status": "failed", "message": message, **result}
