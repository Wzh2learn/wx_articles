# 🚀 王往AI 公众号工作流

一套完整的 AI 驱动的微信公众号内容生产工作流，从选题到发布**全流程自动化**。

## ✨ 功能特性

| 模块 | 功能 | 技术栈 |
|------|------|--------|
| 🎯 **选题雷达** | 全网扫描热点，动态提取关键词，智能推荐选题 | DeepSeek + DuckDuckGo |
| ✍️ **写作智能体** | 读取研究笔记，生成符合人设的初稿 | DeepSeek Reasoner |
| 📋 **TODO提取器** | 列出草稿中需要补充的截图和内容 | Python Regex |
| 🎨 **排版智能体** | Markdown 转 HTML，壹伴风格，一键复制 | Pygments + Premailer |
| 📤 **发布智能体** | 自动上传图片，一键创建草稿 | wechatpy + 微信API |

## 📁 项目结构

```text
wx_articles/
├── README.md                # 项目说明
├── requirements.txt         # Python 依赖
├── config.py.example       # 配置模板
├── config.py               # 你的配置（已被 gitignore）
├── run.py                  # 统一入口脚本
├── agents/                 # 智能体模块
│   ├── __init__.py
│   ├── trend_hunter.py     # 🎯 选题雷达
│   ├── drafter.py          # ✍️ 写作智能体
│   ├── todo_extractor.py   # 📋 TODO 提取器
│   ├── formatter.py        # 🎨 排版智能体
│   └── publisher.py        # 📤 发布智能体
└── data/archive/           # 按日期 + 阶段归档
        └── 2025-12-02/
            ├── 1_topics/       # 选题报告
            │   └── report_1230.md
            ├── 2_research/     # 研究笔记 ← 在这里编辑
            │   └── notes.txt
            ├── 3_drafts/       # 草稿
            │   ├── draft.md
            │   └── todo_list.txt
            ├── 4_publish/      # 发布文件
            │   ├── final.md
            │   └── output.html
            └── 5_assets/       # 资源文件
                └── (图片等)
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
```

### 3. 配置 API Key

复制配置模板并填入你的密钥：

```bash
cp config.py.example config.py
```

然后编辑 `config.py`，或通过环境变量设置：

```bash
# DeepSeek API (必需)
set DEEPSEEK_API_KEY=sk-your-api-key-here

# 微信公众号 API (可选，用于自动发布)
set WECHAT_APP_ID=wx1234567890
set WECHAT_APP_SECRET=your-app-secret
```

### 4. 微信公众号配置（可选）

如果要使用**自动发布**功能：

