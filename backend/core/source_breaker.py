"""外部数据源熔断器。

解决的问题：某个源不可用时（典型情况是国内直连 TMDB、或容器无外网），
每次请求都要等它超时，把整个功能拖慢。例如发现页并发拉三个源、
等 8 秒超时，即使豆瓣早就返回了也要陪着等。

策略：连续失败达到阈值后进入冷却期，期间直接跳过该源；
冷却结束后放行一次试探，成功则恢复。
"""
import logging
import threading
import time
from typing import Dict

logger = logging.getLogger(__name__)


class SourceBreaker:
    def __init__(self, threshold: int = 3, cooldown_seconds: float = 300.0):
        self.threshold = threshold
        self.cooldown = cooldown_seconds
        self._fail_count: Dict[str, int] = {}
        self._open_until: Dict[str, float] = {}
        self._lock = threading.Lock()

    def is_open(self, name: str) -> bool:
        """True 表示该源处于熔断状态，调用方应直接跳过。"""
        with self._lock:
            until = self._open_until.get(name, 0.0)
            if until <= 0:
                return False
            if time.time() >= until:
                # 冷却结束：放行一次试探
                self._open_until.pop(name, None)
                self._fail_count[name] = self.threshold - 1
                logger.info(f"[SourceBreaker] {name} 冷却结束，放行一次试探")
                return False
            return True

    def record_success(self, name: str) -> None:
        with self._lock:
            if self._fail_count.get(name) or self._open_until.get(name):
                logger.info(f"[SourceBreaker] {name} 恢复正常")
            self._fail_count.pop(name, None)
            self._open_until.pop(name, None)

    def record_failure(self, name: str) -> None:
        with self._lock:
            cnt = self._fail_count.get(name, 0) + 1
            self._fail_count[name] = cnt
            if cnt >= self.threshold and name not in self._open_until:
                self._open_until[name] = time.time() + self.cooldown
                logger.warning(
                    f"[SourceBreaker] {name} 连续失败 {cnt} 次，"
                    f"{int(self.cooldown)} 秒内跳过该源以免拖慢整体"
                )

    def remaining_cooldown(self, name: str) -> float:
        with self._lock:
            until = self._open_until.get(name, 0.0)
            return max(0.0, until - time.time()) if until else 0.0

    def reset(self, name: str = "") -> None:
        """清空熔断状态（配置变更或测试用）"""
        with self._lock:
            if name:
                self._fail_count.pop(name, None)
                self._open_until.pop(name, None)
            else:
                self._fail_count.clear()
                self._open_until.clear()


# 外部元数据源共用的熔断器实例
metadata_breaker = SourceBreaker(threshold=3, cooldown_seconds=300.0)
