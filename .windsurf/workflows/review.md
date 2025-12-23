你现在做代码审查，重点不是挑风格，而是：是否违背 rules、是否引入风险、是否缺验证。

# 输入

- 变更说明（或 diff/文件列表）
- 目标与成功标准

# 输出结构

## 1) Summary（改了什么，是否符合目标）

## 2) Guardrails Check（逐条对照 .windsurfrules 的红线/不可破坏点）

## 3) Risk Register（按严重度列风险 + 缓解建议）

## 4) Validation Gaps（缺哪些验证/回归点）

## 5) Suggested Next Actions（按优先级）
