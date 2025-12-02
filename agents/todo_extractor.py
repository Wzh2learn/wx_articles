"""
📋 TODO 提取器 - 从草稿中提取待办事项
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_draft_file, get_todo_file, get_stage_dir

def extract_todos(draft_path):
    """从草稿文件中提取所有 TODO 标记"""
    if not os.path.exists(draft_path):
        print(f"❌ 找不到草稿文件: {draft_path}")
        return []
    
    with open(draft_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # 匹配 (TODO: ...) 或 **TODO: ...** 格式
    pattern = r'\*?\*?\(?\s*TODO[：:]\s*([^)）\n]+)\s*\)?\*?\*?'
    matches = re.findall(pattern, content, re.IGNORECASE)
    
    return [m.strip() for m in matches if m.strip()]

def main():
    print("\n" + "="*50)
    print("📋 TODO 提取器 - 王往AI")
    print("="*50 + "\n")
    
    draft_path = get_draft_file()
    print(f"📁 草稿路径: {draft_path}\n")
    
    todos = extract_todos(draft_path)
    
    if not todos:
        print("✅ 没有找到 TODO 标记，草稿已完整！")
        return
    
    print(f"📌 共找到 {len(todos)} 个待办事项：\n")
    print("-" * 40)
    for i, todo in enumerate(todos, 1):
        print(f"  {i}. {todo}")
    print("-" * 40)
    
    # 保存到草稿目录
    todo_file = get_todo_file()
    with open(todo_file, "w", encoding="utf-8") as f:
        f.write(f"# 待办事项清单\n\n")
        f.write(f"来源: {draft_path}\n\n")
        for i, todo in enumerate(todos, 1):
            f.write(f"[ ] {i}. {todo}\n")
    
    print(f"\n💾 已保存到: {todo_file}")
    print(f"\n� 下一步：")
    print(f"   1. 截图保存到: {get_stage_dir('assets')}")
    print(f"   2. 编辑 {draft_path} 替换 TODO 标记")
    print(f"   3. 润色完成后保存到: {get_stage_dir('publish')}/final.md")

if __name__ == "__main__":
    main()
