# 🚀 王往AI 公众号工作流 v4.3 (Hardcore Stability Edition)

一套完整的 AI 驱动的微信公众号内容生产工作流，从选题到发布**全流程自动化**。

## ✨ 功能特性 (v4.3)

### 新增亮点
- 🛡️ **数据安全**：自动备份机制（Auto Backups），每次写入草稿/定稿前自动生成 `.bak` 防丢失。
- 🧠 **智能去重**：语义去重（Semantic Dedup），选题高相似时自动保留最低相似度候选，防止“撞车”与饥饿。
- 🖥️ **可视化后台**：Streamlit UI（`app.py`），交互式选题、编辑与排版预览。
- ✅ **审计容错**：事实核查与截图均有优雅降级，缺失输入或截图失败会给出可见提示而非崩溃。

| 模块 | 功能 | 核心策略 |
|------|------|--------|
| 🎯 **选题雷达** | 全网扫描热点，三级容错机制 (Jina/RSS/Tavily) | **大厂/开源优先** + **信源净化 (Anti-SEO)** + **严格去重** |
| 🔬 **自动研究** | Exa AI 智能搜索 + 全文获取 + 自动笔记整理 | **批判性评估** (自动拉黑智商税工具) |
| ✍️ **写作智能体** | 读取研究笔记，生成硬核技术流初稿 | **专家验证约束** (Anti-Wrapper) |
| 🎨 **排版智能体** | 自动转换为微信风格 HTML，代码高亮 | **极客代码风** (VS Code 深色主题) |

## 🚀 快速开始

### 1. 启动全自动流程

最简单的方式是一键运行完整流程：

```bash
# 1. 扫描选题 (建议早/中/晚各运行一次)

3. **配置环境变量**
   复制 `.env.example` 为 `.env`，并填入你的 API Key：
   ```ini
   DEEPSEEK_API_KEY=sk-xxxxxxxx
   EXA_API_KEY=xxxxxxxx
   TAVILY_API_KEY=tvly-xxxxxxxx
   SILICONFLOW_API_KEY=sk-xxxxxxxx (用于 Flux 绘图)
   ```

## 🚀 快速上手

### 全自动模式（一键生成）
### 🎯 定向选题说明（-t）

当你使用 `-t` 指定主题时，系统会启用“混合优先级”机制：

- **用户命题优先**：在同等价值下，优先推荐你指定的主题。
- **允许抗旨**：如果扫描到突发的重大更新且爆款潜质更高，会提示你“改写热点”或“合并两者”。
- **同台竞技**：仍会保留部分随机探索，让热点不会被主题锁死。

### 🎨 排版调试说明（format）

`format` 会把 `4_publish/final.md` 转成可直接粘贴到公众号编辑器的 HTML，并自动复制到剪贴板。

- 如果你发现排版没有更新，请先确认 `final.md` 是否保存；脚本会输出“输入文件最后修改时间”用于排查。

### 🖥️ Streamlit 后台

```bash
streamlit run app.py
```

功能：交互式选题扫描、草稿/定稿编辑、实时排版预览（支持新增 livid/vue/typewriter 风格）。

### 📂 项目结构 (v4.3)

```
wx_articles/
├─ app.py                   # Streamlit 可视化后台
├─ run.py                   # CLI 入口（hunt/final/research/draft/refine/audit/format/todo/all）
├─ config/
│  └─ settings.yaml         # 中央配置（watchlist、pricing、sources）
├─ agents/                  # 各智能体 (trend_hunter/researcher/drafter/refiner/auditor/formatter/…)
├─ data/
│  └─ archive/YYYY-MM-DD/   # 当日工作区（topics/research/drafts/publish/assets）
├─ logs/                    # 运行日志（已在 .gitignore）
└─ requirements.txt
```

### 📂 文件夹用途详解

| 文件夹 | 用途 | 自动化状态 |
|--------|------|------|
| `1_topics/` | 选题报告 | ✅ 全自动生成 |
| `2_research/` | 研究笔记 | ✅ **全自动** (Exa AI + Jina) |
| `3_drafts/` | AI 初稿 | ✅ 全自动生成 |
| `4_publish/` | **待发布**定稿 | ✏️ **唯一人工环节**：润色后保存 `final.md` |
| `5_assets/` | 配图素材 | ✏️ 人工添加截图 |

**发布流程**：
```
Trend Hunter (hunt) → Final Decision (final) → Researcher (research) → Drafter (draft)
                                                                     ↓
                                                             人工润色/配图
                                                                     ↓
