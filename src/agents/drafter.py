"""
✍️ 写作智能体 (Drafter) v4.2 (Hardcore Edition)
核心策略：
1. DeepSeek Reasoner：使用深度推理模型，确保逻辑严密。
2. 专家验证约束：拒绝模棱两可，建立权威人设。
3. 绝对禁忌：严禁推荐国内付费套壳工具，锁死“高阶玩法”为技术流。
4. v4.1 新增：混合配图机制 (TODO + AUTO_IMG)
5. v4.2 新增：COVER_PROMPT 英文封面描述 + Draft->Final 直通车
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re
import json
import httpx
import shutil
from openai import OpenAI
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, PROXY_URL, REQUEST_TIMEOUT, get_research_notes_file, get_draft_file, get_final_file, get_today_dir, get_stage_dir, get_logger, retryable, track_cost
from agents.illustrator import IllustratorAgent

from datetime import datetime


import time
from agents import screenshotter

logger = get_logger(__name__)

def _backup_file(path: str):
    """Create a timestamped backup if the file exists."""
    if os.path.exists(path):
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = f"{path}.bak-{ts}"
        shutil.copy(path, backup_path)
        logger.info(f"🛡️ Created backup: {backup_path}")

def get_system_prompt(topic: str = None, strategic_intent: str = None, visual_script: dict = None):
    """
    动态生成系统提示词 (注入反套壳/专家人设约束/视觉脚本)
    包含：
    1. 时效性注入
    2. 专家验证约束
    3. 绝对禁忌 (红线)
    4. 视觉脚本 (如果存在)
    """
    today = datetime.now().strftime('%Y年%m月')
    strategic_block = f"\n\n## 🎯 最高指令：选题策划书（必须逐条执行）\n{strategic_intent}\n" if strategic_intent else ""
    topic_block = f"\n\n## 文章标题约束\n文章标题必须使用：{topic}\n" if topic else ""
    
    visual_block = ""
    if visual_script:
        vs_str = json.dumps(visual_script, indent=2, ensure_ascii=False)
        visual_block = f"""
## 🎨 强制视觉脚本 (Visual Script Execution)
你收到了经过策划的视觉脚本，请**严格按照**以下脚本插入配图占位符，不要自己随意发挥：

【视觉脚本内容】
{vs_str}

【执行要求】
1. **封面图**：必须在文章末尾使用脚本中的 `cover_prompt`。
   格式：`> COVER_PROMPT: [脚本中的 cover_prompt]`
   
2. **文中插图**：请将脚本中的 `illustrations` 列表里的图片，根据上下文逻辑插入到文章最合适的位置。
   - 如果 type 是 "screenshot" -> 使用 `> TODO: [description] (搜索关键词: ...)`
   - 如果 type 是 "art" -> 使用 `> AUTO_IMG: [description]`
   
⚠️ **注意**：脚本中的 description 如果是英文（针对 art），请直接填入 AUTO_IMG；如果是中文（针对 screenshot），请填入 TODO。确保所有脚本中的图片都被使用！
"""

    return f"""
    {visual_block}
你叫"王往AI"。热爱新兴技术的探索者，专注 AI 工作流的硬核博主。

## ⚠️ 时效性要求（重要！）
当前时间是 {today}。文章必须体现最新时效性：
- 如果笔记中包含 2024 年或更早的旧版本信息（如 DeepSeek R1、GPT-4 发布等），请将其作为"历史背景"一笔带过
- 重点描述当前最新的技术现状和功能更新
- 使用"最新"、"刚刚更新"等时效性词汇时要谨慎，确保确实是近期内容

## 专家验证约束（针对不确定的工具）
- **必须**以专家身份发言，**拒绝**使用“据说”、“可能”、“有网友表示”等不确定词汇。
- 如果笔记中某工具的有效性存在争议（例如，小发猫），请使用“我经过严格测试，最终筛选出...”的句式，**直接给出你的最终判断**（信或不信），并引用批判性证据。
- **目标**：文章必须给人“这是最终答案”的自信感。

## 你的写作风格
- **口语化**：像朋友聊天一样，不是写论文。用"你"而不是"读者"。
- **硬核干货**：直接给方案、给步骤、给代码，不废话。
- **情绪节奏**：开头抓痛点，中间给爽感（"就这么简单！"），结尾留期待。
- **真诚**：不贩卖焦虑，只提供解决方案。

