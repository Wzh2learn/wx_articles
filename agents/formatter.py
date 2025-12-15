"""
🎨 排版智能体 (Formatter) v4.0 (Hardcore Edition)
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from datetime import datetime

from markdown_it import MarkdownIt
from pygments import highlight
from pygments.lexers import get_lexer_by_name, TextLexer
from pygments.formatters import HtmlFormatter
from premailer import transform
import pyperclip
from config import get_final_file, get_html_file, get_today_dir, get_stage_dir

# 静音 cssutils 日志
logging.getLogger('cssutils').setLevel(logging.CRITICAL)

WECHAT_CSS = """
/* 微信公众号高级排版 - 壹伴风格 */
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

/* 段落 */
p { 
    margin: 20px 0; 
    min-height: 1em; 
}

/* 标题 - 带有设计感的样式 */
h1 { 
    font-size: 22px; 
    font-weight: bold; 
    text-align: center; 
    color: #1f2329; 
    margin: 40px 0 20px; 
    line-height: 1.4;
}

/* 二级标题 - 左侧竖线 + 背景色块 */
h2 { 
    display: inline-block;
    font-size: 18px; 
    font-weight: bold; 
    color: #1f2329; 
    margin: 40px 0 20px; 
    padding: 5px 15px; 
    border-left: 4px solid #07c160; /* 微信绿 */
    background: linear-gradient(to right, rgba(7, 193, 96, 0.1), transparent);
    border-radius: 0 4px 4px 0;
    width: 100%;
    box-sizing: border-box;
}

/* 三级标题 - 简洁下划线 */
h3 { 
    font-size: 17px; 
    font-weight: bold; 
    color: #1f2329; 
    margin: 30px 0 15px; 
    padding-bottom: 5px;
    border-bottom: 1px solid #eee;
}

/* 强调文字 - 记号笔效果 */
strong, b { 
    font-weight: bold; 
    color: #07c160; 
    background: rgba(7, 193, 96, 0.08);
    padding: 0 2px;
    border-radius: 2px;
}

em, i { 
    font-style: italic; 
    color: #666; 
    font-size: 0.95em;
}

/* 引用块 - 卡片式设计 */
blockquote { 
    margin: 25px 0; 
    padding: 20px; 
    background: #f7f7f7; 
    border-left: 6px solid #ddd; 
    color: #555; 
    font-size: 15px; 
    border-radius: 4px;
    line-height: 1.7;
}

/* 列表 - 优化缩进 */
ul, ol { 
    margin: 20px 0; 
    padding-left: 25px; 
    color: #444;
}
li { 
    margin: 8px 0; 
    line-height: 1.7;
}

/* 代码块 - 简洁深色模式 */
pre { 
    background: #282c34; 
    color: #abb2bf; 
    padding: 15px; 
    border-radius: 6px; 
    overflow-x: auto; 
    margin: 25px 0; 
    line-height: 1.5;
    font-size: 14px;
    font-family: Consolas, 'Courier New', monospace;
    -webkit-overflow-scrolling: touch; /* 移动端滑动流畅 */
}
code {
    font-family: Consolas, 'Courier New', monospace;
}
/* 行内代码 */
p code, li code { 
    background: #f0f0f0; 
    color: #c7254e; 
    padding: 2px 5px; 
    border-radius: 3px; 
    font-size: 0.9em; 
    margin: 0 2px;
}

/* 链接 */
a { 
    color: #576b95; 
    text-decoration: none; 
    border-bottom: 1px dashed #576b95;
    padding-bottom: 1px;
}

/* 图片 - 圆角 + 阴影 */
img { 
    display: block; 
    max-width: 100%; 
    border-radius: 6px; 
    margin: 25px auto; 
    box-shadow: 0 2px 10px rgba(0,0,0,0.05); 
}

/* 分割线 */
hr { 
    border: none; 
    height: 1px; 
    background: #e0e0e0; 
    margin: 40px 0; 
}

