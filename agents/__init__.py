"""
王往AI 公众号工作流 - 智能体模块 v4.0 (Hardcore Edition)

包含以下智能体：
- trend_hunter: 选题雷达，扫描全网热点
- researcher: 研究智能体，自动联网搜索、全文爬取、笔记整理
- drafter: 写作智能体，基于笔记生成初稿
- formatter: 排版智能体，Markdown 转微信 HTML
- todo_extractor: TODO 提取器，列出需补充的内容
- refiner: 润色智能体，定向修改文章
"""

from .trend_hunter import main as run_trend_hunter
from .researcher import ResearcherAgent
from .drafter import main as run_drafter
from .formatter import main as run_formatter
from .todo_extractor import main as run_todo_extractor
from .refiner import refine_article as run_refiner

__all__ = [
    'run_trend_hunter',
    'ResearcherAgent',
    'run_drafter', 
    'run_formatter',
    'run_todo_extractor',
    'run_refiner'
]
