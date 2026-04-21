"""L1 文本处理模块 — 搜索匹配过滤的基石

提供文本标准化、语言检测、中英文分离、短名字判断、名称变体提取、
关键词清洗、分词等能力。所有匹配/搜索/过滤操作的前置处理。

对应技能文档：.kiro/skills/L1-text-processing.md
"""
import re
from typing import List, Dict, Optional


# ── 繁简转换映射（常见繁体字→简体字，覆盖影视标题高频字）──
# 完整转换建议用 OpenCC，这里只做高频字的轻量映射
_TRAD_TO_SIMP: Dict[str, str] = {
    "進": "进", "擊": "击", "國": "国", "語": "语", "東": "东",
    "車": "车", "門": "门", "開": "开", "關": "关", "電": "电",
    "視": "视", "機": "机", "書": "书", "學": "学", "長": "长",
    "動": "动", "畫": "画", "戰": "战", "鬥": "斗", "龍": "龙",
    "風": "风", "雲": "云", "飛": "飞", "馬": "马", "魚": "鱼",
    "鳥": "鸟", "黑": "黑", "點": "点", "體": "体", "發": "发",
    "對": "对", "從": "从", "時": "时", "間": "间", "過": "过",
    "還": "还", "後": "后", "無": "无", "與": "与", "島": "岛",
    "滅": "灭", "劍": "剑", "傳": "传", "說": "说", "話": "话",
    "記": "记", "號": "号", "園": "园", "場": "场", "夢": "梦",
    "愛": "爱", "歲": "岁", "歡": "欢", "氣": "气", "殺": "杀",
    "決": "决", "淚": "泪", "滿": "满", "燈": "灯", "獸": "兽",
    "環": "环", "異": "异", "當": "当", "監": "监", "盜": "盗",
    "碼": "码", "禮": "礼", "種": "种", "節": "节", "紅": "红",
    "線": "线", "練": "练", "義": "义", "聲": "声", "華": "华",
    "藝": "艺", "術": "术", "衛": "卫", "親": "亲", "計": "计",
    "設": "设", "論": "论", "護": "护", "變": "变", "讓": "让",
    "貓": "猫", "質": "质", "車": "车", "軍": "军", "輪": "轮",
    "運": "运", "選": "选", "鐵": "铁", "鑰": "钥", "閃": "闪",
    "陽": "阳", "險": "险", "雜": "杂", "靈": "灵", "響": "响",
    "頭": "头", "顯": "显", "飯": "饭", "駕": "驾", "驗": "验",
    "魔": "魔", "麗": "丽", "齊": "齐", "齒": "齿",
}


# ── 英文停用词（不参与匹配和分词）──
_STOP_WORDS = frozenset({
    "the", "a", "an", "of", "in", "on", "at", "to", "for",
    "is", "it", "and", "or", "but", "not", "no", "by", "with",
    "from", "as", "be", "was", "were", "been", "are", "am",
})


# ── 标点和特殊字符正则 ──
_PUNCT_RE = re.compile(
    r'[\s\-·・、，。.,:;：；！!？?（）()「」『』【】\[\]\/\\～~＝="\'\"&＆_{}|<>@#$%^*+`]'
)

# ── 年份正则 ──
_YEAR_RE = re.compile(r'\s*[\(\[（]?((?:19|20)\d{2})[\)\]）]?\s*$')
_YEAR_INLINE_RE = re.compile(r'[\(\[（]((?:19|20)\d{2})[\)\]）]')

# ── 括号内容正则（含括号本身）──
_BRACKET_RE = re.compile(r'[\[\(（【][^\]\)）】]*[\]\)）】]')

# ── 中文字符正则 ──
_CJK_RE = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf]+')

# ── 日文假名正则 ──
_KANA_RE = re.compile(r'[\u3040-\u309f\u30a0-\u30ff]')

# ── 韩文正则 ──
_HANGUL_RE = re.compile(r'[\uac00-\ud7af]')

# ── 副标题分隔符 ──
_SUBTITLE_SEPS = ['：', ':', ' - ', '～', '~']

# ── 中文季集号正则 ──
_CN_SEASON_RE = re.compile(r'第(\d+)季')
_CN_EPISODE_RE = re.compile(r'第(\d+)集')

