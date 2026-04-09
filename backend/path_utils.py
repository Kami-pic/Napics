import os

def normalize_path(path: str) -> str:
    """统一规范化路径：处理斜杠方向、大小写、UNC 路径。
    增加对 bytes 类型以及编码异常（如 Windows 网络盘乱码）的容错。
    """
    if not path:
        return ""
    
    # 处理可能的字节流
    if isinstance(path, bytes):
        for enc in ["utf-8", "gbk", "shift-jis"]:
            try:
                path = path.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if isinstance(path, bytes):
            return "" # 解码失败

    # 1. 统一斜杠
    p = path.replace("/", os.sep).replace("\\", os.sep)
    # 2. 规范化
    try:
        p = os.path.normpath(p)
        # Windows UNC 路径纠偏（\\server\share 形式）
        return os.path.normcase(p)
    except Exception:
        return p.lower()
