你现在执行【PRPify】流程：把“口述/自然语言需求”整理成可直接喂给 /prp 的输入包。

# 输入（缺失就问最多 5 个问题）

- 我的需求描述（允许一段话/多段话）
- 我希望的结果/验收方式（如果没有，你来给可验证版本）
- 约束/红线（来自 README/SOP/项目规则）
- 相关模块/文件（如果我不知道，你给“最小需要读的文件清单”）

# 输出结构（必须严格按此输出；不要写实现代码）

## 0) Clarifying Questions（最多 5 个；信息足够可跳过）

## 1) PRP Input Packet（交给 /prp 的输入）

- Goal / Success Criteria（可验证）
- What IS / What ISN’T（范围边界）
- Affected Modules / Files（最小集合）
- Constraints / Guardrails（红线/不可破坏点）
- Risks（按严重度）
- Validation Commands（最小验证 + targeted 验证）
- Manual Smoke Checklist（必须手测的关键路径）
- Rollback Plan（出问题怎么最小回退）

## 2) Recommended Next Command

- 你应该接着运行：/prp（推荐一键版：直接贴口述需求也可以，不需要手动复制本输出）
