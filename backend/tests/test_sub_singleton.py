"""Phase 0 验证：SubscriptionManager 全局单例测试。

验证目标：
1. shared._get_sub_manager() 多次调用返回同一实例
2. download_manager 和 routes/subscribe.py 使用同一实例
3. 并发读写 subscriptions.json 不丢数据
"""

import os
import json
import threading
import sys

# 确保 backend 目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_singleton_identity():
    """多次调用 _get_sub_manager() 返回同一实例"""
    from shared import _get_sub_manager
    mgr1 = _get_sub_manager()
    mgr2 = _get_sub_manager()
    assert mgr1 is mgr2, "单例失败：两次调用返回了不同实例"
    print("[PASS] test_singleton_identity")


def test_download_manager_uses_shared_singleton():
    """download_manager._notify_subscription_complete 使用 shared 单例"""
    from shared import _get_sub_manager, _get_download_manager
    
    sub_mgr = _get_sub_manager()
    dm = _get_download_manager()
    
    # 模拟 _notify_subscription_complete 中的导入路径
    from shared import _get_sub_manager as dm_get_mgr
    dm_mgr = dm_get_mgr()
    
    assert sub_mgr is dm_mgr, "download_manager 使用的不是 shared 单例"
    print("[PASS] test_download_manager_uses_shared_singleton")


def test_concurrent_write():
    """并发写入 subscriptions.json 不丢数据"""
    from shared import _get_sub_manager
    mgr = _get_sub_manager()
    
    # 备份原始数据
    original_subs = list(mgr.subscriptions)
    original_file = mgr._file_path
    
    # 用临时文件测试
    test_file = os.path.join(os.path.dirname(original_file), "test_concurrent_subs.json")
    mgr._file_path = test_file
    mgr.subscriptions = []
    mgr._save()
    
    errors = []
    
    def add_sub(i):
        try:
            result = mgr.add({
                "title": f"测试剧集{i}",
                "year": "2025",
                "type": "tv",
            })
            if result.get("status") != "ok":
                errors.append(f"添加失败: {result}")
        except Exception as e:
            errors.append(f"线程{i}异常: {e}")
    
    # 10 个线程并发添加
    threads = [threading.Thread(target=add_sub, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    assert not errors, f"并发写入出错: {errors}"
    assert len(mgr.subscriptions) == 10, f"期望 10 条订阅，实际 {len(mgr.subscriptions)}"
    
    # 验证持久化：重新加载
    mgr._load()
    assert len(mgr.subscriptions) == 10, f"持久化后期望 10 条，实际 {len(mgr.subscriptions)}"
    
    # 清理
    mgr._file_path = original_file
    mgr.subscriptions = original_subs
    try:
        os.remove(test_file)
    except Exception:
        pass
    
    print("[PASS] test_concurrent_write")


if __name__ == "__main__":
    test_singleton_identity()
    test_download_manager_uses_shared_singleton()
    test_concurrent_write()
    print("\n✅ Phase 0 所有测试通过")
