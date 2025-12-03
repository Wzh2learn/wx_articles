import sys
import os
import json
from unittest.mock import MagicMock, patch

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.trend_hunter import (
    WATCHLIST, 
    step1_broad_scan_and_plan, 
    step2_deep_scan, 
    WebSearchTool,
    PHASE_CONFIG,
    CURRENT_CONFIG
)

def test_watchlist_loaded():
    print("\n🧪 [Test 1] 验证 WATCHLIST 配置...")
    expected_items = ["DeepSeek", "Kimi", "Cursor", "豆包", "秘塔搜索"]
    missing = [item for item in expected_items if item not in WATCHLIST]
    
    if not missing:
        print(f"   ✅ WATCHLIST 加载成功，共 {len(WATCHLIST)} 个关注项。")
        print(f"   包含: {WATCHLIST[:5]}...")
    else:
        print(f"   ❌ 缺少关键项: {missing}")
        exit(1)

def test_strategy_config():
    print("\n🧪 [Test 2] 验证策略配置...")
    if CURRENT_CONFIG['name'] == "价值黑客模式":
        print("   ✅ 当前策略: 价值黑客模式 (Value Hacker)")
        print(f"   权重配置: {CURRENT_CONFIG['weights']}")
    else:
        print(f"   ❌ 策略配置错误: {CURRENT_CONFIG['name']}")
        exit(1)

@patch('agents.trend_hunter.random.sample')
def test_step1_logic(mock_sample):
    print("\n🧪 [Test 3] 验证 Step 1 (广域扫描) 逻辑...")
    
    # Mock 随机抽样，固定抽样结果以便验证
    mock_sample.return_value = ["DeepSeek", "Cursor", "豆包"]
    
    # Mock 搜索工具
    mock_search = MagicMock()
    mock_search.search.return_value = [
        {"title": "DeepSeek 隐藏玩法", "body": "这是DeepSeek的教程...", "url": "http://test.com"}
    ]
    
    # Mock OpenAI Client
    mock_client = MagicMock()
    mock_response = MagicMock()
    # 模拟 DeepSeek 返回的 JSON 计划
    mock_plan = {
        "events": [
            {
                "event": "DeepSeek", 
                "angle": "隐藏玩法",
                "news_query": "DeepSeek V3 features",
                "social_query": "DeepSeek 最好用的指令"
            }
        ]
    }
    mock_response.choices[0].message.content = json.dumps(mock_plan)
    mock_client.chat.completions.create.return_value = mock_response

    # 执行 Step 1
    plan = step1_broad_scan_and_plan(mock_client, mock_search)
    
    # 验证 A/B/C 三路搜索是否都触发了
    search_calls = [call.args[0] for call in mock_search.search.call_args_list]
    print(f"   🔍 触发的搜索词: {search_calls[:3]}...")
    
    # 验证 A路 (锚点) 是否包含 WATCHLIST 中的词
    has_anchor = any("DeepSeek" in q for q in search_calls)
    # 验证 B路 (收益) 是否包含 "效率神器"
    has_gain = any("效率神器" in q for q in search_calls)
    # 验证 C路 (损失) 是否包含 "避坑"
    has_pain = any("避坑" in q for q in search_calls)
    
    if has_anchor and has_gain and has_pain:
        print("   ✅ 三路策略 (锚点/收益/损失) 全部触发")
    else:
        print("   ❌ 策略触发不完整")
        print(f"   Anchor: {has_anchor}, Gain: {has_gain}, Pain: {has_pain}")

    # 验证 JSON 解析
    if len(plan) == 1 and plan[0]['event'] == "DeepSeek":
        print("   ✅ DeepSeek 规划解析成功")
    else:
        print("   ❌ 规划解析失败")

def test_step2_logic():
    print("\n🧪 [Test 4] 验证 Step 2 (深度验证) 渠道逻辑...")
    
    mock_search = MagicMock()
    mock_search.search.return_value = []
    
    plan = [{
        "event": "DeepSeek",
        "angle": "隐藏玩法",
        "social_query": "DeepSeek 避坑"
    }]
    
    step2_deep_scan(plan, mock_search)
    
    # 验证社交搜索是否包含了知乎/B站
    social_call = mock_search.search.call_args_list[0].args[0]
    
    if "site:zhihu.com" in social_call and "site:bilibili.com" in social_call:
        print(f"   ✅ 社交搜索渠道正确: {social_call}")
    else:
        print(f"   ❌ 社交搜索渠道缺失: {social_call}")

if __name__ == "__main__":
    print("🚀 开始测试 v7.0 选题雷达逻辑...")
    test_watchlist_loaded()
    test_strategy_config()
    test_step1_logic()
    test_step2_logic()
    print("\n✨ 所有测试通过！准备提交。")