# ── 中文数字季号正则（第一季~第二十季）──
_CN_NUM_MAP = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7,
               "八": 8, "九": 9, "十": 10, "十一": 11, "十二": 12, "十三": 13,
               "十四": 14, "十五": 15, "十六": 16, "十七": 17, "十八": 18,
               "十九": 19, "二十": 20}
_CN_NUM_SEASON_RE = re.compile(r'第([一二三四五六七八九十]+)季')
_CN_NUM_EPISODE_RE = re.compile(r'第([一二三四五六七八九十]+)集')

# ── 尾部续作标记正则（"2"/"3"/"II"/"III" 等紧跟在标题末尾）──
_SEQUEL_SUFFIX_RE = re.compile(
    r'\s*(?:'
    r'[2-9]|[IⅡⅢⅣⅤⅥⅦⅧⅨⅩ]{1,4}'  # 阿拉伯数字 2-9 或罗马数字
    r')\s*$'
)

# ── 特殊标记后缀（剧场版/OVA/SP 等）──
_SPECIAL_SUFFIX_RE = re.compile(
    r'\s*(?:剧场版|劇場版|OVA|OAD|SP|特别篇|番外篇|总集篇|完结篇)\s*$',
    re.I
)


def _trad_to_simp(s: str) -> str:
    """轻量繁简转换（高频字映射）"""
    return "".join(_TRAD_TO_SIMP.get(ch, ch) for ch in s)


def _fullwidth_to_halfwidth(s: str) -> str:
    """全角→半角"""
    out = []
    for ch in s:
        cp = ord(ch)
        if 0xFF01 <= cp <= 0xFF5E:
            out.append(chr(cp - 0xFEE0))
        elif cp == 0x3000:  # 全角空格
            out.append(' ')
        else:
            out.append(ch)
    return "".join(out)


# ════════════════════════════════════════
# 核心能力
# ════════════════════════════════════════

def normalize(text: str) -> str:
    """文本标准化：全角→半角 → 繁简转换 → 去标点 → 去空格 → 小写"""
    if not text:
        return ""
    s = _fullwidth_to_halfwidth(text)
    s = _trad_to_simp(s)
    s = _PUNCT_RE.sub("", s)
    return s.lower()


def detect_language(text: str) -> str:
    """检测文本主要语言，返回 cn/en/jp/ko/mixed/none"""
    if not text:
        return "none"
    # 去掉数字和常见格式字符后判断
    cleaned = re.sub(r'[0-9a-zA-Z\s\.\-_\[\](){}]', '', text)
    if not cleaned:
        # 纯数字/英文/格式字符
        # 检查是否为纯格式字符串（如 S01E05、02.rmvb）
        has_alpha = bool(re.search(r'[a-zA-Z]', text))
        # 格式字符串模式：S01E05、EP01、720p 等
        is_format = bool(re.match(r'^[A-Za-z]?\d+[A-Za-z]?\d*[pPiI]?(\.\w+)?$', text.strip()))
        if is_format or not has_alpha:
            return "none"
        return "en"

    has_kana = bool(_KANA_RE.search(text))
    has_hangul = bool(_HANGUL_RE.search(text))
    has_cjk = bool(_CJK_RE.search(text))
    has_alpha = bool(re.search(r'[a-zA-Z]{2,}', text))  # 至少 2 个连续字母才算英文

    if has_kana:
        return "jp"
    if has_hangul:
        return "ko"
    if has_cjk and has_alpha:
        return "mixed"
    if has_cjk:
        return "cn"
    if has_alpha:
        return "en"
    return "none"


