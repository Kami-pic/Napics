import os
import logging
import json
import requests
from typing import List, Dict

logger = logging.getLogger(__name__)
class AIOrganizer:
    def __init__(self, config):
        self.api_key = config.get("openai_api_key")
        self.base_url = config.get("openai_base_url", "https://api.openai.com/v1")
        self.model = config.get("openai_model", "gpt-3.5-turbo")

    def get_suggestions(self, videos: List[Dict]) -> List[Dict]:
        """
        根据视频列表，请求 AI 给出整理建议。
        返回格式: [{"original_path": "...", "new_path": "...", "reason": "..."}]
        """
        if not self.api_key:
            return []

        # 简化数据，只传文件名和当前文件夹，节省 token
        simplify_list = [{"file_name": v["file_name"], "folder_name": v["folder_name"]} for v in videos]
        
        prompt = f"""
        你是一个专业的 NAS 影视整理专家。以下是我媒体库中一些命名混乱的文件。
        请根据文件名识别出这些电影/剧集，并给出整理建议。
        
        任务要求：
        1. 将同一系列或同一季的影片归入同一个文件夹。
        2. 文件夹命名格式建议为“中文名 (年份)”或“剧集名 第X季”。
        3. 请返回 JSON 格式数据，包含每个文件的 original_path (这里传入原文件名即可) 和 suggested_rel_path (建议的相对路径，包括新文件夹名和规范后的文件名)。
        4. 理由理由 (reason) 请简短。
        
        待处理文件列表：
        {json.dumps(simplify_list[:50], ensure_ascii=False)} 
        """

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "你是一个精确的 JSON 生成器，只返回合法的 JSON 数组。"},
                    {"role": "user", "content": prompt}
                ],
                "response_format": { "type": "json_object" } if "gpt-4" in self.model else None
            }
            
            resp = requests.post(f"{self.base_url}/chat/completions", headers=headers, json=payload, timeout=30)
            result = resp.json()
            content = result["choices"][0]["message"]["content"]
            
            # 尝试解析 JSON
            try:
                suggestions = json.loads(content)
                if isinstance(suggestions, dict) and "suggestions" in suggestions:
                    suggestions = suggestions["suggestions"]
                return suggestions
            except:
                # 简单正则清理或手动解析
                import re
                match = re.search(r"\[.*\]", content, re.DOTALL)
                if match:
                    return json.loads(match.group())
                return []
                
        except Exception as e:
            logger.error(f"AI Suggestion Error: {e}")
            return []

def organize_by_ai(config, videos):
    organizer = AIOrganizer(config)
    return organizer.get_suggestions(videos)


def ai_extract_episode(filename: str, config: dict) -> dict:
    """调用 LLM 从乱码文件名中提取结构化信息。
    AI 仅充当"高级提取器"，绝不允许捏造数据。
    返回 {"clean_name": str, "year": str|None, "season": int|None,
           "episode": int|None, "absolute_episode": int|None}
    失败返回 None。
    """
    api_key = config.get("openai_api_key")
    base_url = config.get("openai_base_url", "https://api.openai.com/v1")
    model = config.get("openai_model", "gpt-3.5-turbo")

    if not api_key:
        return None

    prompt = f"""你是一个视频文件名解析器。请从以下文件名中提取信息。
只返回 JSON，不要任何解释。

文件名：{filename}

返回格式（严格遵守）：
{{"clean_title": "作品名（中文优先）", "year": "年份或null", "season": 季号数字或null, "episode": 分集号数字或null, "absolute_episode": 绝对集数数字或null}}

规则：
- 如果文件名有明确的 S01E01 格式，填 season 和 episode
- 如果只有一个数字且可能是集数，填 absolute_episode
- 如果无法判断，对应字段填 null
- clean_title 必须是干净的作品名，去掉字幕组、编码、分辨率等标签"""

    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "你是一个精确的 JSON 生成器，只返回合法的 JSON 对象。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0
        }
        resp = requests.post(f"{base_url}/chat/completions",
                             headers=headers, json=payload, timeout=15)
        content = resp.json()["choices"][0]["message"]["content"]

        # 尝试从 markdown 代码块中提取 JSON
        import re

        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
        if json_match:
            content = json_match.group(1)

        result = json.loads(content)

        # 字段校验
        clean_title = result.get("clean_title", "")
        if not clean_title or len(clean_title) < 2:
            return None

        # 类型校验
        def _safe_int(v):
            if v is None:
                return None
            try:
                return int(v)
            except (ValueError, TypeError):
                return None

        return {
            "clean_name": clean_title,
            "year": str(result["year"]) if result.get("year") else None,
            "season": _safe_int(result.get("season")),
            "episode": _safe_int(result.get("episode")),
            "absolute_episode": _safe_int(result.get("absolute_episode")),
        }
    except Exception as e:
        logger.error(f"AI extract error: {e}")
        return None
