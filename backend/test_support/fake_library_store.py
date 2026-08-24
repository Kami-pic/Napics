"""测试用假 ConfigManager 的媒体库写入契约。

真实的 ConfigManager 暴露 `library_lock`（按库文件路径共享的 RLock）和
`mutate_library(fn)`（锁内 load → fn → save）。路由层现在一律走这两个入口，
所以任何替换 config_m 的假实现都必须提供它们，否则测的是"假对象缺方法"
而不是路由行为。

用法：让假 ConfigManager 继承 LibraryMutationContract，
自己只实现 load_library / save_library。
"""

import threading


class LibraryMutationContract:
    """把 library_lock / mutate_library 转发到假的 load_library / save_library。

    锁用一个真的 RLock（可重入），行为和生产一致；
    mutate_library 的返回值语义也保持一致：
    None 保存原地修改、False 跳过落盘、list 覆盖整库。
    """

    @property
    def library_lock(self) -> threading.RLock:
        lock = getattr(self, "_fake_library_lock", None)
        if lock is None:
            lock = threading.RLock()
            self._fake_library_lock = lock
        return lock

    def mutate_library(self, fn):
        with self.library_lock:
            library = self.load_library()
            result = fn(library)
            if result is False:
                return False
            if result is None:
                self.save_library(library)
                return True
            if isinstance(result, list):
                self.save_library(result)
                return True
            raise TypeError(
                f"mutate_library 的回调只能返回 None / False / list，收到 {type(result).__name__}"
            )
