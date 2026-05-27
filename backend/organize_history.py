import os
import json
import time
import shutil
from typing import List, Dict
from datetime import datetime

HISTORY_DIR = os.path.join(
    os.environ.get("NAPICS_DATA_DIR") or os.path.dirname(os.path.abspath(__file__)),
    "organize_snapshots"
)
MAX_SNAPSHOTS = 100  # 最大保留数量


class OrganizeHistory:
    def __init__(self):
        if not os.path.exists(HISTORY_DIR):
            os.makedirs(HISTORY_DIR)

    def _generate_summary(self, operations: List[Dict], label: str) -> str:
        """根据操作列表生成简短摘要"""
        count = len(operations)
        if label == "organize":
            dirs = set()
            for op in operations:
                p = op.get("new_path", "")
                if p:
                    parts = p.replace("\\", "/").split("/")
                    # 取倒数第二级目录名作为目标
                    if len(parts) >= 2:
                        dirs.add(parts[-2])
            if dirs:
                sample = list(dirs)[:3]
                extra = f" 等{len(dirs)}个文件夹" if len(dirs) > 3 else ""
                return f"整理 {count} 个文件 → {'、'.join(sample)}{extra}"
            return f"整理 {count} 个文件"
        elif label == "rename":
            renames = []
            for op in operations:
                old_name = os.path.basename(op.get("old_path", ""))
                new_name = os.path.basename(op.get("new_path", ""))
                if old_name != new_name:
                    renames.append(new_name)
            if renames:
                sample = renames[:2]
                extra = f" 等{len(renames)}项" if len(renames) > 2 else ""
                return f"重命名 {'、'.join(s[:15] for s in sample)}{extra}"
            return f"重命名 {count} 项"
        elif label == "merge_seasons":
            return f"合并散落季 {count} 个文件"
        return f"{label or '操作'} {count} 项"

    def create_snapshot(self, operations: List[Dict], label: str = ""):
        """保存一次批量操作的快照"""
        snapshot_id = int(time.time())
        snapshot_path = os.path.join(HISTORY_DIR, f"snapshot_{snapshot_id}.json")

        ops = []
        for op in operations:
            entry = {"old_path": op.get("old_path", ""), "new_path": op.get("new_path", "")}
            entry["is_dir"] = op.get("is_dir", False)
            ops.append(entry)

        summary = self._generate_summary(ops, label)

        with open(snapshot_path, "w", encoding="utf-8") as f:
            json.dump({
                "id": snapshot_id,
                "time": time.ctime(),
                "label": label,
                "summary": summary,
                "ops": ops
            }, f, indent=4, ensure_ascii=False)

        # 自动清理：超过上限时删除旧快照（但每月至少保留一条）
        self._auto_cleanup()

        return snapshot_id

    def _auto_cleanup(self):
        """清理超出上限的快照，但每月至少保留一条"""
        files = sorted(
            [f for f in os.listdir(HISTORY_DIR) if f.startswith("snapshot_")],
            reverse=True
        )
        if len(files) <= MAX_SNAPSHOTS:
            return

        # 按月分组，标记每月最后一条
        monthly_keepers = set()
        for fname in files:
            try:
                ts = int(fname.replace("snapshot_", "").replace(".json", ""))
                month_key = datetime.fromtimestamp(ts).strftime("%Y-%m")
                if month_key not in monthly_keepers:
                    monthly_keepers.add(month_key)
                    # 这个文件是该月的最新一条，标记为保留
            except (ValueError, OSError):
                pass

        # 从旧到新遍历，删除超出上限且不是月度保留的
        kept_months = {}
        to_delete = []
        for fname in files:
            try:
                ts = int(fname.replace("snapshot_", "").replace(".json", ""))
                month_key = datetime.fromtimestamp(ts).strftime("%Y-%m")
            except (ValueError, OSError):
                to_delete.append(fname)
                continue

            if month_key not in kept_months:
                kept_months[month_key] = fname  # 每月最新的一条

        # 保留最新的 MAX_SNAPSHOTS 条 + 每月至少一条
        keep_set = set(files[:MAX_SNAPSHOTS])
        keep_set.update(kept_months.values())

        for fname in files:
            if fname not in keep_set:
                try:
                    os.remove(os.path.join(HISTORY_DIR, fname))
                except OSError:
                    pass

    def list_snapshots(self, limit: int = 20):
        files = [f for f in os.listdir(HISTORY_DIR) if f.startswith("snapshot_")]
        snapshots = []
        for fname in sorted(files, reverse=True)[:limit]:
            try:
                with open(os.path.join(HISTORY_DIR, fname), "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                    # 兼容旧快照：补充 summary
                    if "summary" not in data:
                        data["summary"] = self._generate_summary(
                            data.get("ops", []), data.get("label", "")
                        )
                    snapshots.append(data)
            except Exception:
                pass
        return snapshots

    def clear_all(self, keep_monthly: bool = True):
        """清空所有快照
        keep_monthly=True 时每月保留最新一条
        """
        files = sorted(
            [f for f in os.listdir(HISTORY_DIR) if f.startswith("snapshot_")],
            reverse=True
        )
        if not files:
            return {"deleted": 0, "kept": 0}

        keep_set = set()
        if keep_monthly:
            kept_months = {}
            for fname in files:
                try:
                    ts = int(fname.replace("snapshot_", "").replace(".json", ""))
                    month_key = datetime.fromtimestamp(ts).strftime("%Y-%m")
                    if month_key not in kept_months:
                        kept_months[month_key] = fname
                except (ValueError, OSError):
                    pass
            keep_set = set(kept_months.values())

        deleted = 0
        for fname in files:
            if fname not in keep_set:
                try:
                    os.remove(os.path.join(HISTORY_DIR, fname))
                    deleted += 1
                except OSError:
                    pass

        return {"deleted": deleted, "kept": len(keep_set)}

    def rollback(self, snapshot_id: int):
        snapshot_path = os.path.join(HISTORY_DIR, f"snapshot_{snapshot_id}.json")
        if not os.path.exists(snapshot_path):
            return False, "Snapshot not found"

        with open(snapshot_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        success = []
        failed = []
        created_dirs = set()

        for op in reversed(data["ops"]):
            old_p = op["old_path"]
            new_p = op["new_path"]

            if not os.path.exists(new_p):
                failed.append({"path": new_p, "error": "File already moved or deleted"})
                continue

            try:
                os.makedirs(os.path.dirname(old_p), exist_ok=True)
                shutil.move(new_p, old_p)
                success.append(new_p)
                parent = os.path.dirname(new_p)
                if parent:
                    created_dirs.add(parent)
            except Exception as e:
                failed.append({"path": new_p, "error": str(e)})

        for d in sorted(created_dirs, key=len, reverse=True):
            try:
                if os.path.isdir(d) and not os.listdir(d):
                    os.rmdir(d)
            except Exception:
                pass

        return True, {"success": success, "failed": failed}


history_m = OrganizeHistory()
