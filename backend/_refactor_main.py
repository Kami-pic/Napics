"""
自动拆分 main.py 为模块化路由文件。
运行方式：cd backend && python _refactor_main.py

策略：
1. 解析 main.py，按 @app.get/@app.post/@app.delete 分割路由块
2. 按路径前缀分配到不同路由文件
3. 生成 routes/*.py（用 APIRouter）
4. 生成新 main.py（薄壳 + include_router）
5. 验证：对比新旧 app 的路由集合是否完全一致
"""
import re
import os
import sys
import textwrap

MAIN_PY = "main.py"
BACKUP = "main.py.refactor_backup"

# ── 路由分配规则：路径前缀 → 文件名 ──
ROUTE_MAP = [
    # (前缀列表, 目标文件名, 标签)
    (["/scan", "/sync", "/library"], "library", "媒体库管理"),
    (["/scrape", "/proxy/image"], "scrape", "刮削与元数据"),
    (["/media/shadow-name", "/media/info", "/config/indexers"], "scrape", "刮削与元数据"),
    (["/organize", "/analyze", "/rename"], "organize", "整理与分析"),
    (["/api/search", "/search"], "search", "搜索"),
    (["/alist"], "search", "搜索"),
    (["/download", "/batch-search", "/batch-download"], "download", "下载管理"),
    (["/config", "/no-scrape", "/cache", "/backup", "/restore"], "config", "配置管理"),
    (["/douban", "/add-media"], "discover", "发现与推荐"),
    (["/movie/poster"], "discover", "发现与推荐"),
    (["/recycle-bin", "/torrent-blacklist", "/analysis", "/api/system", "/api/config", "/api/"], "system", "系统运维"),
    (["/batch_manage", "/play", "/ai/"], "tools", "杂项工具"),
]

def match_route_file(path: str) -> str:
    """根据路径匹配目标路由文件"""
    for prefixes, filename, _ in ROUTE_MAP:
        for prefix in prefixes:
            if path.startswith(prefix):
                return filename
    return "misc"


