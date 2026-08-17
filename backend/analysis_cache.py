"""分析结果缓存：增量更新，避免重复全量分析。"""

import json
import os
import threading
import time
from typing import Optional, Dict

CACHE_FILE = "analysis_cache.json"


class AnalysisCache:
    """分析结果缓存管理器。"""

    def __init__(self, path: str = CACHE_FILE):
        self._path = path
        self._data: Dict = {"results": {}, "summary": {}, "updated_at": 0}
        # 分析缓存可能很大，但多数启动周期不会访问分析页；首次使用时再读，
        # API 返回结构与落盘格式保持不变。
        self._loaded = False
        self._lock = threading.RLock()

    def _ensure_loaded(self):
        with self._lock:
            if not self._loaded:
                self._load()

    def _load(self):
        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception:
                self._data = {"results": {}, "summary": {}, "updated_at": 0}
        self._loaded = True

    def _save(self):
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def get(self) -> Optional[Dict]:
        """获取缓存的分析结果，如果存在且未过期。"""
        with self._lock:
            self._ensure_loaded()
            if not self._data.get("updated_at"):
                return None
            return self._data

    def get_age_hours(self) -> float:
        """获取缓存年龄（小时）。"""
        with self._lock:
            self._ensure_loaded()
            updated = self._data.get("updated_at", 0)
            if not updated:
                return float("inf")
            return (time.time() - updated) / 3600

    def update(self, report: Dict):
        """更新缓存。"""
        with self._lock:
            self._loaded = True
            self._data = {
                "results": report.get("results", []),
                "summary": report.get("summary", {}),
                "cross_folder_issues": report.get("cross_folder_issues", []),
                "updated_at": time.time(),
            }
            self._save()

    def update_folder(self, folder_path: str, folder_report: Dict):
        """增量更新单个文件夹的分析结果。"""
        with self._lock:
            self._ensure_loaded()
            results = self._data.get("results", [])
            # 替换或追加
            found = False
            for i, r in enumerate(results):
                if r.get("path") == folder_path:
                    results[i] = folder_report
                    found = True
                    break
            if not found:
                results.append(folder_report)
            self._data["results"] = results
            self._data["updated_at"] = time.time()
            # 重新计算 summary
            self._recalc_summary()
            self._save()

    def _recalc_summary(self):
        results = self._data.get("results", [])
        self._data["summary"] = {
            "total_folders": len(results),
            "structure_issues": sum(len(r.get("structure_ops", [])) for r in results),
            "rename_issues": sum(len(r.get("rename_ops", [])) for r in results),
            "scrape_issues": sum(len(r.get("scrape_issues", [])) for r in results),
            "quality_issues": sum(len(r.get("quality_issues", [])) for r in results),
            "filename_issues": sum(len(r.get("filename_issues", [])) for r in results),
            "shadow_name_issues": sum(len(r.get("shadow_name_issues", [])) for r in results),
        }

    def invalidate(self):
        """清除缓存。"""
        with self._lock:
            self._loaded = True
            self._data = {"results": {}, "summary": {}, "updated_at": 0}
            self._save()
