"""
路由模块：library_tree
从 library.py 拆分 — 目录树构建（get_library_tree + finalize + post_process）
"""
import os
import re
import logging
from typing import Dict, List, Optional

from fastapi import APIRouter

from shared import config_m, shadow_m, _tmdb_client
import organizer, scraper

logger = logging.getLogger(__name__)
router = APIRouter()


def _build_real_node_paths(videos: List[dict]) -> Dict[str, str]:
    """folder_name 的每一级前缀 → 该级目录的**真实绝对路径**。

    为什么需要它：节点 path 原来是 `os.path.join(scan_paths[0], 相对路径)` 拼出来的
    ——只有当这个文件恰好来自第一个扫描路径时才对。文件来自 scan_paths[1..] 或某个
    虚拟库时，拼出来的是文件系统上**不存在**的路径。而前端的「查看 / 定位到目录」
    是拿真实路径（下载任务的 save_path、发现条目的 local_folder）去树里比对的，
    假路径必然匹配不上，用户看到的就是点了没反应。

    做法：每个视频的 `file_path` 是真实的，`dirname(file_path)` 就对应 folder_name
    的最后一级；逐级 dirname 上去就得到每一级的真实路径，全程不碰 scan_paths。

    只在「file_path 的末尾若干段和 folder_name 完全一致」时采信 —— 两者不同步
    （改名后漏更新之类）时宁可退回旧拼法，也不要往树上写一个更离谱的路径。
    """
    result: Dict[str, str] = {}
    for v in videos:
        file_path = v.get("file_path") or ""
        rel_dir = (v.get("folder_name") or "").replace("\\", "/")
        parts = [p for p in rel_dir.split("/") if p]
        if not file_path or not parts:
            continue

        # 从最深一级往上退，同时校验每一段的目录名对得上
        node_dir = os.path.dirname(file_path)
        chain = []
        matched = True
        for part in reversed(parts):
            if os.path.basename(node_dir.rstrip("\\/")) != part:
                matched = False
                break
            chain.append(node_dir)
            node_dir = os.path.dirname(node_dir.rstrip("\\/"))
        if not matched:
            continue

        chain.reverse()  # 现在 chain[i] 对应 parts[:i+1]
        for i in range(len(parts)):
            key = "/".join(parts[: i + 1])
            # 已有值就不覆盖：同一目录下的视频算出来的是同一个路径
            result.setdefault(key, chain[i])
    return result


