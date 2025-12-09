"""
🧪 选题雷达单元测试脚本
只测试 fetch_dynamic_trends 函数，不消耗 Tavily 额度，不运行完整流程。
"""
import sys
import os
import httpx
from openai import OpenAI

# 导入配置
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, PROXY_URL, REQUEST_TIMEOUT

# 模拟环境引入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agents.trend_hunter import fetch_dynamic_trends, WebSearchTool

def test_radar():
    print("🧪 正在启动雷达单元测试...")
    print(f"🔌 代理配置: {PROXY_URL}")
    print(f"🔑 API Key: {DEEPSEEK_API_KEY[:5]}******")
    
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
        print(f"❌ 客户端初始化失败: {e}")
        return

    # 初始化 Tavily 工具
    search_tool = WebSearchTool()

    # 运行抓取
    try:
        keywords = fetch_dynamic_trends(client, search_tool)
        
        print("\n" + "="*50)
        print("🎉 测试结果报告")
        print("="*50)
        
        if keywords:
            print(f"✅ 成功捕获 {len(keywords)} 个热词:")
            for i, kw in enumerate(keywords, 1):
                print(f"   {i}. {kw}")
        else:
            print("⚠️ 未捕获到任何关键词 (请检查网络或 Jina 服务状态)")
            
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_radar()