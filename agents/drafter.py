"""
✍️ 写作智能体 (Drafter) v2.0 - 生成微信公众号初稿
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from openai import OpenAI
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, PROXY_URL, REQUEST_TIMEOUT, RESEARCH_NOTES_FILE, get_draft_file, archive_current_notes, get_today_dir

SYSTEM_PROMPT = """
你叫"王往AI"。前搜广推算法工程师，现专注 AI 工作流的硬核博主。

## 风格
1. **逻辑清晰**：用技术视角解构问题，告诉读者怎么做和为什么。
2. **说人话**：不堆术语，目标受众是"职场想偷懒的小白"。
3. **犀利直接**：拒绝正确的废话，直击痛点。

## 文章结构
1. **痛点引入**：描述痛苦，制造焦虑但马上给解药。
2. **核心实操**：
   * Step 1 DeepSeek 思考：给出核心 Prompt 模板
   * Step 2 Kimi 生成：强调指令细节，提醒追问技巧
   * 避坑指南：指出新手易错点
3. **总结升华**：技术角度点评，强调少加班。
4. **结尾引导**：
   * 正文已给核心 Prompt（显得大方）
   * 话术："Prompt 核心逻辑都写上面了。**想要打包好的懒人包（含3个场景模板）**，关注我，回复【PPT】获取。"

## 格式
* Markdown 格式
* 标题要吸引人
* 截图位置标记：**(TODO: 此处插入 [描述] 的截图)**
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
    print(f"📖 读取 {RESEARCH_NOTES_FILE}...")
    notes = read_notes(RESEARCH_NOTES_FILE)
    if not notes:
        return
    print(f"   ✓ 共 {len(notes)} 字符\n")
    
    # 备份笔记到今日目录
    backup = archive_current_notes()
    if backup:
        print(f"📦 笔记已备份: {backup}\n")
    
    draft = generate_draft(notes)
    if draft:
        draft_file = get_draft_file()
        with open(draft_file, "w", encoding="utf-8") as f:
            f.write(draft)
        print(f"✅ 初稿已保存: {draft_file}")
        print(f"📌 下一步：打开 draft.md，人工润色后保存为 final.md（同目录）")

if __name__ == "__main__":
    main()
