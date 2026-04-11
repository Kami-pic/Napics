"""
路由模块：poster — 海报管理 + 图片代理
从 routes/scrape.py 拆分而来
"""
import os
import re
import requests
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse, FileResponse, Response

from shared import config_m

router = APIRouter()


@router.get("/proxy/image")
def proxy_image(url: str):
    """代理外部图片请求（绕过防盗链 + 走 HTTP 代理）"""
    try:
        headers = {"Referer": "https://movie.douban.com/", "User-Agent": "Mozilla/5.0"}
        proxies = None
        http_proxy = getattr(config_m.config, 'http_proxy', '') or ''
        if http_proxy:
            proxies = {"http": http_proxy, "https": http_proxy}
        resp = requests.get(url, headers=headers, stream=True, timeout=10, proxies=proxies)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "image/jpeg")
        from fastapi.responses import Response
        return Response(content=resp.content, media_type=content_type,
                        headers={"Cache-Control": "public, max-age=86400"})
    except Exception:
        raise HTTPException(status_code=404, detail="Image fetch failed")


@router.get("/scrape/poster")
def get_local_poster(path: str, cover: bool = False):
    """返回本地海报文件或回跳到在线 TMDB 海报"""
    from fastapi.responses import Response, RedirectResponse
    from fastapi import HTTPException
    import os
    import re

    def _poster_response(file_path: str):
        with open(file_path, "rb") as f:
            content = f.read()
        ext = os.path.splitext(file_path)[1].lower()
        mt = "image/png" if ext == ".png" else "image/jpeg"
        # 允许浏览器缓存海报 1 小时，前端通过 _t= 参数做缓存失效
        return Response(content=content, media_type=mt,
                        headers={"Cache-Control": "public, max-age=3600"})

    # 1. 聚合容器模式
    if cover:
        if os.path.isdir(path):
            for name in ["cover.jpg", "cover.png"]:
                p = os.path.join(path, name)
                if os.path.exists(p):
                    return _poster_response(p)
        raise HTTPException(status_code=404, detail="No cover found")

    # 2. 物理路径查找
    if os.path.isdir(path):
        # 2a. 标准文件夹级海报
        for name in ["poster.jpg", "poster.png", "folder.jpg", "cover.jpg"]:
            p = os.path.join(path, name)
            if os.path.exists(p):
                return _poster_response(p)
        
        # 2b. 季文件夹：查找 seasonXX-poster.jpg，或 fallback 到父目录
        folder_name = os.path.basename(path)
        season_match = re.search(r'(?:S(\d+)|第(\d+)季|Season\s*(\d+))', folder_name, re.I)
        if season_match:
            sn = season_match.group(1) or season_match.group(2) or season_match.group(3)
            for fmt in [f"season{sn.zfill(2)}-poster.jpg", f"season{sn}-poster.jpg"]:
                p = os.path.join(path, fmt)
                if os.path.exists(p):
                    return _poster_response(p)
            # 季文件夹没有自己的封面：fallback 到父目录的 poster
            parent = os.path.dirname(path)
            if parent and os.path.isdir(parent):
                for name in ["poster.jpg", "poster.png"]:
                    p = os.path.join(parent, name)
                    if os.path.exists(p):
                        return _poster_response(p)
        
        # 2c. 非季文件夹：找 *-poster.jpg（视频同名封面）
        try:
            for f in os.listdir(path):
                fl = f.lower()
                if fl.endswith('-poster.jpg') or fl.endswith('-poster.png') or fl.endswith('-thumb.jpg'):
                    return _poster_response(os.path.join(path, f))
        except OSError:
            pass
    else:
        # 单文件模式：寻找同名海报
        base = os.path.splitext(path)[0]
        for ext in ["-poster.jpg", "-poster.png", "-thumb.jpg", ".jpg", ".png"]:
            p = base + ext
            if os.path.exists(p):
                return _poster_response(p)
        
        # 模糊回退 1：寻找文件夹内的标准海报
        folder = os.path.dirname(path)
        for name in ["poster.jpg", "poster.png", "folder.jpg", "cover.jpg"]:
            p = os.path.join(folder, name)
            if os.path.exists(p):
                return _poster_response(p)
        
        # 模糊回退 2：高精度关键词匹配（处理重命名及大杂烩目录）
        try:
            items = os.listdir(folder)
            v_name = os.path.splitext(os.path.basename(path))[0].lower()
            keywords = [w for w in re.split(r'[^a-zA-Z0-9\u4e00-\u9fff]', v_name) if len(w) >= 2]
            
            if not keywords:
                # 兜底：如果目录下只有一个视频，直接认领
                video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".ts", ".m4v"}
                vids = [f for f in items if os.path.splitext(f)[1].lower() in video_exts]
                if len(vids) == 1:
                    for f in items:
                        if f.lower().endswith(("-poster.jpg", "-poster.png", "poster.jpg", "poster.png")):
                            return _poster_response(os.path.join(folder, f))
            else:
                best_match = None
                max_score = 0
                for f in items:
                    fl = f.lower()
                    if fl.endswith(("-poster.jpg", "-poster.png", "-thumb.jpg", "poster.jpg", "poster.png")):
                        score = sum(1 for k in keywords if k in fl)
                        if score > max_score:
                            max_score = score
                            best_match = f
                
                # 匹配门槛
                if best_match and (max_score >= 2 or max_score >= len(keywords) * 0.5):
                    return _poster_response(os.path.join(folder, best_match))
                
        except OSError:
            pass

    raise HTTPException(status_code=404, detail="No poster found")