## 🚫 绝对禁忌（红线）
1. **严禁推荐任何“国内付费套壳工具”**（如笔灵、小发猫等）。不要说它们“效果尚可”或“适合有预算的人”，要直接定义为“不推荐”、“没必要花钱”。
2. **“高阶玩法”只能是技术流**：
- ❌ 错误的高阶：推荐买某某会员。
- ✅ 正确的高阶：使用 DeepSeek 的 **API 接入**、使用 **Ollama 本地部署**、使用 **Python 脚本批量处理**、或者 **多轮提示词迭代策略**。
3. **严禁推荐 API 中转商/分销商**：如“老张AI / laozhang.ai”、“API2D”等。我们只教用户用 **官方 API** 或 **开源本地模型 (Ollama/vLLM)**。如果为了省钱，请教他们用“开源模型”，而不是“二贩子服务”。

## 战略意图对齐（必须执行）
你会收到一份“选题策划书（strategic_intent）”，它是本次写作的最高指令：
- 开头必须回应策划书的“心理锚点”，用 1-2 句话把读者情绪钉住
- 文章结构必须覆盖策划书的“核心看点”，不得漏项
- 严禁自由发挥导致偏题：如果研究笔记里有内容不服务于策划书目标，宁可不写
- 如遇冲突：以“可引用证据”为准，同时在文中点出“与策划书假设不一致”的地方
{topic_block}{strategic_block}{visual_block}

## 决策指令（聚焦唯一最佳实践）
当研究笔记中出现多个解决同一问题的工具/路线（例如 VSCode 插件 vs Cursor 原生功能）时：
- **请选择体验最“原生”、最“顺滑”的一个作为主推**，给出一条从 0 到 1 可复现的最短路径
- 另一个仅作为备选一句带过，或直接不提
- 不要做“大拼盘罗列”，你必须给读者“唯一主推款”的明确结论

## 结构调整指令
- 在【避坑指南】部分：直接点名“笔灵”、“PaperYY”等工具虽能保留格式，但本质是信息差割韭菜。
- 在【高阶玩法】部分：必须讲**“如何用 DeepSeek 深度思考模式”** 或者 **“如何用 Word/WPS 自带功能配合 AI 恢复格式”**，替代付费工具。

## 任务
根据用户提供的研究笔记，写一篇**微信公众号文章**。

## 排版规范（重要！）
1. **禁止论文风格**：不要用"一、二、三"或"1. 2. 3."这种序号开头的大段落！
2. **用小标题分段**：每个小标题用 `##` 或 `###`，标题本身要有吸引力，比如：
- ❌ 错误示范：`## 一、工具介绍`
- ✅ 正确示范：`## 这个工具能帮你省下 20 刀/月`
   - ✅ 正确示范：`## 这个工具能帮你省下 20 刀/月`
3. **短段落**：每段 2-4 行，手机阅读更友好。
4. **重点加粗**：关键数字、工具名、操作步骤用 **加粗**。
5. **适当用 emoji**：但不要过度（每个小标题可以加一个）。

## 文章结构模板
```
# [爆款标题]

[开头 Hook：1-2句话戳痛点，让读者觉得"这说的就是我！"]

## 🔥 [痛点放大]
[描述问题有多烦人，建立共鸣]

## 💡 [解决方案]
[介绍工具/方法，给出"啊哈时刻"]

## 📝 [手把手教程]
[具体步骤，每步一小段]

> TODO: [需要配图的地方] (搜索关键词: xxx)

## ⚠️ [避坑指南]（可选）
[常见问题和解决方法]

## 🎁 [额外福利]（可选）
[进阶技巧或相关资源]

---
**关注我，下次继续聊 AI 工具的骚操作 👆**
```

## 配图占位符格式（v4.2 混合模式）
你有三种配图方式，请根据场景选择：

### 0️⃣ 封面图提示词（必须提供！）
在文章末尾（备选标题之前），你**必须**提供一个英文封面描述：
格式：`> COVER_PROMPT: [English visual description, NO TEXT]`
要求：
- **必须用英文**（Flux 模型对英文理解更好）
- **严禁包含任何文字/标题**（No text, no title, no words）
- 画面要抽象、科技感强、高质感
- 描述具体画面元素，如光效、颜色、构图
示例：
- `> COVER_PROMPT: Abstract cyberpunk cityscape with glowing data streams, isometric view, neon blue and purple, 8k resolution`
- `> COVER_PROMPT: Futuristic AI neural network visualization, floating holographic nodes, dark background with volumetric lighting`
- `> COVER_PROMPT: Minimalist tech illustration of a glowing smartphone with AI assistant emerging as light particles`