def split_by_language(text: str) -> Dict[str, str]:
    """从混合文本中提取中文部分和英文部分
    数字紧邻中文时归入中文（如 "91天" → cn="91天"，"JOJO的奇妙冒险" → cn="JOJO的奇妙冒险"）
    独立的英文单词归入英文（如 "Attack on Titan" → en="Attack on Titan"）
    """
    if not text:
        return {"cn": "", "en": ""}

    # 策略：按 token 分组，判断每个 token 归属
    # token 类型：CJK 字符、英文单词、数字、其他
    # 规则：
    #   - CJK 字符 → cn
    #   - 英文单词（≥2 个连续字母）→ en
    #   - 数字：如果紧邻 CJK → cn，否则 → en
    #   - 单个字母（如 S、E）→ en

    # 用正则拆分为 token 序列，保留位置信息
    tokens = re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf]+|[a-zA-Z]+|[0-9]+|[^\u4e00-\u9fff\u3400-\u4dbfa-zA-Z0-9]+', text)

    cn_parts = []
    en_parts = []

    for i, tok in enumerate(tokens):
        is_cjk = bool(_CJK_RE.match(tok))
        is_alpha = bool(re.match(r'^[a-zA-Z]+$', tok))
        is_digit = bool(re.match(r'^[0-9]+$', tok))

        if is_cjk:
            cn_parts.append(tok)
        elif is_alpha:
            # 单个字母紧邻 CJK 时归入 cn（如 "JOJO的" 中的 JOJO）
            # 但独立的英文单词（前后都不是 CJK）归入 en
            prev_cjk = i > 0 and bool(_CJK_RE.match(tokens[i - 1]))
            next_cjk = i < len(tokens) - 1 and bool(_CJK_RE.match(tokens[i + 1]))
            if prev_cjk or next_cjk:
                cn_parts.append(tok)
            else:
                en_parts.append(tok)
        elif is_digit:
            # 数字紧邻 CJK 时归入 cn（如 "91天" 中的 91）
            prev_cjk = i > 0 and bool(_CJK_RE.match(tokens[i - 1]))
            next_cjk = i < len(tokens) - 1 and bool(_CJK_RE.match(tokens[i + 1]))
            if prev_cjk or next_cjk:
                cn_parts.append(tok)
            else:
                en_parts.append(tok)
        # 其他字符（空格、标点等）跳过

    cn = "".join(cn_parts)
    en = " ".join(en_parts).strip()
    # 清理英文部分多余空格
    en = re.sub(r'\s+', ' ', en).strip()

    return {"cn": cn, "en": en}


def is_short_name(text: str) -> bool:
    """判断是否为短名字（需要更严格的匹配策略）"""
    if not text:
        return True

    # 提取中文字符
    cn_chars = re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf]', text)
    # 提取英文部分（去掉数字）
    en_part = re.sub(r'[\u4e00-\u9fff\u3400-\u4dbf\d\s\.\-_\[\](){}]', '', text).strip()

    if cn_chars:
        # 有中文：按中文字符数判断
        return len(cn_chars) <= 2
    elif en_part:
        # 纯英文：按字符数判断
        return len(en_part) <= 5
    else:
        # 纯数字/符号：不算短名字（如 "2001"）
        return False


def extract_variants(text: str) -> List[str]:
    """从标题中提取所有可能的搜索/匹配变体"""
    if not text:
        return []

    variants = [text]  # 原始标题
    seen = {text}

    def _add(v: str):
        v = v.strip()
        if v and v not in seen:
            seen.add(v)
            variants.append(v)

    # 去副标题
    for sep in _SUBTITLE_SEPS:
        if sep in text:
            main = text.split(sep, 1)[0].strip()
            if main:
                _add(main)
            break

    # 去年份后缀
    no_year = _YEAR_RE.sub("", text).strip()
    if no_year and no_year != text:
        _add(no_year)

    # 去括号内容（含年份、分辨率等）
    no_brackets = _BRACKET_RE.sub("", text).strip()
    no_brackets = re.sub(r'\s+', ' ', no_brackets).strip()
    if no_brackets and no_brackets != text:
        _add(no_brackets)

    # 中英文分离
    parts = split_by_language(text)
    if parts["cn"]:
        _add(parts["cn"])
    if parts["en"]:
        _add(parts["en"])

    # 季集号标准化（阿拉伯数字）
    m = _CN_SEASON_RE.search(text)
    if m:
        base = _CN_SEASON_RE.sub("", text).strip()
        if base:
            _add(base)
            _add(f"{base} S{int(m.group(1)):02d}")

    # 季集号标准化（中文数字：第五季 → 去掉 / 转 S05）
    m2 = _CN_NUM_SEASON_RE.search(text)
    if m2:
        base = _CN_NUM_SEASON_RE.sub("", text).strip()
        if base:
            _add(base)
            num = _CN_NUM_MAP.get(m2.group(1))
            if num:
                _add(f"{base} S{num:02d}")

    # 去掉剧场版/OVA/SP 等特殊标记后缀
    no_special = _SPECIAL_SUFFIX_RE.sub("", text).strip()
    if no_special and no_special != text:
        _add(no_special)

    # 去掉续作数字后缀（"黑客帝国3" → "黑客帝国"，"速度与激情9" → "速度与激情"）
    no_sequel = _SEQUEL_SUFFIX_RE.sub("", text).strip()
    if no_sequel and no_sequel != text and len(no_sequel) >= 2:
        _add(no_sequel)

    return variants


