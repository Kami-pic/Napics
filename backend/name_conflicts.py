"""取名证据的冲突检测。

为什么需要这一层：取名的每个来源都会错 —— 下载来的文件名各式各样，NFO 也会
刮削错。以前的做法是给来源排座次（`NAME_SOURCE_PRIORITY`：manual 4 > nfo 3 >
parsed 1），谁的位次高谁说了算。问题是 `nfo` 只说明"数据存在哪儿"，不代表"有多准"：
库里 1992 条 `shadow_name_source=nfo` 里只有 28 条（1.4%）带外部 ID。
尺子本身不准，靠"换一把尺子去量"（A 错了用 B 校、B 错了用 A 校）只会互相打补丁。

这里的做法是把**证据采集**和**裁决**分开，中间插一层可判定的冲突检测：

- 证据彼此独立采集，互不校准：分集 NFO、目录级 NFO、作品级目录名、文件名里的序号
- 冲突检测只做能写成断言的比对，不做"哪个更可信"的猜测
- 全部一致 → 照常写入；出现冲突 → 仍写入当前最优候选，但打上 `name_conflicts`
  标记，让这条数据在 UI 上可被筛出、在整理时被拦下

裁决取舍（由实现者定，写在这里以免日后反复）：
1. **冲突时填候选而不是留空**。留空会让搜索和 UI 一起失去可用值，退化成"没名字"；
   填最优候选至少可用，标记保证它不会被当成可信数据悄悄沉淀下去。
2. **改磁盘的操作遇冲突必须拒绝**（见 renamer 里的 skip_reason）。名字错了可以改回来，
   文件被同名覆盖改不回来。
3. **扫描期不联网**。扫描已经被 ffprobe 拖得很慢，且离线可用是底线。
   带 tmdb_id 时用外部 ID 查权威名，只在用户显式点刮削/重新匹配时做。
"""
import logging
import os
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# 冲突类型
SEASON_MISMATCH = "nfo_season_vs_folder"      # NFO 的季号与目录名说的不一致
EPISODE_MISMATCH = "nfo_episode_vs_filename"  # NFO 的集号与文件名里的序号不一致
YEAR_MISMATCH = "nfo_year_vs_name"            # NFO 年份与文件名/目录名里的年份不一致
SIBLING_MISMATCH = "sibling_name_mismatch"    # 同一目录下各集算出的作品名互不相同

_YEAR_RE = re.compile(r'(19\d{2}|20\d{2})')


def _years_in(text: str) -> List[int]:
    return [int(y) for y in _YEAR_RE.findall(text or "")]


def detect_item_conflicts(file_path: str, file_name: str = "",
                          nfo: Optional[Dict] = None) -> List[str]:
    """单条视频的证据冲突。返回冲突类型列表，没有冲突返回空列表。

    只比对**两边都拿到了值**的项：缺一边不算冲突（缺失是常态，不是矛盾）。
    """
    from nfo_handler import read_video_nfo, work_folder_of
    from organizer import _get_season_number, parse_filename

    file_name = file_name or os.path.basename(file_path)
    if nfo is None:
        try:
            nfo = read_video_nfo(file_path)
        except Exception as e:
            logger.debug(f"[name_conflicts] 读 NFO 失败 {file_name}: {e}")
            nfo = None
    if not nfo:
        return []

    conflicts = []
    folder = os.path.dirname(file_path)
    parsed = parse_filename(file_name)

    # 季号：目录结构 vs NFO。实测军火女王 Season 02 目录里每集都写着 season=1
    dir_season = _get_season_number(os.path.basename(folder))
    nfo_season = nfo.get("season_number") or 0
    if dir_season and nfo_season and dir_season != nfo_season:
        conflicts.append(SEASON_MISMATCH)

    # 集号：文件名里的序号 vs NFO
    file_episode = parsed.get("episode")
    nfo_episode = nfo.get("episode_number") or 0
    if file_episode and nfo_episode and file_episode != nfo_episode:
        conflicts.append(EPISODE_MISMATCH)

    # 年份：容忍 1 年（上映年与发行年常差一年），超过就是对不上
    nfo_years = _years_in(str(nfo.get("year") or ""))
    name_years = _years_in(file_name) or _years_in(os.path.basename(work_folder_of(file_path)))
    if nfo_years and name_years:
        if min(abs(nfo_years[0] - y) for y in name_years) > 1:
            conflicts.append(YEAR_MISMATCH)

    return conflicts


def _episode_key(item: dict) -> str:
    """同一部作品的标识：取结构化清洗名的中文侧，没有就用英文侧"""
    return (item.get("clean_name_cn") or item.get("clean_name_en") or "").strip()


_SUFFIX_RE = re.compile(r'S\d+E\d+', re.I)


def _looks_like_episode(item: dict) -> bool:
    """这条是不是"某部剧的某一集"。

    判据用清洗名里的 SxxExx：散装电影目录（一个目录几十部不同的片）里每条名字
    本来就该不一样，不能拿"名字不一致"去说它有问题。
    """
    return bool(_SUFFIX_RE.search(item.get("clean_name") or ""))


def annotate_group_conflicts(items: List[dict]) -> int:
    """同目录一致性自检：同一目录下的多集，算出的作品名必须相同。

    算出各不相同的名字，说明取到的是**分集级**信息（实测军火女王一季 12 集拿到了
    「炎兔」「脉冲星」「奏出音乐的武器第一篇」…），整组都不可信。
    这个判据不依赖任何外部数据，纯粹是内部一致性。

    返回被标记的条目数。
    """
    groups: Dict[str, List[dict]] = {}
    for item in items:
        path = item.get("file_path") or ""
        if not path or not _looks_like_episode(item):
            continue
        groups.setdefault(os.path.dirname(path), []).append(item)

    marked = 0
    for folder, group in groups.items():
        if len(group) < 3:
            continue   # 两集看不出一致性，别误伤
        keys = {_episode_key(i) for i in group if _episode_key(i)}
        if len(keys) <= 1:
            continue
        logger.info(f"[name_conflicts] 同目录作品名不一致，{len(group)} 条标记存疑: {folder} -> {sorted(keys)[:4]}")
        for item in group:
            add_conflicts(item, [SIBLING_MISMATCH])
            marked += 1
    return marked


def add_conflicts(item: dict, conflicts: List[str]) -> None:
    """把冲突标记合并进条目。无冲突时把字段清掉，避免旧标记留着不走。"""
    if not conflicts:
        return
    existing = item.get("name_conflicts") or []
    merged = sorted(set(existing) | set(conflicts))
    item["name_conflicts"] = merged
    item["name_needs_review"] = True


def clear_conflicts(item: dict) -> None:
    """重算名字前先清掉旧标记，否则修好了标记还挂着"""
    item.pop("name_conflicts", None)
    item.pop("name_needs_review", None)