1. 登录 [微信公众平台](https://mp.weixin.qq.com/)
2. 进入「设置与开发」→「基本配置」
3. 获取 `AppID` 和 `AppSecret`
4. 将你的公网 IP 添加到「IP 白名单」
5. 填入 `config.py` 或设置环境变量

## 🚀 使用方法

### 快速开始

```bash
# 查看帮助
python run.py
python run.py help

# 运行选题雷达
python run.py hunt

# 运行写作智能体
python run.py draft

# 提取 TODO 清单
python run.py todo

# 运行排版智能体
python run.py format

# 自动发布到微信草稿箱
python run.py publish

# 运行完整流程（交互式）
python run.py all
```

### 完整工作流

```mermaid
graph TD
    A[python run.py hunt] -->|生成| B(topic_report.md)
    B -->|人工选择选题| C[NotebookLM 研究]
    C -->|整理| D(research_notes.txt)
    D -->|python run.py draft| E(draft.md)
    E -->|python run.py todo| F{查看 TODO 清单}
    F -->|人工补图润色| G(final.md)
    G -->|python run.py format| H(output.html)
    H -->|方式A: 手动| I[浏览器复制粘贴]
    H -->|方式B: 自动| J[python run.py publish]
    J -->|自动创建| K[微信草稿箱]
```

#### Step 1: 选题 🎯

```bash
python run.py hunt
```

- 自动扫描 GitHub Trending、ReadHub、小红书、微博、少数派
- AI 动态提取今日热词
- 推荐 3 个最适合你人设的选题
- 输出：`data/archive/2025-12-02/topic_report_1230.md`

#### Step 2: 研究 📚

1. 选择一个选题
2. 去 [NotebookLM](https://notebooklm.google.com/) 做深度研究
3. 整理笔记到 `data/input/research_notes.txt`

#### Step 3: 写初稿 ✍️

```bash
python run.py draft
```

- 读取研究笔记（自动备份到今日目录）
- DeepSeek Reasoner 生成初稿（流式输出）
- 输出：`data/archive/2025-12-02/draft.md`

#### Step 4: 查看 TODO 📋

```bash
python run.py todo
```

- 列出草稿中所有需要补充的内容
- 显示图片搜索关键词建议
- 帮助你快速定位需要处理的部分

#### Step 5: 润色 ✨

1. 打开今日目录下的 `draft.md`
2. 根据 TODO 清单补充截图
3. 润色文字，加入个人风格
4. 保存为同目录下的 `final.md`

#### Step 6: 排版 🎨

```bash
python run.py format
```

- 转换为微信公众号兼容的 HTML
- 壹伴风格（渐变标题、卡片引用、记号笔高亮）
- 自动复制到剪贴板
- 输出：`data/archive/2025-12-02/output.html`

#### Step 7: 发布 📤

**方式 A：手动发布**
1. 用浏览器打开 `output.html`
2. `Ctrl+A` 全选 → `Ctrl+C` 复制
3. 粘贴到公众号**普通编辑模式**

**方式 B：自动发布（推荐）**
```bash
python run.py publish
```

- 自动上传所有图片到微信服务器
- 支持 PicGo 等图床链接自动转存
- 自动选择第一张图作为封面
- 一键创建草稿，去后台点发布即可！

### 📅 日期归档说明

每次运行脚本，文件会自动保存到 `data/archive/YYYY-MM-DD/` 目录下。

这样设计的好处：

- **历史可追溯**：每次创作的素材、初稿、定稿都有完整记录
- **不会覆盖**：两三天更新一次，文件不会互相覆盖
- **便于回顾**：随时查看过去写了什么

## 🎨 排版风格

采用**壹伴风格**，简洁专业：

| 元素 | 样式 |
|------|------|
| 代码块 | VS Code 深色主题，圆角阴影 |
| H2 标题 | 左侧微信绿竖条 + 渐变背景 |
| H3 标题 | 简洁下划线 |
| 强调文字 | 加粗 + 记号笔绿色高亮 |
| 引用块 | 卡片式设计，圆角灰底 |
| 图片 | 圆角 + 轻阴影 |
| 链接 | 微信蓝 + 虚线下划线 |

## ⚙️ 配置说明

编辑 `config.py` 或设置环境变量：

```python
# === API 配置 ===
DEEPSEEK_API_KEY = "sk-your-key"  # 或 os.getenv("DEEPSEEK_API_KEY")

# === 微信公众号配置 ===
WECHAT_APP_ID = "wx1234..."       # 或 os.getenv("WECHAT_APP_ID")
WECHAT_APP_SECRET = "secret..."   # 或 os.getenv("WECHAT_APP_SECRET")

# === 代理配置 ===
PROXY_URL = "http://127.0.0.1:7898"  # 无需代理设为 None

# === 人设标签 ===
PERSONA_TAGS = ["AI", "DeepSeek", "效率", "工具", ...]
```

## 📦 依赖

```text
Python 3.9+

# 选题雷达
duckduckgo-search, beautifulsoup4, httpx

# 写作智能体
openai

# 排版智能体
markdown-it-py, pygments, premailer, pyperclip, lxml

# 发布智能体
wechatpy, requests
```

安装命令：`pip install -r requirements.txt`

## 🔒 安全说明

- 所有敏感配置支持**环境变量**读取
- 文章和图片仅在**本地 ↔ 微信服务器**之间传输
- 不经过任何第三方服务器
- 请勿将 `config.py` 中的真实密钥提交到公开仓库

## 🤝 作者

**王往AI** - 热爱新兴技术的探索者，专注 AI 工作流的硬核博主

---

*用 AI 帮你偷懒，把省下的时间用来生活。*
