# 📅 每日公众号发文 SOP (wx_articles v5.0) — 流量与效率版

## 1. 全天候：极速选题雷达 (随时运行)
1. **启动扫描**：`python main.py hunt`
2. **多源并发**：系统现在采用并发探测 Product Hunt, Hacker News, V2EX 和**微信公众号热榜**，速度提升显著。
3. **最新权重**：可以多次运行 `hunt`。系统在最终决策时会赋予**最后一份报告**最高的决策权重。

## 2. 定点：综合决策 (推荐 12:00 或 18:00)
1. **生成决策**：`python main.py final`
2. **权重校验**：检查输出，确认系统是否采纳了最新的主推选题。
3. **策略切换**：如果当前是起量期，确保 `config/settings.yaml` 中的 `operational_phase` 设置为 `TRAFFIC_STORM`。

## 3. 自动生产：研究与初稿
1. **深度研究**：`python main.py research`。系统将优先通过 **Perplexity** 获取深度摘要，再由 Tavily/Exa 补充细节。
2. **生成初稿**：`python main.py draft --mode traffic`（或直接运行 `draft`，系统会自动读取配置）。
3. **标题工厂**：在 `draft.md` 末尾查看 5 个不同维度的爆款标题，根据直觉选一个。

## 4. 发布前：润色与校验
1. **编辑定稿**：在 `4_publish/final.md` 中进行最后的润色。
2. **自动截图**：检查 `5_assets` 目录，确认 GitHub 或官网截图是否已自动生成。
3. **排版发布**：`python main.py format --style livid`，复制 HTML 到公众号后台。
4. **节流模式**：开发测试时建议使用 `python main.py hunt --dry-run` 以节省 API 额度。
