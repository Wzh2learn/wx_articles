你要为本次需求生成一份 PRP（Product Requirements Prompt），目标是“可执行蓝图”，而不是空泛方案。

如果你只有口述/自然语言需求：直接把需求贴到下面的【输入】中即可；你需要先将其整理成 “PRP Input Packet”，再基于该 Input Packet 输出最终 PRP。

如果你已经运行过 /prpify：也可以把 /prpify 输出的 “PRP Input Packet” 直接贴到下面的【输入】中。

# 输入（缺失就问最多 3 个问题）

- Goal / Success Criteria（可验证）
- What IS / What ISN’T
- 受影响模块/文件（最小集合）
- 约束/红线（来自 .windsurfrules）
- 验证命令（最小验证 + targeted 验证）

# 输出结构（必须严格按此输出）

## 1) Goal & Success Criteria

## 2) Non-Goals

## 3) Context (only what’s needed)

- 相关 docs / 关键文件路径 / 现有模式（不要扫全仓库）

## 4) Design / Implementation Blueprint

- 数据结构/接口变更（如有）
- 按顺序的步骤（每步说明修改点与原因）
- 集成点（前端/后端/API/存储）

## 5) Risks & Guardrails

- 可能破坏点（持久化 schema、keys、重试逻辑、性能/风控）

## 6) Validation Loop

- 最小验证（必须）
- targeted 验证（按改动类型）
- 回归点（哪些功能必须手测）
