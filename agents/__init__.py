"""
王往AI 公众号工作流 - 智能体模块

包含以下智能体：
- trend_hunter: 选题雷达，扫描全网热点
- drafter: 写作智能体，基于笔记生成初稿
- formatter: 排版智能体，Markdown 转微信 HTML
- todo_extractor: TODO 提取器，列出需补充的内容
- publisher: 发布智能体，自动上传图片并创建草稿
"""

from .trend_hunter import main as run_trend_hunter
from .drafter import main as run_drafter
from .formatter import main as run_formatter
from .todo_extractor import main as run_todo_extractor
from .publisher import publish_draft as run_publisher

__all__ = [
    'run_trend_hunter', 
    'run_drafter', 
    'run_formatter',
    'run_todo_extractor',
    'run_publisher'
]
