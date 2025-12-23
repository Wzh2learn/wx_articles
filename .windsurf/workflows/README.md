# Workflows Quickstart

## Recommended Loops

### 1) Effect-driven（不确定改哪里/先看效果）

- /persona-wx
- /product-review
- /prp 或 /bugfix（如果需要工程）
- /review
- /release-check
- 回到 /product-review 复验

### 2) Requirement-driven（你已决定要做什么）

- /persona-wx
- /prpify（把口述需求整理成 PRP 输入）
- /prp（生成可执行蓝图）
- 实现
- /review
- /release-check

## What each workflow is for

- **one-loop**: 一页纸用法协议（两条入口：效果驱动 vs 需求驱动）
- **persona-wx**: 注入内容产品目标与质量门槛
- **product-review**: 先看问题与机会、再决定要不要进工程
- **prpify**: 把自由描述整理成 /prp 的标准输入包
- **prp**: 输出“可执行蓝图”（步骤、集成点、风险、验证）
- **bugfix**: 最小 bugfix 闭环（根因→最小改动→最小验证）
- **review**: 风险/红线/验证缺口的代码审查
- **release-check**: 合并/发布前的 must-pass 验收清单