def clean_keyword(text: str, blacklist: Optional[List[str]] = None) -> str:
    """搜索前关键词清洗"""
    if not text:
        return ""

    s = text

    # 黑名单词清理
    if blacklist:
        for word in blacklist:
            s = re.sub(r'\b' + re.escape(word) + r'\b', '', s, flags=re.IGNORECASE)
            # 也处理方括号内的
            s = re.sub(r'\[' + re.escape(word) + r'\]', '', s, flags=re.IGNORECASE)

    # 去括号内容
    s = _BRACKET_RE.sub("", s)

    # 去年份后缀
    s = _YEAR_RE.sub("", s).strip()

    # 中文季号标准化（阿拉伯数字）
    m = _CN_SEASON_RE.search(s)
    if m:
        s = _CN_SEASON_RE.sub(f"S{int(m.group(1)):02d}", s)

    # 中文季号标准化（中文数字）
    m2 = _CN_NUM_SEASON_RE.search(s)
    if m2:
        num = _CN_NUM_MAP.get(m2.group(1))
        if num:
            s = _CN_NUM_SEASON_RE.sub(f"S{num:02d}", s)

    m = _CN_EPISODE_RE.search(s)
    if m:
        s = _CN_EPISODE_RE.sub(f"E{int(m.group(1)):02d}", s)

    # 中文集号标准化（中文数字）
    m2 = _CN_NUM_EPISODE_RE.search(s)
    if m2:
        num = _CN_NUM_MAP.get(m2.group(1))
        if num:
            s = _CN_NUM_EPISODE_RE.sub(f"E{num:02d}", s)

    # 去特殊字符（保留字母、数字、CJK、空格）
    s = re.sub(r'[^\w\u4e00-\u9fff\u3400-\u4dbf\s]', '', s)

    # 合并多余空格
    s = re.sub(r'\s+', ' ', s).strip()

    return s


def tokenize(text: str) -> List[str]:
    """分词：英文按空格+去停用词，中文按字符拆分"""
    if not text:
        return []

    parts = split_by_language(text)
    tokens = []

    # 英文分词
    if parts["en"]:
        for word in parts["en"].lower().split():
            # 去掉非字母数字
            word = re.sub(r'[^a-z0-9]', '', word)
            if word and word not in _STOP_WORDS:
                tokens.append(word)

    # 中文按字符拆分
    if parts["cn"]:
        for ch in parts["cn"]:
            tokens.append(ch)

    return tokens


def process_text(text: str, blacklist: Optional[List[str]] = None) -> Dict:
    """统一处理入口，输出标准化结构供 L2/L3/L4 使用"""
    if not text:
        return {
            "original": "", "normalized": "", "language": "none",
            "cn": "", "en": "", "is_short_name": True,
            "variants": [], "tokens": [], "clean_keyword": "",
        }

    parts = split_by_language(text)
    lang = detect_language(text)
    # 短名字判断用中文部分（如果有），否则用英文部分
    check_name = parts["cn"] if parts["cn"] else parts["en"]

    return {
        "original": text,
        "normalized": normalize(text),
        "language": lang,
        "cn": parts["cn"],
        "en": parts["en"],
        "is_short_name": is_short_name(check_name),
        "variants": extract_variants(text),
        "tokens": tokenize(text),
        "clean_keyword": clean_keyword(text, blacklist=blacklist),
    }
