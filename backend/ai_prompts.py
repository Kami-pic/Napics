"""AI prompt 模板集中管理。
每个场景独立一个函数，返回 messages 列表，方便调优和版本控制。
"""
import json
from typing import List, Optional


# ── 场景 1：文件名智能解析 ──

EXTRACT_EPISODE_SCHEMA = {
    "clean_title": {"type": str, "required": True},
    "year": {"type": str, "required": False},
    "season": {"type": int, "required": False},
    "episode": {"type": int, "required": False},
    "absolute_episode": {"type": int, "required": False},
}

EXTRACT_EPISODE_BATCH_SCHEMA = {
    "results": {"type": list, "required": True},
}


def prompt_extract_episode(filename: str) -> list:
    """从单个乱码文件名提取结构化信息"""
    return [
        {
            "role": "system",
            "content": "你是一个视频文件名解析器。只返回合法的 JSON 对象，不要任何解释。"
        },
        {
            "role": "user",
            "content": f"""请从以下文件名中提取信息。

文件名：{filename}

返回格式（严格遵守）：
{{"clean_title": "作品名（中文优先）", "year": "年份或null", "season": 季号数字或null, "episode": 分集号数字或null, "absolute_episode": 绝对集数数字或null}}

规则：
- 如果文件名有明确的 S01E01 格式，填 season 和 episode
- 如果只有一个数字且可能是集数，填 absolute_episode
- 如果无法判断，对应字段必须填 null，绝不猜测
- clean_title 必须是干净的作品名，去掉字幕组、编码、分辨率等标签
- 如果完全无法识别作品名，clean_title 填空字符串"""
        }
    ]


def prompt_extract_episode_batch(filenames: list) -> list:
    """批量文件名解析（一次最多 10 个）"""
    file_list = "\n".join(f"{i+1}. {fn}" for i, fn in enumerate(filenames))
    return [
        {
            "role": "system",
            "content": "你是一个视频文件名解析器。只返回合法的 JSON 对象，不要任何解释。"
        },
        {
            "role": "user",
            "content": f"""请从以下文件名列表中逐个提取信息。

文件名列表：
{file_list}

返回格式（严格遵守）：
{{"results": [
  {{"index": 1, "clean_title": "作品名", "year": "年份或null", "season": null, "episode": null, "absolute_episode": null}},
  ...
]}}

规则：
- 每个文件名独立解析，index 对应上面的序号
- 如果文件名有明确的 S01E01 格式，填 season 和 episode
- 如果只有一个数字且可能是集数，填 absolute_episode
- 如果无法判断，对应字段必须填 null，绝不猜测
- clean_title 必须是干净的作品名，去掉字幕组、编码、分辨率等标签
- 如果完全无法识别作品名，clean_title 填空字符串"""
        }
    ]


# ── 场景 2：刮削候选智能匹配 ──

SELECT_CANDIDATE_SCHEMA = {
    "selected_index": {"type": int, "required": True},
    "confidence": {"type": str, "required": True},
    "reason": {"type": str, "required": True},
}


def prompt_select_scrape_candidate(
    folder_name: str,
    file_list: list,
    candidates: list
) -> list:
    """从 TMDB 刮削候选中选择最佳匹配"""
    # 简化候选信息，节省 token
    simplified = []
    for i, c in enumerate(candidates[:10]):
        simplified.append({
            "index": i,
            "title": c.get("title", ""),
            "original_title": c.get("original_title", ""),
            "year": c.get("year", ""),
            "overview": (c.get("overview", "") or "")[:100],
            "media_type": c.get("media_type", ""),
        })

    files_str = "\n".join(f"  - {f}" for f in file_list[:15])

    return [
        {
            "role": "system",
            "content": "你是一个影视元数据匹配专家。只返回合法的 JSON 对象，不要任何解释。"
        },
        {
            "role": "user",
            "content": f"""请根据文件夹信息，从候选列表中选择最匹配的一项。

文件夹名：{folder_name}
文件夹内文件：
{files_str}

候选列表：
{json.dumps(simplified, ensure_ascii=False, indent=2)}

返回格式：
{{"selected_index": 候选序号, "confidence": "high"或"medium"或"low", "reason": "选择理由（一句话）"}}

规则：
- 根据文件夹名和文件列表判断这是什么影视作品
- 从候选中选择最匹配的，返回其 index
- confidence 判断标准：
  - high：文件夹名和候选标题高度吻合，年份也对得上
  - medium：标题基本匹配但有歧义（如同名不同版本）
  - low：不太确定，可能匹配错误
- 如果所有候选都不匹配，selected_index 填 -1，confidence 填 "low"
"""
        }
    ]


# ── 场景 3：媒体库健康诊断 ──

DIAGNOSIS_SCHEMA = {
    "health_score": {"type": int, "required": True},
    "priorities": {"type": list, "required": True},
    "summary": {"type": str, "required": True},
}


def prompt_library_diagnosis(stats: dict, issues: list) -> list:
    """媒体库健康诊断"""
    return [
        {
            "role": "system",
            "content": "你是一个 NAS 媒体库管理专家。只返回合法的 JSON 对象，不要任何解释。"
        },
        {
            "role": "user",
            "content": f"""分析媒体库状态，给出健康评分和改进建议。

统计：{json.dumps(stats, ensure_ascii=False)}

问题：{json.dumps(issues[:10], ensure_ascii=False)}

返回格式：{{"health_score": 0-100整数, "priorities": [{{"category": "类别", "severity": "high/medium/low", "count": 数量, "suggestion": "建议", "action": "batch_scrape/batch_upgrade/organize/cleanup/manual"}}], "summary": "100字内总结"}}

priorities 最多 5 条，按严重程度排序。"""
        }
    ]
