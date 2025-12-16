"""
🎨 排版智能体 (Formatter) v4.2 - 多风格版
支持多种排版风格：green(壹伴绿), blue(科技蓝), orange(暖橙), minimal(极简)
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from datetime import datetime

# 静音 cssutils 日志 (必须在 premailer 导入前设置)
logging.getLogger('cssutils').setLevel(logging.CRITICAL)
import cssutils
cssutils.log.setLevel(logging.CRITICAL)

from markdown_it import MarkdownIt
from pygments import highlight
from pygments.lexers import get_lexer_by_name, TextLexer
from pygments.formatters import HtmlFormatter
from premailer import transform
import pyperclip
from config import get_final_file, get_html_file, get_today_dir, get_stage_dir, get_logger


logger = get_logger(__name__)

# ============================================================================
# 多风格 CSS 模板
# ============================================================================

def _get_base_css():
    """基础样式 - 所有风格共用"""
    return """
body, .article-content { 
    font-family: -apple-system, 'PingFang SC', 'Helvetica Neue', 'Microsoft YaHei', sans-serif; 
    font-size: 16px; 
    line-height: 1.8; 
    color: #333; 
    background: #fff; 
    padding: 20px; 
    letter-spacing: 0.5px;
    text-align: justify;
}
p { margin: 20px 0; min-height: 1em; }
em, i { font-style: italic; color: #666; font-size: 0.95em; }
ul, ol { margin: 20px 0; padding-left: 25px; color: #444; }
li { margin: 8px 0; line-height: 1.7; }
pre { 
    background: #282c34; color: #abb2bf; padding: 15px; border-radius: 6px; 
    overflow-x: auto; margin: 25px 0; line-height: 1.5; font-size: 14px;
    font-family: Consolas, 'Courier New', monospace;
}
code { font-family: Consolas, 'Courier New', monospace; }
p code, li code { background: #f0f0f0; color: #c7254e; padding: 2px 5px; border-radius: 3px; font-size: 0.9em; margin: 0 2px; }
a { color: #576b95; text-decoration: none; border-bottom: 1px dashed #576b95; padding-bottom: 1px; }
img { display: block; max-width: 100%; border-radius: 6px; margin: 25px auto; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
hr { border: none; height: 1px; background: #e0e0e0; margin: 40px 0; }
.todo-marker { display: block; background: #fff9c4; border: 2px dashed #fbc02d; border-radius: 8px; padding: 20px; margin: 30px 0; text-align: center; color: #f57f17; font-size: 15px; font-weight: bold; }
table { width: 100%; border-collapse: collapse; margin: 25px 0; font-size: 14px; }
th { background: #f2f2f2; color: #333; font-weight: bold; padding: 12px 10px; text-align: left; border-bottom: 2px solid #ddd; }
td { padding: 12px 10px; border-bottom: 1px solid #eee; color: #555; }
"""

STYLE_TEMPLATES = {
    # ========== 壹伴绿 - 经典微信风格 ==========
    "green": {
        "name": "壹伴绿",
        "accent": "#07c160",
        "css": """
h1 { font-size: 22px; font-weight: bold; text-align: center; color: #1f2329; margin: 40px 0 20px; line-height: 1.4; }
h2 { font-size: 18px; font-weight: bold; color: #1f2329; margin: 40px 0 20px; padding: 8px 15px; border-left: 4px solid #07c160; background-color: rgba(7, 193, 96, 0.08); border-radius: 0 4px 4px 0; }
h3 { font-size: 17px; font-weight: bold; color: #1f2329; margin: 30px 0 15px; padding-bottom: 5px; border-bottom: 1px solid #eee; }
strong, b { font-weight: bold; color: #07c160; background: rgba(7, 193, 96, 0.08); padding: 0 3px; border-radius: 2px; }
blockquote { margin: 25px 0; padding: 20px; background: #f7f7f7; border-left: 6px solid #07c160; color: #555; font-size: 15px; border-radius: 4px; }
"""
    },
    
    # ========== 科技蓝 - 极客风格 ==========
    "blue": {
        "name": "科技蓝",
        "accent": "#1890ff",
        "css": """
h1 { font-size: 22px; font-weight: bold; text-align: center; color: #1890ff; margin: 40px 0 20px; line-height: 1.4; padding-bottom: 10px; border-bottom: 2px solid #1890ff; }
h2 { font-size: 18px; font-weight: bold; color: #fff; margin: 40px 0 20px; padding: 10px 20px; background: linear-gradient(135deg, #1890ff, #096dd9); border-radius: 4px; }
h3 { font-size: 17px; font-weight: bold; color: #1890ff; margin: 30px 0 15px; padding-left: 12px; border-left: 3px solid #1890ff; }
strong, b { font-weight: bold; color: #1890ff; }
blockquote { margin: 25px 0; padding: 20px; background: linear-gradient(135deg, #e6f7ff, #fff); border-left: 6px solid #1890ff; color: #555; font-size: 15px; border-radius: 4px; }
p code, li code { background: #e6f7ff; color: #1890ff; padding: 2px 5px; border-radius: 3px; font-size: 0.9em; }
"""
    },
    
    # ========== 暖橙 - 活力风格 ==========
    "orange": {
        "name": "暖橙活力",
        "accent": "#fa8c16",
        "css": """
h1 { font-size: 22px; font-weight: bold; text-align: center; color: #d46b08; margin: 40px 0 20px; line-height: 1.4; }
h2 { font-size: 18px; font-weight: bold; color: #d46b08; margin: 40px 0 20px; padding: 10px 15px; background: linear-gradient(to right, #fff7e6, #fff); border-left: 5px solid #fa8c16; border-radius: 0 8px 8px 0; }
h3 { font-size: 17px; font-weight: bold; color: #d46b08; margin: 30px 0 15px; }
strong, b { font-weight: bold; color: #fa8c16; background: rgba(250, 140, 22, 0.1); padding: 0 3px; border-radius: 2px; }
blockquote { margin: 25px 0; padding: 20px; background: #fffbe6; border-left: 6px solid #faad14; color: #555; font-size: 15px; border-radius: 4px; }
p code, li code { background: #fff7e6; color: #d46b08; padding: 2px 5px; border-radius: 3px; font-size: 0.9em; }
"""
    },
    
    # ========== 极简黑白 - 专业风格 ==========
    "minimal": {
        "name": "极简黑白",
        "accent": "#333",
        "css": """
h1 { font-size: 24px; font-weight: 900; text-align: center; color: #000; margin: 50px 0 25px; line-height: 1.3; letter-spacing: 2px; }
h2 { font-size: 18px; font-weight: 700; color: #000; margin: 45px 0 20px; padding-bottom: 8px; border-bottom: 3px solid #000; text-transform: uppercase; letter-spacing: 1px; }
h3 { font-size: 16px; font-weight: 600; color: #333; margin: 30px 0 15px; }
strong, b { font-weight: 700; color: #000; }
blockquote { margin: 25px 0; padding: 25px; background: #f5f5f5; border-left: none; border-top: 2px solid #000; border-bottom: 2px solid #000; color: #333; font-size: 15px; font-style: italic; }
p code, li code { background: #f0f0f0; color: #333; padding: 2px 5px; border-radius: 0; font-size: 0.9em; border: 1px solid #ddd; }
a { color: #000; border-bottom: 1px solid #000; }
"""
    },
    
    # ========== 深紫优雅 - 高端风格 ==========
    "purple": {
        "name": "深紫优雅",
        "accent": "#722ed1",
        "css": """
h1 { font-size: 22px; font-weight: bold; text-align: center; color: #531dab; margin: 40px 0 20px; line-height: 1.4; }
h2 { font-size: 18px; font-weight: bold; color: #fff; margin: 40px 0 20px; padding: 10px 20px; background: linear-gradient(135deg, #722ed1, #531dab); border-radius: 25px; text-align: center; }
h3 { font-size: 17px; font-weight: bold; color: #722ed1; margin: 30px 0 15px; padding-left: 12px; border-left: 3px solid #722ed1; }
strong, b { font-weight: bold; color: #722ed1; background: rgba(114, 46, 209, 0.08); padding: 0 3px; border-radius: 2px; }
blockquote { margin: 25px 0; padding: 20px; background: linear-gradient(135deg, #f9f0ff, #fff); border-left: 6px solid #722ed1; color: #555; font-size: 15px; border-radius: 4px; }
p code, li code { background: #f9f0ff; color: #722ed1; padding: 2px 5px; border-radius: 3px; font-size: 0.9em; }
"""
    },
}

def get_style_css(style_name: str = "green") -> str:
    """获取指定风格的完整 CSS"""
    if style_name not in STYLE_TEMPLATES:
        logger.warning(f"未知风格 '{style_name}'，使用默认 green 风格")
        style_name = "green"
    
    base = _get_base_css()
    style = STYLE_TEMPLATES[style_name]["css"]
    return base + style

# 保持向后兼容
WECHAT_CSS = get_style_css("green")

def highlight_code(code, lang):
    try:
        lexer = get_lexer_by_name(lang, stripall=True)
    except:
        lexer = TextLexer()
    formatter = HtmlFormatter(nowrap=True, cssclass='highlight', style='monokai')
    return f'<pre><code class="language-{lang}">{highlight(code, lexer, formatter)}</code></pre>'

def convert_md_to_html(md_content):
    # 移除所有图片语法，替换为占位符，方便人工插图
    def replace_img(match):
        alt = match.group(1)
        return f'<div style="background:#f0f0f0; border:2px dashed #ccc; padding:20px; text-align:center; color:#666; margin:20px 0;">🖼️ 请在此处插入图片：{alt}</div>'
    
    # 匹配 ![]()
    md_content = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', replace_img, md_content)
    
    md = MarkdownIt('commonmark', {'html': True, 'typographer': True})
    md.enable('table').enable('strikethrough')
    html = md.render(md_content)
    # 代码块高亮
    def replace_code(m):
        code = m.group(2).replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
        return highlight_code(code, m.group(1))
    html = re.sub(r'<pre><code class="language-(\w+)">(.*?)</code></pre>', replace_code, html, flags=re.DOTALL)
    html = re.sub(r'<pre><code>(.*?)</code></pre>', lambda m: highlight_code(m.group(1).replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&'), 'text'), html, flags=re.DOTALL)
    # TODO 标记 (匹配 Markdown 转换后的 <strong> 标签)
    html = re.sub(r'<strong>\(TODO:([^)]+)\)</strong>', r'<div class="todo-marker">📸 TODO:\1</div>', html)
    # 也匹配原始 Markdown 格式（以防万一）
    html = re.sub(r'\*\*\(TODO:([^)]+)\)\*\*', r'<div class="todo-marker">📸 TODO:\1</div>', html)
    return html

def inline_css(html, style_name: str = "green"):
    """将 CSS 内联到 HTML 元素中，生成适合复制到微信的富文本"""
    css = get_style_css(style_name)
    style_info = STYLE_TEMPLATES.get(style_name, STYLE_TEMPLATES["green"])
    accent = style_info["accent"]
    
    full = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>微信公众号文章预览</title>
    <style>{css}</style>
</head>
<body style="max-width: 600px; margin: 40px auto; padding: 20px;">
    <div class="article-content">{html}</div>
    <div style="margin-top: 40px; padding: 20px; background: {accent}15; border-radius: 8px; text-align: center; border: 1px solid {accent}30;">
        <p style="color: {accent}; font-weight: bold; margin: 0;">📋 复制方法：</p>
        <p style="color: #555; margin: 10px 0 0 0;">全选上方内容 (Ctrl+A) → 复制 (Ctrl+C) → 粘贴到公众号<strong>普通编辑模式</strong></p>
        <p style="color: #999; margin: 10px 0 0 0; font-size: 13px;">⚠️ 图片需在公众号后台手动上传替换占位符</p>
    </div>
</body>
</html>"""
    try:
        inlined = transform(full, remove_classes=False, keep_style_tags=True)
        return inlined
    except Exception as e:
        logger.warning("⚠️ CSS内联失败: %s", e)
        return full

def list_styles():
    """列出所有可用风格"""
    print("\n🎨 可用排版风格：")
    print("-" * 40)
    for key, info in STYLE_TEMPLATES.items():
        print(f"  {key:10} - {info['name']} (主色: {info['accent']})")
    print("-" * 40)
    print("使用方法: python run.py format -s <风格名>")
    print("例如: python run.py format -s blue\n")

def main(style: str = "green"):
    """
    排版主函数
    
    Args:
        style: 排版风格，可选 green/blue/orange/minimal/purple
    """
    if style not in STYLE_TEMPLATES:
        logger.warning(f"未知风格 '{style}'，可用风格: {', '.join(STYLE_TEMPLATES.keys())}")
        style = "green"
    
    style_info = STYLE_TEMPLATES[style]
    
    logger.info("%s", "="*60)
    logger.info("🎨 排版智能体 v4.2 - %s风格", style_info["name"])
    logger.info("%s", "="*60)

    final_file = get_final_file()
    html_file = get_html_file()

    logger.info("📁 今日工作目录: %s", get_today_dir())
    logger.info("📖 读取 %s...", final_file)
    
    if not os.path.exists(final_file):
        logger.error("❌ 找不到 %s", final_file)
        logger.error("   请先将润色后的定稿保存到: %s/final.md", get_stage_dir('publish'))
        return

    try:
        mtime = os.path.getmtime(final_file)
        logger.info("🕒 输入文件最后修改时间: %s", datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S'))
    except Exception:
        pass
    
    with open(final_file, "r", encoding="utf-8") as f:
        md = f.read()
    logger.info("✓ 共 %s 字符", len(md))
    
    logger.info("🔄 转换 Markdown -> HTML...")
    html = convert_md_to_html(md)
    logger.info("🎨 应用 %s 风格...", style_info["name"])
    final = inline_css(html, style_name=style)
    
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(final)
    logger.info("📄 已保存: %s", html_file)
    
    try:
        pyperclip.copy(final)
        logger.info("📋 已复制到剪贴板！")
    except Exception:
        logger.warning("⚠️ 复制失败，请手动复制 output.html")
    
    logger.info("%s", "="*60)
    logger.info("✅ 排版完成！风格: %s", style_info["name"])
    logger.info("📌 下一步（重要！）：")
    logger.info("   1. 用浏览器打开: %s", html_file)
    logger.info("   2. 在页面上 Ctrl+A 全选内容")
    logger.info("   3. Ctrl+C 复制")
    logger.info("   4. 到公众号【普通编辑模式】Ctrl+V 粘贴")
    logger.info("   5. ⚠️ 遇到虚线框占位符时，请手动上传并插入对应图片！")
    logger.info("%s", "="*60)
    logger.info("💡 其他风格: %s", ", ".join(STYLE_TEMPLATES.keys()))

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="微信公众号排版智能体")
    parser.add_argument("-s", "--style", default="green", 
                        choices=list(STYLE_TEMPLATES.keys()),
                        help="排版风格 (默认: green)")
    parser.add_argument("--list", action="store_true", help="列出所有可用风格")
    args = parser.parse_args()
    
    if args.list:
        list_styles()
    else:
        main(style=args.style)