@router.post("/scrape/upload-poster")
async def upload_poster(path: str, file: UploadFile = File(...), cover: bool = False):
    """手动上传海报到指定文件夹。cover=True 时写入 cover.jpg（聚合容器独立封面）"""
    folder = path if os.path.isdir(path) else os.path.dirname(path)
    if not os.path.isdir(folder):
        raise HTTPException(status_code=404, detail="Folder not found")
    
    ext = os.path.splitext(file.filename or "poster.jpg")[1] or ".jpg"
    # 视频文件：写同名 poster
    if not os.path.isdir(path) and os.path.isfile(path):
        base = os.path.splitext(path)[0]
        target = base + f"-poster{ext}"
    else:
        filename = f"cover{ext}" if cover else f"poster{ext}"
        target = os.path.join(folder, filename)
    content = await file.read()
    with open(target, "wb") as f:
        f.write(content)
    return {"status": "ok", "path": target}


@router.post("/scrape/poster-url")
def set_poster_from_url(path: str, url: str, cover: bool = False):
    """通过 URL 拉取海报保存到本地。cover=True 时写入 cover.jpg（聚合容器独立封面）"""
    try:
        resp = requests.get(url, stream=True, timeout=15)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        ext = ".jpg"
        if "png" in content_type:
            ext = ".png"
        
        if os.path.isdir(path):
            filename = f"cover{ext}" if cover else f"poster{ext}"
            target = os.path.join(path, filename)
        elif os.path.isfile(path):
            base = os.path.splitext(path)[0]
            target = base + f"-poster{ext}"
        else:
            raise HTTPException(status_code=404, detail="Path not found")
        
        with open(target, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
        return {"status": "ok", "path": target}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scrape/delete-poster")
def delete_poster(path: str):
    """删除本地海报 — 模拟 get_local_poster 的查找逻辑，找到实际显示的封面并删除"""
    deleted = []
    errors = []
    
    target_dir = path if os.path.isdir(path) else os.path.dirname(path)
    
    def _try_delete(filepath: str):
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
                deleted.append(filepath)
                return True
            except Exception as e:
                errors.append(f"{filepath}: {e}")
        return False
    
    if os.path.isdir(target_dir):
        folder_name = os.path.basename(target_dir)
        
        # 1. 当前目录标准封面
        for name in ["poster.jpg", "poster.png", "folder.jpg", "cover.jpg", "folder.png", "cover.png"]:
            _try_delete(os.path.join(target_dir, name))
        
        # 2. 当前目录 *-poster.jpg/png
        try:
            for f in os.listdir(target_dir):
                fl = f.lower()
                if fl.endswith('-poster.jpg') or fl.endswith('-poster.png') or fl.endswith('-thumb.jpg'):
                    _try_delete(os.path.join(target_dir, f))
        except OSError:
            pass
        
        # 3. 如果当前目录没删到任何封面，检查父目录（和 get_local_poster 的 fallback 一致）
        if not deleted:
            parent = os.path.dirname(target_dir)
            if parent and os.path.isdir(parent):
                for name in ["poster.jpg", "poster.png", "folder.jpg", "cover.jpg"]:
                    _try_delete(os.path.join(parent, name))
                try:
                    for f in os.listdir(parent):
                        fl = f.lower()
                        if fl.endswith('-poster.jpg') or fl.endswith('-poster.png'):
                            _try_delete(os.path.join(parent, f))
                except OSError:
                    pass
    
    # 文件路径：删同名封面
    if not os.path.isdir(path):
        base = os.path.splitext(path)[0]
        for suffix in ["-poster.jpg", "-poster.png", "-thumb.jpg", ".jpg"]:
            _try_delete(base + suffix)
    
    # 删 TMDB 缓存
    folder_name = os.path.basename(target_dir)
    safe_name = "".join(x for x in folder_name if x.isalnum() or x in " -_").strip()
    cache_path = os.path.join(os.getcwd(), "posters", f"{safe_name}.jpg")
    _try_delete(cache_path)
    
    print(f"[DeletePoster] path={path} deleted={len(deleted)} errors={errors}")
    return {"status": "ok", "deleted": deleted, "errors": errors}
