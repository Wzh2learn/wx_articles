你现在做代码审查，重点不是挑风格，而是：是否违背 rules、是否引入风险、是否缺验证。

# 输入

- 变更说明（或 diff/文件列表）
- 目标与成功标准

# 代码审查 (Review) 指南

你要对当前的修改进行深度审计，确保不仅代码能跑通，而且符合工程规范与产品目标。

## 1) 审查核心项 (Checklist)

- **功能对齐**：是否完全实现了 PRP 蓝图中的所有功能？
- **文档同步**：README、SOP、ARCHITECTURE 等文档是否已随代码更新？
- **范围一致性**：除了修改的文件，相关的页面（UI）、引用该函数的其他模块是否已同步适配？
- **代码质量**：是否有无用的 console.log、未捕获的异常或不符合 .windsurfrules 的风格？

## 2) Guardrails Check（逐条对照 .windsurfrules 的红线/不可破坏点）

## 3) Risk Register（按严重度列风险 + 缓解建议）

## 4) Validation Gaps（缺哪些验证/回归点）

## 5) Suggested Next Actions（按优先级）
