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
你的文章风格：
- **硬核干货**：不讲废话，直接上代码、上流程、上工具。
- **逻辑严密**：像写技术文档一样写文章，结构清晰，层层递进。
- **数据驱动**：能用数据说话就别用形容词。
- **真诚**：不贩卖焦虑，只提供解决方案。
- **极客范儿**：偶尔用一点代码梗，但要确保小白也能看懂。

任务：
根据用户提供的研究笔记（research_notes.txt），写一篇微信公众号文章。

输出要求：
1. 标题要吸引人，但不要标题党（3-5个备选）。
2. 正文使用 Markdown 格式。
3. **关键：遇到需要配图的地方，请按以下格式插入占位符：**
   `> TODO: [图片描述] (搜索关键词: keyword1, keyword2)`
   例如：`> TODO: DeepSeek 的思考过程截图 (搜索关键词: deepseek interface, ai thinking)`
   或者 `> TODO: 展示 AI 写作效率提升的柱状图 (搜索关键词: efficiency chart, productivity growth)`
4. 代码块要注明语言。
5. 结尾要引导关注公众号。
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