### 1️⃣ 实操截图（人工处理 或 自动截图）
适用场景：展示真实界面、操作步骤、软件截图
格式：`> TODO: [截图描述] (搜索关键词: keyword1, keyword2)`

**v4.3 新增 - 自动截图功能**：
如果你需要截取某个官网首页，请按以下格式，系统会自动调用浏览器截图：
格式：`> TODO: [DeepSeek 官网首页] (type="screenshot", url="https://www.deepseek.com")`
要求：
- 必须包含 `type="screenshot"`
- 必须包含有效的 `url="..."`
- URL 必须是官网首页或公开页面，无需登录

示例：`> TODO: [DeepSeek 联网模式开关位置截图] (搜索关键词: DeepSeek, 联网模式)`
示例：`> TODO: [DeepSeek 官网] (type="screenshot", url="https://www.deepseek.com")`

### 2️⃣ AI 素材图（自动生成）
适用场景：抽象概念、氛围图、章节插图、装饰性配图
格式：`> AUTO_IMG: [English visual description, NO TEXT]`
要求：
- **必须用英文描述**（Flux 模型对英文效果更好！）
- **严禁包含任何文字**（No text, no words, no letters）
- 画面要具体、有视觉冲击力
示例：
- `> AUTO_IMG: A glowing AI chip floating in dark space with blue neon lights, cinematic lighting`
- `> AUTO_IMG: Robotic hand typing on holographic keyboard, futuristic office, volumetric fog`
- `> AUTO_IMG: Abstract data flow visualization, glowing particles, dark background, 8k`

ℹ️ **注意**：AUTO_IMG 和 COVER_PROMPT 会在文章生成后自动替换为真实图片链接。

