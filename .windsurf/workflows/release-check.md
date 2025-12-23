你现在做发布/合并前验收：确保“可运行、可回归、可回滚”。

# 输入

- 本次变更范围（文件/模块）
- 运行方式（dev/build/deploy）
- 环境变量变化（如有）

# 输出结构

## 1) Must-pass Checklist

- lint/build/test/dev smoke（按项目 rules）

## 2) Runtime/Env Checklist

- env keys、proxy/base_url、serverless 路由、CORS 等（若涉及）

## 3) Critical Path Smoke

- 关键用户路径（最少 3 条）

## 4) Rollback Plan

- 如果上线出问题，最小回退动作
