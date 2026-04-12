# 滚动阻尼 + 磁力吸附交互设计

> 用于两个内容区域（媒体库 / 推荐发现页）之间的分页式滚动体验。
> 实现文件：`frontend/hooks/useScrollDamping.ts`

## 核心概念

页面分为上下两个区域，中间有一堵"墙"（发现页头部位置）。滚动行为在墙的两侧有不同的吸附规则，模拟物理阻尼感。

```
┌─────────────────────┐
│   媒体库（上半区）    │  ← scrollTop = 0（顶部磁力点）
│   Header + 卡片      │
│                     │
├─ ─ ─ 墙 ─ ─ ─ ─ ─ ─┤  ← wallRef（发现页 div 的 offsetTop）
│   推荐/探索（下半区） │
│   DiscoverPage       │
│   ...                │
└─────────────────────┘
```

## 吸附规则

### 下滑吸附（媒体库 → 墙）
- **触发条件**：下滑中，scrollTop 进入 `wall - 460` 到 `wall` 的范围
- **行为**：smoothTo(wall)，350ms easeOutQuad 动画

### 上滑吸附（发现页 → 墙）
- **触发条件**：上滑中，scrollTop 进入 `wall` 到 `wall + 460` 的范围
- **行为**：smoothTo(wall)，350ms easeOutQuad 动画

### 上滑吸附（发现页 → 墙 → 媒体库）
- **距墙 < 460px**（从发现页接近墙）：吸附到墙，250ms
- **距墙 > 260px**（穿过墙后）：吸附到顶部，200ms

### 为什么上滑需要 260px 缓冲
- 穿过墙后不立刻吸附，给用户一个"已经离开发现页"的感知
- 260px 大约是 2-3 次鼠标滚轮的距离，体感自然

## 技术实现要点

### 只用 scroll 事件
- 不用 wheel 事件拦截（会导致抖动、阻力感不自然）
- scroll 事件在惯性滚动时也会触发，覆盖所有场景
- `passive: true` 不阻止默认行为，性能好

### smoothTo 动画
- 手动 requestAnimationFrame + easeOutQuad 缓动
- `animatingRef` 防止重复触发
- 动画期间新的 scroll 事件被跳过（`if (animatingRef.current) return`）

### 方向判断
- `dir = st - lastSt`：正数=下滑，负数=上滑
- 只在对应方向触发吸附，避免锁死

### wall 位置动态计算
- 用 `getBoundingClientRect` 实时计算，不依赖 `offsetTop`（避免 offsetParent 不准确）
- `wall = scrollTop + (wallRef.top - container.top)`

## 参数调优记录

| 参数 | 最终值 | 调优过程 |
|------|--------|----------|
| 下滑触发距离 | wall - 460px | 从 80→150→460，太小会感觉不到吸附 |
| 下滑动画时长 | 350ms | 太快闪现，太慢拖沓 |
| 上滑吸墙距离 | < 460px | 和下滑对称 |
| 上滑到顶距离 | > 260px | 穿过缓冲区才回媒体库 |
| 上滑动画时长 | 200ms | 快速吸附，体感像被磁铁吸回 |
| 缓动函数 | easeOutQuad | easeOutCubic 结尾太慢，easeInOut 中间会抖 |

## 踩坑记录

1. **wheel 事件 + preventDefault 方案**：会导致发现页内部正常滚动被干扰，放弃
2. **overflow:hidden 冻结惯性**：会导致滚动条消失→内容宽度变化→左右抖动，放弃
3. **scroll 事件中 smoothTo 被惯性覆盖**：动画期间 `animatingRef` 跳过新事件解决
4. **offsetTop 不准确**：改用 getBoundingClientRect 动态计算
5. **顶部吸附锁死**：不区分方向会导致下滑也被吸回顶部，必须判断 `dir`