@router.get("/library/tree")
def get_library_tree():
    """生成嵌套的目录树结构"""
    videos = config_m.load_library()
    root_node = {
        "name": "媒体库",
        "path": "",
        "children": [],
        "videos": [],
        "video_count": 0,
        "has_cover": False,
        "_child_index": {},
    }

    config = config_m.config
    base_path = config.scan_paths[0] if config.scan_paths else ""

    # 构建 media_libraries 的库名 → 实际路径映射
    _lib_path_map: Dict[str, str] = {}
    for lib in (config.media_libraries or []):
        if lib.paths:
            _lib_path_map[lib.name] = lib.paths[0]

    # 每个 folder_name 前缀 → 真实绝对目录。见 _build_real_node_paths 的说明。
    real_node_paths = _build_real_node_paths(videos)

    for v in videos:
        rel_dir = v.get("folder_name", "")  # "Movies/Action" 或 "电影/复仇者联盟"
        rel_dir = rel_dir.replace("\\", "/")
        parts = [p for p in rel_dir.split("/") if p]

        current_node = root_node
        current_rel = ""
        # 判断该视频是否属于某个 media_library
        is_lib_video = parts and parts[0] in _lib_path_map
        lib_base = _lib_path_map.get(parts[0], "") if is_lib_video else ""

        for i, part in enumerate(parts):
            current_rel = os.path.join(current_rel, part) if current_rel else part
            child = current_node["_child_index"].get(part)
            if not child:
                # 节点的绝对路径：优先用从视频 file_path 反推出来的**真实**目录。
                # 拼接是最后的退路 —— 它只在 scan_paths[0] 恰好是该文件的扫描根时才对。
                node_path = real_node_paths.get(current_rel.replace("\\", "/"))
                if not node_path:
                    if is_lib_video:
                        if i == 0:
                            # 库名节点：path 用库的第一个路径
                            node_path = lib_base
                        else:
                            # 库内子节点：相对于库路径
                            sub_rel = os.path.join(*parts[1:i+1])
                            node_path = os.path.join(lib_base, sub_rel)
                    else:
                        node_path = os.path.join(base_path, current_rel) if base_path else current_rel
                child = {
                    "name": part,
                    "path": node_path,
                    "children": [],
                    "videos": [],
                    "video_count": 0,
                    "has_cover": False,
                    "_child_index": {},
                }
                current_node["children"].append(child)
                current_node["_child_index"][part] = child
            current_node = child
        current_node["videos"].append(v)

    # 读取用户配置的 category_tags（路径 → 标签）
    configured_tags = config.category_tags or {}

    # 预计算一级分类路径集合
    top_category_paths = set()
    # media_libraries 的库名 → category_tag 映射
    _lib_category_tags: Dict[str, str] = {}
    for lib in (config.media_libraries or []):
        _lib_category_tags[lib.name] = lib.category_tag

    for child in root_node["children"]:
        child_path = child["path"]
        child_name = child["name"]
        # media_libraries 的库名节点 → 一定是一级分类（无论是否有子目录）
        if child_name in _lib_category_tags:
            top_category_paths.add(child_path)
        elif child["children"]:
            # 已配置的标签 → 一定是一级分类
            if child_path in configured_tags:
                top_category_paths.add(child_path)
            else:
                name_lower = child_name.strip().lower()
                if name_lower in organizer._CATEGORY_KEYWORD_MAP:
                    top_category_paths.add(child_path)
                elif any(kw in name_lower for kw in organizer._CATEGORY_KEYWORD_MAP):
                    top_category_paths.add(child_path)

    def _resolve_category_tag(node_path: str, node_name: str) -> str:
        """解析一级分类目录的标签：配置优先，否则自动推断"""
        # media_libraries 的库名节点：使用配置的 category_tag
        if node_name in _lib_category_tags:
            return _lib_category_tags[node_name]
        if node_path in configured_tags:
            return configured_tags[node_path]
        return organizer.infer_category_tag(node_name)

    # 季目录名正则（用于自主推断）
    _SEASON_DIR_PAT = re.compile(
        r'(?:S\d+|第\d+季|第[一二三四五六七八九十]+季|Season\s*\d+|特别篇|SP|OVA|OAD|剧[場场]版|Specials?)',
        re.I
    )
    # 集号文件名正则
    _EPISODE_PAT = re.compile(
        r'(?:S\d+E\d+|EP?\d+|第\d+[集话話]|\b\d{2,3}\b(?=\s*[\.\-\[\(]))',
        re.I
    )

    def _guess_structure_type_from_tree(node) -> str:
        """无 category_tag 时，从树结构特征自主推断底层结构类型（movie/tv）。"""
        children = node.get("children", [])
        videos = node.get("videos", [])

        # 信号1：子目录名匹配季目录模式
        if children:
            season_like = sum(1 for c in children if _SEASON_DIR_PAT.search(c["name"]))
            if season_like >= 1 and season_like >= len(children) * 0.3:
                return "tv"

        # 信号2：视频文件名含集号特征
        if videos:
            ep_count = sum(1 for v in videos if _EPISODE_PAT.search(v.get("file_name", "")))
            if ep_count >= len(videos) * 0.5 and len(videos) >= 2:
                return "tv"

        # 信号3：多视频 + 平均时长短
        if videos and len(videos) >= 3:
            durations = [v.get("duration", 0) for v in videos if v.get("duration", 0) > 0]
            if durations:
                avg_min = (sum(durations) / len(durations)) / 60
                if avg_min < 45:
                    return "tv"

        # 信号4：文件夹名含 tv 类关键词
        folder_name = node.get("name", "")
        if folder_name:
            tag = organizer.infer_category_tag(folder_name)
            if tag and organizer.category_tag_to_structure_type(tag) == "tv":
                return "tv"

        # 信号5：子目录各自有多视频且含集号 → tv（聚合多部剧）
        if children and not videos:
            tv_like_children = 0
            for c in children:
                c_videos = c.get("videos", [])
                if c_videos and len(c_videos) >= 2:
                    c_ep = sum(1 for v in c_videos if _EPISODE_PAT.search(v.get("file_name", "")))
                    if c_ep >= len(c_videos) * 0.5:
                        tv_like_children += 1
                elif c.get("children"):
                    c_season = sum(1 for cc in c["children"] if _SEASON_DIR_PAT.search(cc["name"]))
                    if c_season >= 1:
                        tv_like_children += 1
            if tv_like_children >= len(children) * 0.5 and tv_like_children >= 1:
                return "tv"

        # 默认 movie
        return "movie"

    def _infer_folder_type_from_tree(node, category_tag: str) -> str:
        """从树结构推断 folder_type，不依赖文件系统。"""
        children = node.get("children", [])
        videos = node.get("videos", [])
        has_children = len(children) > 0
        has_videos = len(videos) > 0

        if category_tag:
            structure_type = organizer.category_tag_to_structure_type(category_tag)
        else:
            structure_type = _guess_structure_type_from_tree(node)

        if structure_type == "movie":
            if not has_children:
                if not has_videos:
                    return ""
                if len(videos) == 1:
                    return "movie"
                vnames = [v.get("file_name", "") for v in videos]
                if organizer._is_series_collection(vnames, node["name"]):
                    return "series"
                return "collection"
            if has_videos:
                return "collection"
            all_single = all(len(c.get("videos", [])) <= 1 and not c.get("children") for c in children)
            if all_single:
                child_names = [c["name"] for c in children]
                if organizer._is_series_collection(child_names, node["name"]):
                    return "series"
                return "collection"
            return "mixed"

        elif structure_type == "tv":
            if not has_children:
                if has_videos:
                    return "tv"
                return ""

            _SPECIAL_PAT = re.compile(r'(?:Season\s*0+|Specials?|SP|OVA|OAD|特别篇|剧[場场]版)', re.I)

            if len(children) == 1:
                return "tv"

            children_with_subdirs = 0
            for c in children:
                if _SPECIAL_PAT.search(c["name"]):
                    continue
                if c.get("children") and len(c["children"]) > 0:
                    children_with_subdirs += 1

            if children_with_subdirs >= 2:
                return "mixed"

            return "tv"

        return ""

    def finalize(node, parent_category_tag=""):
        count = len(node["videos"])
        has_cover = count > 0
        category_tag = parent_category_tag
        if node["path"] in top_category_paths:
            category_tag = _resolve_category_tag(node["path"], node["name"])
        for child in node["children"]:
            c_count, c_cover = finalize(child, category_tag)
            count += c_count
            if c_cover: has_cover = True
        node["video_count"] = count
        node["has_cover"] = has_cover
        # 标记分类聚合文件夹
        if not node["children"] and len(node["videos"]) > 1:
            vfiles = [v.get("file_name", "") for v in node["videos"]]
            node["is_category"] = scraper._is_category_folder(node["name"], vfiles)
        else:
            node["is_category"] = False
        # 添加 folder_type
        if node["path"] and node["path"] != base_path:
            # 优先读取用户手动覆盖
            _ft_override = None
            try:
                _ft_override = organizer._load_folder_type_override(node["path"])
            except Exception:
                pass

            if node["path"] in top_category_paths:
                node["category_tag"] = category_tag
                node["is_top_category"] = True
                node["is_virtual_library"] = node["name"] in _lib_category_tags
                node["folder_type"] = _ft_override or _infer_folder_type_from_tree(node, category_tag)
            else:
                node["category_tag"] = ""
                node["is_top_category"] = False
                if _ft_override:
                    node["folder_type"] = _ft_override
                else:
                    node["folder_type"] = _infer_folder_type_from_tree(node, category_tag)
        else:
            node["folder_type"] = ""
            node["category_tag"] = ""
            node["is_top_category"] = False
        # 文件夹级影子名
        node["shadow_name"] = ""
        node["shadow_tmdb_id"] = None

        if node.get("videos"):
            for v in node["videos"]:
                if v.get("shadow_name"):
                    _raw_shadow = v["shadow_name"]
                    if node.get("folder_type") in ("tv", "season"):
                        _raw_shadow = re.sub(r'\s+S\d+E\d+\s*$', '', _raw_shadow, flags=re.IGNORECASE).strip()
                        _raw_shadow = re.sub(r'\s+S\d+\s*$', '', _raw_shadow, flags=re.IGNORECASE).strip()
                        _raw_shadow = re.sub(r'\s+E\d+\s*$', '', _raw_shadow, flags=re.IGNORECASE).strip()
                    node["shadow_name"] = _raw_shadow
                    node["shadow_tmdb_id"] = v.get("shadow_tmdb_id")
                    break

        if not node.get("shadow_name") and node.get("children"):
            for child in node["children"]:
                if child.get("shadow_name"):
                    _raw_shadow2 = child["shadow_name"]
                    if node.get("folder_type") in ("tv",):
                        _raw_shadow2 = re.sub(r'\s+S\d+E\d+\s*$', '', _raw_shadow2, flags=re.IGNORECASE).strip()
                        _raw_shadow2 = re.sub(r'\s+S\d+\s*$', '', _raw_shadow2, flags=re.IGNORECASE).strip()
                        _raw_shadow2 = re.sub(r'\s+E\d+\s*$', '', _raw_shadow2, flags=re.IGNORECASE).strip()
                    node["shadow_name"] = _raw_shadow2
                    node["shadow_tmdb_id"] = child.get("shadow_tmdb_id")
                    break

        # 文件夹级 clean_name
        if node["path"] and node["path"] != base_path:
            from clean_name_system import clean_for_folder, parse_legacy_clean_name
            from organizer import _extract_season_number
            _season_num = _extract_season_number(node["name"]) if node.get("folder_type") == "season" else None
            _folder_result = clean_for_folder(
                folder_name=node["name"],
                shadow_name=node.get("shadow_name", ""),
                folder_type=node.get("folder_type", ""),
                season_num=_season_num,
            )
            node["clean_name"] = _folder_result.display or node["name"]
            node["clean_name_cn"] = _folder_result.cn
            node["clean_name_en"] = _folder_result.en
            node["clean_name_original"] = _folder_result.original

            # 手动覆盖
            for video in node.get("videos", []):
                if video.get("clean_name_source") == "manual":
                    if video.get("clean_name"):
                        node["clean_name"] = video["clean_name"]
                        _cn_parts = re.findall(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]+', video["clean_name"])
                        if _cn_parts:
                            node["clean_name_cn"] = "".join(_cn_parts)
                    if video.get("clean_name_en"):
                        node["clean_name_en"] = video["clean_name_en"]
                    break

            # 垃圾英文名检测
            _has_manual = any(v.get("clean_name_source") == "manual" and v.get("clean_name_en") for v in node.get("videos", []))
            _en = node["clean_name_en"]
            if _en and not _has_manual and node.get("folder_type") in ("tv", "season", "movie", "mixed", ""):
                _JUNK_EN = {"season", "seasons", "sps", "sp", "extra", "extras", "ncop", "nced",
                            "pv", "menu", "tv", "ova", "oad", "bonus", "specials"}
                _en_stripped = re.sub(r'[sS]\s*\d+', '', _en).strip()
                _en_stripped = re.sub(r'\d+', '', _en_stripped).strip()
                if len(_en_stripped) <= 3 or _en.lower().strip() in _JUNK_EN:
                    node["clean_name_en"] = ""

            # 自愈层1：视频条目缺失结构化字段时，从 clean_name 反向解析
            for video in node.get("videos", []):
                if not video.get("clean_name_cn") and not video.get("clean_name_en") and video.get("clean_name"):
                    _legacy = parse_legacy_clean_name(video)
                    if _legacy.cn:
                        video["clean_name_cn"] = _legacy.cn
                    if _legacy.en:
                        video["clean_name_en"] = _legacy.en
                    if _legacy.original:
                        video["clean_name_original"] = _legacy.original
                    if _legacy.cn or _legacy.en:
                        library_dirty[0] = True

            # 自愈层2：从视频条目冒泡补全文件夹
            _folder_en_len = len(node["clean_name_en"])
            for video in node.get("videos", []):
                if not node["clean_name_cn"] and video.get("clean_name_cn"):
                    node["clean_name_cn"] = video["clean_name_cn"]
                v_en = video.get("clean_name_en", "")
                if v_en and (not node["clean_name_en"] or (len(v_en) > _folder_en_len + 3)):
                    _v_en_stripped = re.sub(r'[sS]\s*\d+', '', v_en).strip()
                    _v_en_stripped = re.sub(r'\d+', '', _v_en_stripped).strip()
                    if len(_v_en_stripped) > 3:
                        node["clean_name_en"] = v_en
                        _folder_en_len = len(v_en)
                if not node["clean_name_original"] and video.get("clean_name_original"):
                    node["clean_name_original"] = video["clean_name_original"]
                if node["clean_name_cn"] and node["clean_name_en"] and node["clean_name_original"]:
                    break

            # 自愈层4：从子树冒泡（仅 tv/season）
            if node.get("folder_type") in ("tv", "season"):
                for child in node.get("children", []):
                    if not node["clean_name_cn"] and child.get("clean_name_cn"):
                        node["clean_name_cn"] = child["clean_name_cn"]
                    if not node["clean_name_en"] and child.get("clean_name_en"):
                        node["clean_name_en"] = child["clean_name_en"]
                    if not node["clean_name_original"] and child.get("clean_name_original"):
                        node["clean_name_original"] = child["clean_name_original"]
                    if node["clean_name_cn"] and node["clean_name_en"] and node["clean_name_original"]:
                        break
        else:
            node["clean_name"] = node.get("name", "")
            node["clean_name_cn"] = ""
            node["clean_name_en"] = ""
            node["clean_name_original"] = ""
        return count, has_cover

    # 自愈标志
    library_dirty = [False]
    finalize(root_node)

    # 二次遍历：标记 season + 传播 parent_category_tag + 计算层级 clean_name
    def post_process(node, inherited_tag="", parent_cn="", parent_en="", parent_original=""):
        from clean_name_system import clean_for_folder, clean_from_filename
        from organizer import _extract_season_number

        cat = node.get("category_tag", "") or inherited_tag
        node["parent_category_tag"] = cat

        # 深度修正：如果父节点没影子名，尝试从子节点反向追溯
        if not node.get("shadow_name") and node.get("children"):
            for child in node["children"]:
                if child.get("shadow_name"):
                    node["shadow_name"] = child["shadow_name"]
                    break

        # 当前节点的结构化名称，用于传递给子节点
        if node.get("is_top_category"):
            cur_cn = ""
            cur_en = ""
            cur_original = ""
        else:
            cur_cn = node.get("clean_name_cn", "") or parent_cn
            cur_en = node.get("clean_name_en", "") or parent_en
            cur_original = node.get("clean_name_original", "") or parent_original

        # tv 的子目录标记为 season + 计算季 clean_name
        if node.get("folder_type") == "tv":
            for child in node.get("children", []):
                if child.get("folder_type") != "mixed":
                    child["folder_type"] = "season"
                _child_has_manual = any(v.get("clean_name_source") == "manual" for v in child.get("videos", []))
                if _child_has_manual:
                    continue
                season_num = _extract_season_number(child["name"])
                folder_result = clean_for_folder(
                    folder_name=child["name"],
                    shadow_name=child.get("shadow_name", ""),
                    parent_cn=cur_cn,
                    parent_en=cur_en,
                    folder_type="season",
                    season_num=season_num,
                )
                child["clean_name"] = folder_result.display or child["name"]
                child["clean_name_cn"] = folder_result.cn
                child["clean_name_en"] = folder_result.en
                child["clean_name_original"] = folder_result.original

        # 视频的 clean_name
        if node.get("folder_type") in ("tv", "season", "movie") and node.get("videos"):
            for v in node["videos"]:
                existing_source = v.get("clean_name_source", "")
                if existing_source in ("manual", "nfo", "tmdb"):
                    continue
                if cur_cn or cur_en:
                    result = clean_from_filename(
                        v.get("file_name", ""),
                        folder_name=node.get("name", ""),
                        parent_cn=cur_cn,
                        parent_en=cur_en,
                        parent_original=cur_original,
                    )
                    if result.display:
                        # 只有算出来的值和已存的不同才写回并置脏标记。
                        # 否则每次请求目录树都会触发一次全库落盘 + 索引重建 + 完整度刷新。
                        if (v.get("clean_name") != result.display
                                or v.get("clean_name_cn") != result.cn
                                or v.get("clean_name_en") != result.en
                                or v.get("clean_name_original") != result.original):
                            v["clean_name"] = result.display
                            v["clean_name_cn"] = result.cn
                            v["clean_name_en"] = result.en
                            v["clean_name_original"] = result.original
                            library_dirty[0] = True

        for child in node.get("children", []):
            post_process(child, cat, cur_cn, cur_en, cur_original)
    post_process(root_node)

    def cleanup(node):
        node.pop("_child_index", None)
        for child in node.get("children", []):
            cleanup(child)

    cleanup(root_node)

    # 自愈持久化
    if library_dirty[0]:
        try:
            healed = {v["file_path"]: v for v in videos if v.get("file_path")}

            def _apply_healed(latest):
                """只把补全过的条目替换掉，其余沿用最新落盘内容。

                videos 是构树开始时读到的快照，直接整份写回会抹掉这期间
                别处新增的条目；反过来也不能把期间已删除的条目复活。
                """
                return [healed.get(v.get("file_path"), v) for v in latest]

            config_m.mutate_library(_apply_healed)
            logger.info("[tree] 自愈：已补全视频条目的结构化清洗名并持久化")
        except Exception as e:
            logger.warning(f"[tree] 自愈持久化失败: {e}")

    return root_node