/* TODO 占位符 - 醒目提示 */
.todo-marker { 
    display: block;
    background: #fff9c4; 
    border: 2px dashed #fbc02d; 
    border-radius: 8px; 
    padding: 20px; 
    margin: 30px 0; 
    text-align: center; 
    color: #f57f17; 
    font-size: 15px; 
    font-weight: bold;
    box-shadow: 0 2px 6px rgba(0,0,0,0.05);
}

/* 表格 */
table { 
    width: 100%; 
    border-collapse: collapse; 
    margin: 25px 0; 
    font-size: 14px; 
}
th { 
    background: #f2f2f2; 
    color: #333; 
    font-weight: bold; 
    padding: 12px 10px; 
    text-align: left; 
    border-bottom: 2px solid #ddd;
}
td { 
    padding: 12px 10px; 
    border-bottom: 1px solid #eee; 
    color: #555;
}
tr:nth-child(even) { background: #fcfcfc; }
"""

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

def inline_css(html):
    """将 CSS 内联到 HTML 元素中，生成适合复制到微信的富文本"""
    full = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>微信公众号文章预览</title>
    <style>{WECHAT_CSS}</style>
</head>
<body style="max-width: 600px; margin: 40px auto; padding: 20px;">
    <div class="article-content">{html}</div>
    <div style="margin-top: 40px; padding: 20px; background: #e8f5e9; border-radius: 8px; text-align: center;">
        <p style="color: #2e7d32; font-weight: bold; margin: 0;">📋 复制方法：</p>
        <p style="color: #555; margin: 10px 0 0 0;">全选上方内容 (Ctrl+A) → 复制 (Ctrl+C) → 粘贴到公众号<strong>普通编辑模式</strong></p>
        <p style="color: #999; margin: 10px 0 0 0; font-size: 13px;">⚠️ 图片需在公众号后台手动上传替换占位符</p>
    </div>
</body>
</html>"""
    try:
        inlined = transform(full, remove_classes=False, keep_style_tags=True)
        return inlined
    except Exception as e:
        print(f"⚠️ CSS内联失败: {e}")
        return full

def main():
    print("\n" + "="*60 + "\n🎨 排版智能体 - 极客代码风\n" + "="*60 + "\n")

    final_file = get_final_file()
    html_file = get_html_file()

    print(f"📁 今日工作目录: {get_today_dir()}\n")
    print(f"📖 读取 {final_file}...")
    
    if not os.path.exists(final_file):
        print(f"❌ 找不到 {final_file}")
        print(f"   请先将润色后的定稿保存到: {get_stage_dir('publish')}/final.md")
        return

    try:
        mtime = os.path.getmtime(final_file)
        print(f"🕒 输入文件最后修改时间: {datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception:
        pass
    
    with open(final_file, "r", encoding="utf-8") as f:
        md = f.read()
    print(f"   ✓ 共 {len(md)} 字符\n")
    
    print("🔄 转换 Markdown -> HTML...")
    html = convert_md_to_html(md)
    print("🎨 内联 CSS...")
    final = inline_css(html)
    
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(final)
    print(f"📄 已保存: {html_file}")
    
    try:
        pyperclip.copy(final)
        print("📋 已复制到剪贴板！\n")
    except:
        print("⚠️ 复制失败，请手动复制 output.html\n")
    
    print("="*60)
    print("✅ 排版完成！")
    print("\n📌 下一步（重要！）：")
    print(f"   1. 用浏览器打开: {html_file}")
    print("   2. 在页面上 Ctrl+A 全选内容")
    print("   3. Ctrl+C 复制")
    print("   4. 到公众号【普通编辑模式】Ctrl+V 粘贴")
    print("   5. ⚠️ 遇到虚线框占位符时，请手动上传并插入对应图片！")
    print("="*60)

if __name__ == "__main__":
    main()
