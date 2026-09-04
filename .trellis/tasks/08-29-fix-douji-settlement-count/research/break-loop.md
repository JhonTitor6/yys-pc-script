# Bug Analysis: 斗技胜利结算漏记总场次

## 1. Root Cause Category

- **Category**: E - Implicit Assumption；D - Test Coverage Gap
- **Specific Cause**: 代码假设胜利模板之后一定还会触发普通结束模板，但同一画面存在多个模板时，事件循环只处理优先命中的一个；胜利回调点击后，普通结束模板可能不再出现。

## 2. Why Fixes Failed

1. 上次修复只给胜利次数加了单场去重状态，没有把胜负结果、总场次和日志作为一个结算事务处理。
2. 回归测试只断言胜利次数，没有断言总场次与日志，因此错误的两阶段结算假设没有失败信号。

## 3. Prevention Mechanisms

| Priority | Mechanism | Specific Action | Status |
|---|---|---|---|
| P0 | Architecture | 首个胜/负终态原子消费整场计数与日志 | DONE |
| P0 | Test Coverage | 覆盖重复胜利模板、同场混合模板、下一场失败 | DONE |
| P1 | Documentation | 更新 backend 质量规范，禁止依赖结算模板顺序 | DONE |

## 4. Systematic Expansion

- **Similar Issues**: 其他脚本若把一次业务结算拆到两个视觉事件，也可能漏计或重复计数。
- **Design Improvement**: 业务结果应由“每场只消费一次”的状态统一记录，视觉回调只提供结果类型和点击动作。
- **Process Improvement**: 结算回归测试必须同时断言点击、总场次、胜利次数和日志，不得只测单个计数器。

## 5. Knowledge Capture

- [x] 更新 `.trellis/spec/backend/quality-guidelines.md` 的结算原子性契约。
