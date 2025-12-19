import os
import time
from playwright.sync_api import sync_playwright
import config

logger = config.get_logger(__name__)

def capture_homepage(url: str, output_path: str) -> bool:
    """
    使用 Playwright 截取网页首屏
    
    Args:
        url: 目标网址
        output_path: 图片保存路径 (包含文件名)
        
    Returns:
        bool: 是否成功
    """
    logger.info(f"📸 正在截图: {url}")
    
    try:
        with sync_playwright() as p:
            # 启动浏览器 (headless=True)
            browser = p.chromium.launch(headless=True)
            
            # 创建上下文 (设置 Viewport)
            context = browser.new_context(
                viewport={'width': 1280, 'height': 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            page = context.new_page()
            
            # 访问页面
            try:
                page.goto(url, wait_until="networkidle", timeout=30000)
            except Exception as e:
                logger.warning(f"   ⚠️ 页面加载超时或不完全: {e}")
                # 即使超时也尝试截图
            
            # 注入 JS 移除常见的 Cookie 遮罩 / 弹窗
            try:
                page.evaluate("""() => {
                    // 移除常见的 Cookie Consent 元素
                    const selectors = [
                        '#onetrust-banner-sdk',
                        '.cookie-banner',
                        '.accept-cookies', 
                        '[class*="cookie"]',
                        '[id*="cookie"]',
                        '[class*="popup"]',
                        '[class*="modal"]'
                    ];
                    selectors.forEach(s => {
                        const els = document.querySelectorAll(s);
                        els.forEach(el => el.remove());
                    });
                }""")
                # 稍微等待 JS 执行和页面稳定
                page.wait_for_timeout(2000)
            except Exception:
                pass
            
            # 截图
            page.screenshot(path=output_path)
            logger.info(f"   ✅ 截图已保存: {output_path}")
            
            browser.close()
            return True
            
    except Exception as e:
        logger.error(f"❌ 截图失败: {e}")
        return False

if __name__ == "__main__":
    # 测试代码
    test_url = "https://www.deepseek.com"
    test_path = "test_screenshot.png"
    capture_homepage(test_url, test_path)
