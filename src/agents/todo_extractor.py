"""
📋 TODO 提取器 v4.0 (Hardcore Edition) - 从草稿中提取待办事项
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_draft_file, get_todo_file, get_stage_dir, get_logger


logger = get_logger(__name__)

def extract_todos(draft_path):
    """从草稿文件中提取所有 TODO 标记"""
    if not os.path.exists(draft_path):
        logger.error("❌ 找不到草稿文件: %s", draft_path)
        return []
    
    with open(draft_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # 匹配 (TODO: ...) 或 **TODO: ...** 格式
    pattern = r'\*?\*?\(?\s*TODO[：:]\s*([^)）\n]+)\s*\)?\*?\*?'
    matches = re.findall(pattern, content, re.IGNORECASE)
    
    return [m.strip() for m in matches if m.strip()]

def main():
    logger.info("%s", "="*50)
    logger.info("📋 TODO 提取器 - 王往AI")
    logger.info("%s", "="*50)
    
    draft_path = get_draft_file()
    logger.info("📁 草稿路径: %s", draft_path)
    
    todos = extract_todos(draft_path)
    
    if not todos:
        logger.info("✅ 没有找到 TODO 标记，草稿已完整！")
        return
    
    logger.info("📌 共找到 %s 个待办事项：", len(todos))
    logger.info("%s", "-" * 40)
    for i, todo in enumerate(todos, 1):
        logger.info("  %s. %s", i, todo)
    logger.info("%s", "-" * 40)
    
    # 保存到草稿目录
    todo_file = get_todo_file()
    with open(todo_file, "w", encoding="utf-8") as f:
        f.write(f"# 待办事项清单\n\n")
        f.write(f"来源: {draft_path}\n\n")
        for i, todo in enumerate(todos, 1):
            f.write(f"[ ] {i}. {todo}\n")
    
    logger.info("💾 已保存到: %s", todo_file)
    logger.info("💡 下一步：")
    logger.info("   1. 截图保存到: %s", get_stage_dir('assets'))
    logger.info("   2. 编辑 %s 替换 TODO 标记", draft_path)
    logger.info("   3. 润色完成后保存到: %s/final.md", get_stage_dir('publish'))

if __name__ == "__main__":
    main()
