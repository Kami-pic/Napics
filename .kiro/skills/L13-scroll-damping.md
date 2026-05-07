# L13 滚动阻尼交互

> 通用型 Skill：两区域间磁力吸附 + 方向感知 + easeOut 动画
> 实现文件：`frontend/hooks/useScrollDamping.ts`

## 核心模式

页面分为上下两个内容区域，中间有一个"墙"（分界点）。滚动行为在墙两侧有不同的吸附规则，模拟物理阻尼感。

```
┌─────────────────────┐
│   区域 A（上半区）    │  ← 顶部磁力点
│                     │
├─ ─ ─ 墙 ─ ─ ─ ─ ─ ─┤  ← wallRef（分界元素的 offsetTop）
│   区域 B（下半区）    │
│                     │
└─────────────────────┘
```

## 吸附规则

| 方向 | 触发条件 | 行为 |
|------|---------|------|
| 下滑（A→墙） | scrollTop 进入 `wall - threshold` 到 `wall` | smoothTo(wall) |
| 上滑（B→墙） | scrollTop 进入 `wall` 到 `wall + threshold` | smoothTo(wall) |
| 上滑穿墙（墙→A） | 距墙 > buffer 且继续上滑 | smoothTo(0) |

## 关键设计决策

1. **只用 scroll 事件**：不用 wheel 事件拦截（会导致抖动），scroll 在惯性滚动时也触发，`passive: true` 不阻止默认行为
2. **方向判断**：`dir = currentScroll - lastScroll`，只在对应方向触发吸附，避免锁死
3. **动画互斥**：`animatingRef` 防止重复触发，动画期间跳过新 scroll 事件
4. **wall 位置动态计算**：用 `getBoundingClientRect` 实时计算，不依赖 `offsetTop`

## smoothTo 动画

- 手动 `requestAnimationFrame` + easeOutQuad 缓动
- 时长 200-350ms（快速吸附体感像磁铁）
- 动画结束后释放 `animatingRef`

## 参数参考

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| 触发阈值 | 400-500px | 太小感觉不到吸附 |
| 穿墙缓冲 | 200-300px | 给用户"已离开"的感知 |
| 下滑动画时长 | 300-400ms | 太快闪现，太慢拖沓 |
| 上滑动画时长 | 150-250ms | 快速吸回 |
| 缓动函数 | easeOutQuad | easeOutCubic 结尾太慢 |

## 适用场景

- 双区域分页式布局（媒体库 + 推荐页）
- 长页面中的"章节锁定"
- 任何需要"滚动到某个位置时停一下"的交互

## 踩坑

- wheel + preventDefault 会干扰区域内部正常滚动
- overflow:hidden 冻结惯性会导致滚动条消失→宽度变化→左右抖动
- 不区分方向会导致双向锁死
- offsetTop 在嵌套容器中不准确，必须用 getBoundingClientRect