def parse_main_py():
    """解析 main.py，提取：
    - header: imports + 全局初始化（到第一个 @app 之前）
    - routes: [(method, path, func_name, code_block, line_start), ...]
    - helpers: 非路由的顶层函数/类（在路由之间的）
    """
    with open(MAIN_PY, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # 找所有 @app.xxx 装饰器的行号
    route_pattern = re.compile(r'^@app\.(get|post|delete|put|patch)\("([^"]+)"')
    
    # 第一遍：标记所有路由起始行
    route_starts = []  # [(line_idx, method, path)]
    for i, line in enumerate(lines):
        m = route_pattern.match(line.strip())
        if m:
            route_starts.append((i, m.group(1).upper(), m.group(2)))

    if not route_starts:
        print("ERROR: 没有找到任何路由！")
        sys.exit(1)

    # header = 第一个路由之前的所有内容
    first_route_line = route_starts[0][0]
    header_lines = lines[:first_route_line]

    # 提取每个路由块（从 @app.xxx 到下一个 @app.xxx 或顶层定义之前）
    # 但要注意：路由之间可能有 helper 函数、类定义等
    
    blocks = []  # [(type, content, route_info)]
    # type: "route" | "helper"
    # route_info: (method, path, func_name) or None
    
    for idx, (line_idx, method, path) in enumerate(route_starts):
        # 确定块的结束行
        if idx + 1 < len(route_starts):
            next_start = route_starts[idx + 1][0]
        else:
            # 最后一个路由：到文件末尾（但排除 if __name__ 块）
            next_start = len(lines)
            for j in range(line_idx + 1, len(lines)):
                if lines[j].strip().startswith('if __name__'):
                    next_start = j
                    break

        # 提取路由函数名
        func_name = ""
        for j in range(line_idx, min(line_idx + 5, len(lines))):
            fm = re.match(r'^(?:async\s+)?def\s+(\w+)', lines[j].strip())
            if fm:
                func_name = fm.group(1)
                break

        # 向上查找：路由装饰器之前可能有连续的装饰器或空行
        block_start = line_idx
        # 向上找连续的装饰器
        while block_start > 0 and (lines[block_start - 1].strip().startswith('@') or lines[block_start - 1].strip() == ''):
            if lines[block_start - 1].strip().startswith('@'):
                block_start -= 1
            elif lines[block_start - 1].strip() == '' and block_start - 2 >= 0 and lines[block_start - 2].strip().startswith('@'):
                block_start -= 1
            else:
                break

        # 在当前路由块和下一个路由块之间，可能有 helper 代码
        # 找到当前路由函数的结束（下一个顶层定义或下一个路由）
        route_func_end = next_start
        
        # 提取当前路由块
        route_code = "".join(lines[block_start:route_func_end])
        
        blocks.append({
            "type": "route",
            "method": method,
            "path": path,
            "func_name": func_name,
            "code": route_code,
            "line_start": block_start,
            "line_end": route_func_end,
        })

    # if __name__ 块
    main_block = ""
    for i, line in enumerate(lines):
        if line.strip().startswith('if __name__'):
            main_block = "".join(lines[i:])
            break

    return header_lines, blocks, main_block


def generate_route_file(filename: str, blocks: list) -> str:
    """生成单个路由文件的内容"""
    # 收集这个文件需要的所有 import
    code_combined = "\n".join(b["code"] for b in blocks)
    
    content = f'"""\n路由模块：{filename}\n"""\n'
    content += "import os\nimport json\nimport re\nimport time\nimport asyncio\nimport shutil\nimport requests\nimport subprocess\nimport sys\nimport threading\n"
    content += "from typing import List, Optional, Dict\n"
    content += "from fastapi import APIRouter, HTTPException, UploadFile, File\n"
    content += "from fastapi.responses import StreamingResponse, FileResponse, Response\n"
    content += "from pydantic import BaseModel\n\n"
    content += "from shared import (\n"
    content += "    config_m, shadow_m, indexer_m, torrent_bl, analysis_cache,\n"
    content += "    _get_download_manager, _get_pan_search_service, _get_recycle_bin, _get_file_relocator,\n"
    content += "    _tmdb_client, get_clients,\n"
    content += "    _get_category_from_path, _is_top_category, _sync_library_paths, _update_clean_names_after_scrape,\n"
    content += ")\n"
    content += "import scanner, searcher, downloader, tmdb_client, config_manager\n"
    content += "import ai_organizer, douban_client, bangumi_client, scraper, organizer, analyzer\n"
    content += "from organize_history import history_m\n"
    content += "from global_filter import GlobalFilter\n"
    content += "from download_manager import DownloadManager, DownloadTask\n\n"
    content += f'router = APIRouter()\n\n'

    for b in blocks:
        # 替换 @app.xxx 为 @router.xxx
        code = b["code"]
        code = re.sub(r'@app\.(get|post|delete|put|patch)\(', r'@router.\1(', code)
        content += code
        if not code.endswith("\n"):
            content += "\n"

    return content


def generate_new_main(route_files: list) -> str:
    """生成新的 main.py（薄壳）"""
    content = '"""\nNAS Video Upgrader API — 模块化入口\n路由按业务域拆分到 routes/ 目录下。\n"""\n'
    content += "import os\nimport sys\n\n"
    content += "# 确保 backend/ 在 sys.path\n"
    content += "_dir = os.path.dirname(os.path.abspath(__file__))\n"
    content += "if _dir not in sys.path:\n"
    content += "    sys.path.insert(0, _dir)\n\n"
    content += "# Windows stdout 编码修复\n"
    content += "if sys.platform == 'win32':\n"
    content += "    try:\n"
    content += "        import io\n"
    content += "        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')\n"
    content += "        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')\n"
    content += "    except Exception:\n"
    content += "        pass\n\n"
    content += "from fastapi import FastAPI\n"
    content += "from fastapi.middleware.cors import CORSMiddleware\n\n"
    
    # 导入路由
    for rf in sorted(set(route_files)):
        content += f"from routes.{rf} import router as {rf}_router\n"
    
    content += "\napp = FastAPI(title='NAS Video Upgrader API')\n\n"
    content += "app.add_middleware(\n"
    content += "    CORSMiddleware,\n"
    content += "    allow_origins=['*'],\n"
    content += "    allow_credentials=True,\n"
    content += "    allow_methods=['*'],\n"
    content += "    allow_headers=['*'],\n"
    content += ")\n\n"
    content += "# 注册所有路由\n"
    for rf in sorted(set(route_files)):
        content += f"app.include_router({rf}_router)\n"
    
    content += "\n\n@app.get('/')\ndef read_root():\n    return {'message': 'NAS Video Upgrader API is running'}\n\n"
    content += "\nif __name__ == '__main__':\n"
    content += "    import uvicorn\n"
    content += "    uvicorn.run('main:app', host='127.0.0.1', port=8000, reload=False)\n"
    
    return content


def verify_routes():
    """验证新旧 main.py 的路由集合完全一致"""
    print("\n=== 验证路由一致性 ===")
    
    # 从旧 main.py 提取路由
    old_routes = set()
    with open(BACKUP, "r", encoding="utf-8") as f:
        for line in f:
            m = re.match(r'\s*@app\.(get|post|delete|put|patch)\("([^"]+)"', line.strip())
            if m:
                old_routes.add((m.group(1).upper(), m.group(2)))
    
    # 从新 main.py 加载 app 并提取路由
    # 用 import 的方式加载
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    # 从路由文件提取
    new_routes = set()
    routes_dir = os.path.join(os.path.dirname(__file__), "routes")
    for fname in os.listdir(routes_dir):
        if fname.endswith(".py") and fname != "__init__.py":
            fpath = os.path.join(routes_dir, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                for line in f:
                    m = re.match(r'\s*@router\.(get|post|delete|put|patch)\("([^"]+)"', line.strip())
                    if m:
                        new_routes.add((m.group(1).upper(), m.group(2)))
    
    # 加上 main.py 自身的路由（健康检查）
    with open("main.py", "r", encoding="utf-8") as f:
        for line in f:
            m = re.match(r"\s*@app\.(get|post|delete|put|patch)\(['\"]([^'\"]+)['\"]", line.strip())
            if m:
                new_routes.add((m.group(1).upper(), m.group(2)))
    
    # 对比
    missing = old_routes - new_routes
    extra = new_routes - old_routes
    
    print(f"旧 main.py 路由数: {len(old_routes)}")
    print(f"新模块化路由数: {len(new_routes)}")
    
    if missing:
        print(f"\n❌ 缺失 {len(missing)} 个路由:")
        for m, p in sorted(missing):
            print(f"  {m} {p}")
    
    if extra:
        print(f"\n⚠️ 多出 {len(extra)} 个路由:")
        for m, p in sorted(extra):
            print(f"  {m} {p}")
    
    if not missing and not extra:
        print("✅ 路由完全一致！")
        return True
    return False


def main():
    if not os.path.exists(MAIN_PY):
        print(f"ERROR: {MAIN_PY} 不存在")
        sys.exit(1)

    print("=== 解析 main.py ===")
    header_lines, blocks, main_block = parse_main_py()
    print(f"  header: {len(header_lines)} 行")
    print(f"  路由块: {len(blocks)} 个")

    # 分配路由到文件
    file_blocks = {}  # filename → [blocks]
    for b in blocks:
        target = match_route_file(b["path"])
        file_blocks.setdefault(target, []).append(b)

    print("\n=== 路由分配 ===")
    for fname, blist in sorted(file_blocks.items()):
        paths = [f"{b['method']} {b['path']}" for b in blist]
        print(f"  routes/{fname}.py: {len(blist)} 个路由")
        for p in paths:
            print(f"    {p}")

    # 备份旧 main.py
    if not os.path.exists(BACKUP):
        import shutil
        shutil.copy2(MAIN_PY, BACKUP)
        print(f"\n  备份: {MAIN_PY} → {BACKUP}")

    # 生成路由文件
    os.makedirs("routes", exist_ok=True)
    # 确保 __init__.py 存在
    init_path = os.path.join("routes", "__init__.py")
    if not os.path.exists(init_path):
        with open(init_path, "w") as f:
            f.write("# 路由模块包\n")

    for fname, blist in file_blocks.items():
        content = generate_route_file(fname, blist)
        fpath = os.path.join("routes", f"{fname}.py")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  生成: {fpath} ({len(blist)} 个路由)")

    # 生成新 main.py
    route_files = list(file_blocks.keys())
    new_main = generate_new_main(route_files)
    with open(MAIN_PY, "w", encoding="utf-8") as f:
        f.write(new_main)
    print(f"\n  生成新 main.py")

    # 验证
    ok = verify_routes()
    
    if ok:
        print("\n=== 拆分完成 ✅ ===")
        print("测试启动: python -m uvicorn main:app --host 127.0.0.1 --port 8000")
    else:
        print("\n=== 路由不一致，请检查 ❌ ===")
        print(f"旧文件备份在: {BACKUP}")
        print("恢复: copy main.py.refactor_backup main.py")


if __name__ == "__main__":
    main()