公众号后台手动发布 ← Formatter (format) ← final.md (定稿)
```

## 🛠️ 安装

### 1. 克隆项目

```bash
cd D:\AIlearn
git clone <repo_url> wx_articles
cd wx_articles
```

### 2. 安装依赖

```bash
# 如果有代理
pip install -r requirements.txt --proxy http://127.0.0.1:7898

# 无代理
pip install -r requirements.txt

# 可视化后台
pip install streamlit
```

### 3. 配置 API Key

复制配置模板并填入你的密钥：

```bash
cp config.py.example config.py
```

然后编辑 `config.py`，或通过环境变量设置：

```bash
# DeepSeek API (核心大脑)
set DEEPSEEK_API_KEY=sk-your-api-key-here

# Exa AI (智能搜索核心)
set EXA_API_KEY=your-exa-key

# Tavily (备用搜索)
set TAVILY_API_KEY=tvly-your-key
```

## 🧹 Maintenance

- **自动备份**：`draft`/`final` 写入前自动生成 `.bak`（同目录，含时间戳）。如需恢复，直接用最新 `.bak` 覆盖原文件。
- **事实核查**：`python run.py audit`（或在 Streamlit 后台点击 “Run Audit”）。缺少笔记/定稿时会显示“Audit Skipped”黄色提示，不会崩溃。
- **排版导出**：`python run.py format --style livid`（或其它风格）。输出 `output.html` 并复制到剪贴板。

## 🚀 核心模块详解

### 1. 选题雷达 (Trend Hunter) 🎯

**v4.0 升级：三级容错 + 随机化**

- **三级容错机制**：Jina Primary -> Jina Backup (RSS) -> Tavily Search，确保从不空手而归。
- **心理学三路搜索**：
    - 🎯 **A路 (锚点)**：死磕顶流 (DeepSeek/Kimi/Cursor) 隐藏玩法
    - ⚡ **B路 (收益)**：随机抽取 "效率神器"、"自动化办公" 词库
    - 🛡️ **C路 (损失)**：随机抽取 "避坑"、"智商税"、"平替" 词库
- **严格去重**：自动加载历史记录，禁止生成重复选题。

### 2. 自动研究 (Auto Researcher) 🔬

**v4.0 升级：批判性评估过滤器**

- **Exa AI 智能搜索**：自动定位微信/知乎/掘金等高质量信源。
- **反套壳机制**：在整理笔记时，自动识别并拉黑“付费套壳工具”（如笔灵、小发猫）。
- **硬核验证**：只提取 Prompt 优化、API 接入、本地部署等真正的高阶玩法。

### 3. 写作智能体 (Drafter) ✍️

**v4.0 升级：专家人设锁死**

- **DeepSeek Reasoner 加持**：使用深度推理模型生成逻辑严密的文章。
- **绝对禁忌**：严禁推荐任何“国内付费套壳工具”。
- **技术流定义**：将“高阶玩法”严格定义为技术层面的解决方案。

## ⚙️ 配置说明

编辑 `config.py` 或设置环境变量：

```python
# === API 配置 ===
DEEPSEEK_API_KEY = "sk-..." 
EXA_API_KEY = "..."          # 核心搜索
TAVILY_API_KEY = "tvly-..."  # 兜底搜索

# === 微信公众号配置 ===
WECHAT_APP_ID = "..."
WECHAT_APP_SECRET = "..."

# === 代理配置 ===
PROXY_URL = "http://127.0.0.1:7898" 
```

## 🤝 作者

**王往AI** - 热爱新兴技术的探索者，专注 AI 工作流的硬核博主

---

*用技术反击信息差，用 AI 捍卫硬核价值。*
