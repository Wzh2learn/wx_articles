"""
✍️ 写作智能体 (Drafter) v2.0 - 生成微信公众号初稿
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from openai import OpenAI
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, PROXY_URL, REQUEST_TIMEOUT, get_research_notes_file, get_draft_file, get_today_dir, get_stage_dir

SYSTEM_PROMPT = """
你叫"王往AI"。热爱新兴技术的探索者，专注 AI 工作流的硬核博主。

## 你的写作风格
- **口语化**：像朋友聊天一样，不是写论文。用"你"而不是"读者"。
- **硬核干货**：直接给方案、给步骤、给代码，不废话。
- **情绪节奏**：开头抓痛点，中间给爽感（"就这么简单！"），结尾留期待。
- **真诚**：不贩卖焦虑，只提供解决方案。

## 任务
根据用户提供的研究笔记，写一篇**微信公众号文章**。

## 排版规范（重要！）
1. **禁止论文风格**：不要用"一、二、三"或"1. 2. 3."这种序号开头的大段落！
2. **用小标题分段**：每个小标题用 `##` 或 `###`，标题本身要有吸引力，比如：
   - ❌ 错误示范：`## 一、工具介绍`
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

## 配图占位符格式
遇到需要配图的地方，插入：
`> TODO: [图片描述] (搜索关键词: keyword1, keyword2)`

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
        print(f"❌ 找不到 {filepath}")
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()

def generate_draft(notes):
    print("🚀 调用 DeepSeek Reasoner...")
    with httpx.Client(proxy=PROXY_URL, timeout=REQUEST_TIMEOUT) as http_client:
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL, http_client=http_client)
        messages = [{"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"【研究笔记】：\n{notes}"}]
        try:
            response = client.chat.completions.create(model="deepseek-reasoner", messages=messages, stream=True)
            print("\n" + "="*20 + " 生成中 " + "="*20 + "\n")
            collected = []
            for chunk in response:
                if chunk.choices[0].delta.content:
                    c = chunk.choices[0].delta.content
                    print(c, end="", flush=True)
                    collected.append(c)
            print("\n\n" + "="*50 + "\n")
            return "".join(collected)
        except Exception as e:
            print(f"❌ 生成失败: {e}")
            return None

def main():
    print("\n" + "="*60 + "\n✍️ 写作智能体 - 王往AI\n" + "="*60 + "\n")
    print(f"📁 今日工作目录: {get_today_dir()}\n")
    
    notes_file = get_research_notes_file()
    print(f"📖 读取 {notes_file}...")
    
    notes = read_notes(notes_file)
    if not notes:
        print(f"\n💡 请先在以下位置创建研究笔记：")
        print(f"   {notes_file}")
        return
    print(f"   ✓ 共 {len(notes)} 字符\n")
    
    draft = generate_draft(notes)
    if draft:
        draft_file = get_draft_file()
        with open(draft_file, "w", encoding="utf-8") as f:
            f.write(draft)
        print(f"✅ 初稿已保存: {draft_file}")
        print(f"\n📌 下一步：")
        print(f"   1. 运行 python run.py todo 查看待补充内容")
        print(f"   2. 截图保存到 {get_stage_dir('assets')}")
        print(f"   3. 润色后保存到 {get_stage_dir('publish')}/final.md")

if __name__ == "__main__":
    main()
