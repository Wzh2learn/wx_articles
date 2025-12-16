"""
🧪 选题雷达单元测试脚本
只测试 fetch_dynamic_trends 函数，不消耗 Tavily 额度，不运行完整流程。
"""
import sys
import os
import httpx
from openai import OpenAI

# 导入配置
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, PROXY_URL, REQUEST_TIMEOUT, get_logger

# 模拟环境引入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agents.trend_hunter import fetch_dynamic_trends, WebSearchTool

logger = get_logger(__name__)

def test_radar():
    logger.info("🧪 正在启动雷达单元测试...")
    logger.info("🔌 代理配置: %s", PROXY_URL)
    logger.info("🔑 API Key: %s******", (DEEPSEEK_API_KEY[:5] if DEEPSEEK_API_KEY else ""))

    # 初始化客户端
    try:
        if PROXY_URL:
            http_client = httpx.Client(proxy=PROXY_URL, timeout=REQUEST_TIMEOUT)
        else:
            http_client = httpx.Client(timeout=REQUEST_TIMEOUT)

        client = OpenAI(
            api_key=DEEPSEEK_API_KEY, 
            base_url=DEEPSEEK_BASE_URL, 
            http_client=http_client
        )
    except Exception as e:
        logger.error("❌ 客户端初始化失败: %s", e)
        return

    # 初始化 Tavily 工具
    search_tool = WebSearchTool()

    # 运行抓取
    try:
        keywords = fetch_dynamic_trends(client, search_tool)

        logger.info("%s", "="*50)
        logger.info("🎉 测试结果报告")
        logger.info("%s", "="*50)
        
        if keywords:
            logger.info("✅ 成功捕获 %s 个热词:", len(keywords))
            for i, kw in enumerate(keywords, 1):
                logger.info("   %s. %s", i, kw)
        else:
            logger.warning("⚠️ 未捕获到任何关键词 (请检查网络或 Jina 服务状态)")
            
    except Exception as e:
        logger.error("❌ 测试过程中发生错误: %s", e)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_radar()