## 备选标题
在文末给出 3-5 个备选标题，格式：
```
---
备选标题：
1. xxx
2. xxx
3. xxx
```
"""

def read_notes(filepath):
    if not os.path.exists(filepath):
        logger.error("❌ 找不到 %s", filepath)
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()

def generate_draft(notes, topic: str = None, strategic_intent: str = None, visual_script: dict = None):
    logger.info("🚀 调用 DeepSeek Reasoner...")
    with httpx.Client(proxy=PROXY_URL, timeout=REQUEST_TIMEOUT) as http_client:
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL, http_client=http_client)
        messages = [
            {"role": "system", "content": get_system_prompt(topic=topic, strategic_intent=strategic_intent, visual_script=visual_script)},
            {"role": "user", "content": f"【选题标题】\n{topic or ''}\n\n【选题策划书 / 战略意图（最高指令）】\n{strategic_intent or ''}\n\n【研究笔记】\n{notes}"}
        ]
        try:
            @retryable
            @track_cost(context="generate_draft")
            def _chat_create():
                return client.chat.completions.create(model="deepseek-reasoner", messages=messages, stream=True)

            response = _chat_create()
            logger.info("%s", "="*20 + " 生成中 " + "="*20)
            collected = []
            for chunk in response:
                if chunk.choices[0].delta.content:
                    c = chunk.choices[0].delta.content
                    sys.stdout.write(c)
                    sys.stdout.flush()
                    collected.append(c)
            sys.stdout.write("\n\n" + "="*50 + "\n")
            sys.stdout.flush()
            return "".join(collected)
        except Exception as e:
            logger.error("❌ 生成失败: %s", e)
            return None


def process_auto_images(content: str, illustrator: IllustratorAgent) -> str:
    """
    v4.1: 后处理逻辑 - 扫描并替换 AUTO_IMG 占位符
    
    Args:
        content: 文章 Markdown 内容
        illustrator: IllustratorAgent 实例
    
    Returns:
        替换后的文章内容
    """
    if not illustrator.is_enabled():
        logger.warning("⚠️ 配图功能未启用，保留 AUTO_IMG 占位符")
        return content
    
    # 匹配 AUTO_IMG 占位符: > AUTO_IMG: xxx
    pattern = r'>\s*AUTO_IMG:\s*(.+?)(?:\n|$)'
    matches = re.findall(pattern, content)
    
    if not matches:
        logger.info("📷 未发现 AUTO_IMG 占位符")
        return content
    
    logger.info(f"🎨 发现 {len(matches)} 个 AUTO_IMG 占位符，开始生成...")
    
    for i, description in enumerate(matches, 1):
        description = description.strip()
        logger.info(f"   [{i}/{len(matches)}] 生成: {description[:40]}...")
        
        # 生成素材图
        image_path = illustrator.generate_material(description)
        
        if image_path:
            # 替换占位符为真实图片
            old_placeholder = f"> AUTO_IMG: {description}"
            new_image_tag = f"![素材图]({image_path})"
            content = content.replace(old_placeholder, new_image_tag, 1)
            logger.info(f"   ✅ 已替换为: {image_path}")
        else:
            logger.warning(f"   ⚠️ 生成失败，保留占位符")
    
    return content


def process_screenshots(content: str) -> str:
    """
    v4.3: 扫描 TODO 标签，自动处理网页截图
    格式: > TODO: [...] (type="screenshot", url="...")
    """
    # 匹配 TODO 标签
    # 格式: > TODO: [description] (params)
    pattern = r'>\s*TODO:\s*\[(.*?)\]\s*\((.*?)\)'
    
    matches = list(re.finditer(pattern, content))
    if not matches:
        return content
        
    logger.info(f"📸 扫描到 {len(matches)} 个 TODO 项，正在检查自动截图任务...")
    
    offset = 0
    new_content = content
    
    for match in matches:
        full_match = match.group(0)
        desc = match.group(1)
        params_str = match.group(2)
        
        # 检查是否包含 type="screenshot" 和 url
        if 'type="screenshot"' in params_str or "type='screenshot'" in params_str:
            # 提取 URL
            url_match = re.search(r'url=["\'](.*?)["\']', params_str)
            if url_match:
                url = url_match.group(1)
                logger.info(f"   🔭 发现截图任务: {desc} -> {url}")
                
                # 定义保存路径
                filename = f"screenshot_{int(time.time())}_{abs(hash(url)) % 10000}.png"
                assets_dir = get_stage_dir('assets')
                output_path = os.path.join(assets_dir, filename)
                
                # 相对路径用于 Markdown
                # 假设运行目录是项目根目录，图片在 5_assets
                # 但最终 md 可能在 3_drafts 或 4_publish，引用 5_assets 需要 ../5_assets 或者绝对路径
                # 为了兼容性，通常使用相对路径。
                # 如果 draft.md 在 3_drafts/draft.md, assets 在 5_assets/
                # 引用应该是 ../5_assets/xxx.png
                # 但这里我们简单起见，假设 draft.md 和 assets 都在 working date 目录下
                # 我们使用相对路径 "5_assets/xxx.png" 如果最终发布是把所有东西打包
                # 或者使用 "../5_assets/filename"
                
                # 修正：get_stage_dir 返回的是 absolute path
                # 我们需要生成 markdown 中使用的路径
                # 简单处理：使用相对路径 "../5_assets/" (因为 draft 在 3_drafts)
                md_rel_path = f"../5_assets/{filename}"
                
                # 执行截图
                if screenshotter.capture_homepage(url, output_path):
                    replacement = f"![官网截图]({md_rel_path})\n> *自动截图: {desc}*"
                    new_content = new_content.replace(full_match, replacement, 1)
                else:
                    logger.warning(f"   ⚠️ 截图失败，将标注为需要人工截图")
                    failure_note = f"> ⚠️ AUTO-SCREENSHOT FAILED: {desc}. Please capture manually."
                    new_content = new_content.replace(full_match, failure_note, 1)
    
    return new_content


def extract_cover_prompt(content: str) -> tuple[str, str]:
    """
    v4.2: 从文章中提取 COVER_PROMPT 英文描述
    
    Args:
        content: 文章 Markdown 内容
    
    Returns:
        (cover_prompt, cleaned_content): 封面提示词和移除占位符后的内容
    """
    pattern = r'>\s*COVER_PROMPT:\s*(.+?)(?:\n|$)'
    match = re.search(pattern, content)
    
    if match:
        cover_prompt = match.group(1).strip()
        # 移除占位符行
        cleaned_content = re.sub(pattern, '', content)
        logger.info(f"   🎯 发现 COVER_PROMPT: {cover_prompt[:50]}...")
        return cover_prompt, cleaned_content
    
    return None, content


def add_cover_image(content: str, topic: str, illustrator: IllustratorAgent) -> str:
    """
    v4.2: 在文章开头插入 AI 生成的封面图
    优先使用 COVER_PROMPT 英文描述，降级使用中文标题
    
    Args:
        content: 文章 Markdown 内容
        topic: 文章主题/标题
        illustrator: IllustratorAgent 实例
    
    Returns:
        带封面图的文章内容
    """
    if not illustrator.is_enabled():
        logger.warning("⚠️ 配图功能未启用，跳过封面生成")
        return content
    
    logger.info("🖼️ 正在生成封面图...")
    
    # v4.2: 优先使用文章中的 COVER_PROMPT
    cover_prompt, content = extract_cover_prompt(content)
    
    if cover_prompt:
        logger.info(f"   🎨 使用英文 COVER_PROMPT 生成封面")
        cover_path = illustrator.generate_cover(cover_prompt, use_raw_prompt=True)
    else:
        logger.warning(f"   ⚠️ 未找到 COVER_PROMPT，降级使用中文标题")
        cover_path = illustrator.generate_cover(topic or "AI 技术文章")
    
    if cover_path:
        # 在文章开头插入封面图
        cover_tag = f"![封面]({cover_path})\n\n"
        content = cover_tag + content
        logger.info(f"   ✅ 封面已插入: {cover_path}")
    else:
        logger.warning("   ⚠️ 封面生成失败")
    
    return content

def main(topic: str = None, strategic_intent: str = None, visual_script: dict = None, auto_illustrate: bool = True):
    """
    写作智能体主入口
    
    Args:
        topic: 文章主题/标题
        strategic_intent: 选题策划书
        visual_script: 视觉脚本 (JSON)
        auto_illustrate: 是否启用自动配图 (v4.1)，默认开启
    """
    logger.info("%s", "="*60)
    logger.info("✍️ 写作智能体 v4.2 - 王往AI")
    logger.info("%s", "="*60)
    if visual_script:
        logger.info("🎨 已加载视觉脚本")
        
    logger.info("📁 今日工作目录: %s", get_today_dir())
    
    notes_file = get_research_notes_file()
    logger.info("📖 读取 %s...", notes_file)
    
    notes = read_notes(notes_file)
    if not notes:
        logger.warning("💡 请先在以下位置创建研究笔记：%s", notes_file)
        return
    logger.info("✓ 共 %s 字符", len(notes))
    
    # Step 1: 生成初稿
    draft = generate_draft(notes, topic=topic, strategic_intent=strategic_intent, visual_script=visual_script)
    if not draft:
        return
    
    # Step 2: v4.1 自动配图处理
    if auto_illustrate:
        logger.info("\n" + "="*40)
        logger.info("🎨 v4.2 智能配图系统 (光影质感流)")
        logger.info("="*40)
        
        illustrator = IllustratorAgent()
        
        if illustrator.is_enabled():
            # 2a. 生成封面图并插入开头
            draft = add_cover_image(draft, topic, illustrator)
            
            # 2b. 处理文中的 AUTO_IMG 占位符
            draft = process_auto_images(draft, illustrator)
        else:
            logger.info("⏭️ 配图功能未启用，跳过自动配图")
            logger.info("   💡 如需启用，请配置 REPLICATE_API_TOKEN")

    # Step 2.5: v4.3 自动截图处理
    draft = process_screenshots(draft)
    
    # Step 3: 保存最终草稿
    draft_file = get_draft_file()
    _backup_file(draft_file)
    with open(draft_file, "w", encoding="utf-8") as f:
        f.write(draft)
    logger.info("✅ 初稿已保存: %s", draft_file)
    
    # Step 4 (v4.2 新增): 自动同步到 final.md (草稿即定稿)
    final_file = get_final_file()
    _backup_file(final_file)
    with open(final_file, "w", encoding="utf-8") as f:
        f.write(draft)
    logger.info("✅ 已同步生成 Final 版本: %s", final_file)
    
    # Step 5: 下一步提示
    logger.info("\n📌 下一步：")
    logger.info("   1. 运行 python run.py todo 查看待补充的 TODO 截图")
    logger.info("   2. 手动截图保存到 %s", get_stage_dir('assets'))
    logger.info("   3. 💡 后续请直接修改定稿: %s", final_file)
    
    # 统计配图情况
    todo_count = len(re.findall(r'>\s*TODO:', draft))
    auto_img_count = len(re.findall(r'!\[素材图\]', draft))
    cover_count = 1 if '![封面]' in draft else 0
    
    logger.info("\n📊 配图统计：")
    logger.info(f"   - AI 封面图: {cover_count} 张")
    logger.info(f"   - AI 素材图: {auto_img_count} 张")
    logger.info(f"   - 待手动截图 (TODO): {todo_count} 处")


if __name__ == "__main__":
    main()
