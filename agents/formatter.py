"""
🎨 排版智能体 (Formatter) v1.0 - 极客代码风
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from markdown_it import MarkdownIt
from pygments import highlight
from pygments.lexers import get_lexer_by_name, TextLexer
from pygments.formatters import HtmlFormatter
from premailer import transform
import pyperclip
from config import get_final_file, get_html_file, get_today_dir

WECHAT_CSS = """
body, .article-content { font-family: -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif; font-size: 16px; line-height: 1.75; color: #333; background: #f8f9fa; padding: 20px; }
p { margin: 1em 0; text-align: justify; }
h1 { font-size: 24px; font-weight: bold; text-align: center; margin: 1.5em 0 1em; padding-bottom: 10px; border-bottom: 3px solid #ff6b35; }
h2 { font-size: 20px; font-weight: bold; text-align: center; margin: 1.8em 0 1em; padding-bottom: 12px; border-bottom: 3px solid #ff6b35; }
h3 { font-size: 18px; font-weight: bold; margin: 1.5em 0 0.8em; padding-left: 12px; border-left: 4px solid #ff6b35; }
strong, b { font-weight: bold; color: #d9534f; }
em, i { font-style: italic; color: #666; }
code:not(.hljs) { background: #fff3cd; color: #856404; padding: 2px 6px; border-radius: 4px; font-family: 'Fira Code', monospace; font-size: 14px; }
pre { background: #1e1e1e; border-radius: 8px; padding: 16px; overflow-x: auto; margin: 1.2em 0; box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
pre code { font-family: 'Fira Code', Consolas, monospace; font-size: 14px; line-height: 1.6; color: #d4d4d4; background: none; padding: 0; }
.highlight .k, .highlight .kn, .highlight .kd { color: #569cd6; }
.highlight .s, .highlight .s1, .highlight .s2 { color: #ce9178; }
.highlight .c, .highlight .c1, .highlight .cm { color: #6a9955; }
.highlight .nf, .highlight .nb { color: #dcdcaa; }
.highlight .nn, .highlight .nc { color: #4ec9b0; }
.highlight .mi, .highlight .mf { color: #b5cea8; }
blockquote { border-left: 4px solid #4285f4; background: #e8f0fe; padding: 12px 16px; margin: 1.2em 0; border-radius: 0 8px 8px 0; color: #555; font-size: 15px; }
ul, ol { padding-left: 24px; margin: 1em 0; }
ul li::marker { color: #ff6b35; }
ol li { display: block; }
ol li::before { content: counter(item) "."; counter-increment: item; font-weight: bold; color: #ff6b35; margin-right: 8px; }
ol { counter-reset: item; }
a { color: #4285f4; text-decoration: none; border-bottom: 1px dashed #4285f4; }
img { max-width: 100%; border-radius: 8px; margin: 1em 0; }
hr { border: none; height: 1px; background: linear-gradient(90deg, transparent, #ddd, transparent); margin: 2em 0; }
.todo-marker { background: linear-gradient(135deg, #fff3cd, #ffeeba); border: 2px dashed #ffc107; border-radius: 8px; padding: 16px; margin: 1.5em 0; text-align: center; color: #856404; font-weight: bold; }
table { width: 100%; border-collapse: collapse; margin: 1.2em 0; }
th { background: #ff6b35; color: white; padding: 12px; text-align: left; }
td { padding: 10px 12px; border-bottom: 1px solid #eee; }
tr:nth-child(even) { background: #f8f9fa; }
"""

def highlight_code(code, lang):
    try:
        lexer = get_lexer_by_name(lang, stripall=True)
    except:
        lexer = TextLexer()
    formatter = HtmlFormatter(nowrap=True, cssclass='highlight', style='monokai')
    return f'<pre><code class="language-{lang}">{highlight(code, lexer, formatter)}</code></pre>'

def convert_md_to_html(md_content):
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
    full = f"<!DOCTYPE html><html><head><style>{WECHAT_CSS}</style></head><body><div class='article-content'>{html}</div></body></html>"
    try:
        inlined = transform(full, remove_classes=False, keep_style_tags=False)
        match = re.search(r"<div class=['\"]article-content['\"]>(.*?)</div>\s*</body>", inlined, re.DOTALL)
        return match.group(1).strip() if match else inlined
    except Exception as e:
        print(f"⚠️ CSS内联失败: {e}")
        return html

def main():
    print("\n" + "="*60 + "\n🎨 排版智能体 - 极客代码风\n" + "="*60 + "\n")
    
    final_file = get_final_file()
    html_file = get_html_file()
    
    print(f"📁 今日工作目录: {get_today_dir()}\n")
    print(f"📖 读取 {final_file}...")
    
    if not os.path.exists(final_file):
        print(f"❌ 找不到 {final_file}")
        print(f"   请先在今日目录下创建 final.md（润色后的定稿）")
        return
    
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
    print("\n📌 下一步：")
    print("   1. 打开公众号后台 -> 新建图文")
    print("   2. 点击 </> 切换 HTML 模式")
    print("   3. Ctrl+V 粘贴")
    print("   4. 再点 </> 预览效果")
    print("="*60)

if __name__ == "__main__":
    main()
