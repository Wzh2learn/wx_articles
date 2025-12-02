import os
import re
import sys
import time
from bs4 import BeautifulSoup

# 尝试导入 wechatpy，如果未安装则提示
try:
    from wechatpy import WeChatClient
    from wechatpy.exceptions import WeChatClientException
    import requests
except ImportError:
    WeChatClient = None

# 将父目录加入 sys.path 以便导入 config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    WECHAT_APP_ID, 
    WECHAT_APP_SECRET, 
    get_html_file, 
    get_assets_dir,
    get_final_file,
    get_stage_dir
)

def check_dependencies():
    """检查依赖"""
    if WeChatClient is None:
        print("⚠️  缺少依赖: wechatpy")
        print("   请运行: pip install wechatpy requests")
        return False
    # 不再检查"你的AppID"字符串，因为用户已经填写了
    if not WECHAT_APP_ID or not WECHAT_APP_SECRET:
        print("⚠️  缺少配置: 请在 config.py 中填入 WECHAT_APP_ID 和 WECHAT_APP_SECRET")
        return False
    return True

def download_image(url):
    """下载网络图片到临时文件"""
    try:
        resp = requests.get(url, stream=True, timeout=10)
        if resp.status_code == 200:
            # 获取扩展名
            ext = os.path.splitext(url.split('?')[0])[1]
            if not ext: ext = '.jpg'
            
            temp_file = os.path.join(get_assets_dir(), f"temp_{int(time.time())}{ext}")
            with open(temp_file, 'wb') as f:
                for chunk in resp.iter_content(1024):
                    f.write(chunk)
            return temp_file
    except Exception as e:
        print(f"     ⚠️ 下载图片失败: {e}")
    return None

def upload_images(client, html_content):
    """
    扫描 HTML 中的图片（本地+网络），上传到微信，并替换 URL
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    images = soup.find_all('img')
    
    if not images:
        print("   ℹ️ 文中无图片，跳过上传")
        return html_content, []
    
    print(f"   📸 发现 {len(images)} 张图片，准备上传...")
    
    uploaded_count = 0
    uploaded_media_ids = []
    for img in images:
        src = img.get('src')
        if not src: continue
        
        img_path = None
        is_temp = False
        
        # 情况A：网络图片 (PicGo 等图床)
        if src.startswith('http') or src.startswith('//'):
            # 忽略已经是微信的图片 (mmbiz)
            if 'mmbiz.qpic.cn' in src:
                continue
            print(f"   🌍 发现网络图片，正在转存: {src[:30]}...")
            if src.startswith('//'): src = 'https:' + src
            img_path = download_image(src)
            is_temp = True
            
        # 情况B：本地图片（优先从 assets 目录查找）
        else:
            if os.path.isabs(src):
                img_path = src
            else:
                # 先尝试 assets 目录
                img_path = os.path.join(get_assets_dir(), src)
                # 如果不存在，尝试 publish 目录
                if not os.path.exists(img_path):
                    img_path = os.path.join(get_stage_dir("publish"), src)
        
        # 执行上传
        if img_path and os.path.exists(img_path):
            try:
                print(f"   📤 上传微信服务器: {os.path.basename(img_path)}...")
                with open(img_path, 'rb') as f:
                    res = client.material.add('image', f)
                    url = res['url']
                    media_id = res['media_id']
                    
                # 替换 URL
                img['src'] = url
                img['data-src'] = url
                uploaded_count += 1
                uploaded_media_ids.append(media_id)
                print(f"     ✅ 成功! media_id: {media_id}")
                
            except Exception as e:
                print(f"     ❌ 上传失败: {e}")
            finally:
                # 如果是临时下载的文件，删除之
                if is_temp and os.path.exists(img_path):
                    os.remove(img_path)
        else:
            print(f"   ❌ 无法找到图片文件")

    print(f"   🎉 图片处理完成: 成功 {uploaded_count}/{len(images)}")
    return str(soup), uploaded_media_ids

def extract_title_digest():
    """
    从 final.md 或 html 中提取标题和摘要
    这里简单实现：读取 final.md 的第一行作为标题
    """
    final_md = get_final_file()
    if not os.path.exists(final_md):
        return "未命名文章", "由 AI 生成的自动摘要"
        
    with open(final_md, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    title = "未命名文章"
    digest = "由 AI 自动生成的文章摘要。"
    
    for line in lines:
        if line.strip().startswith('# '):
            title = line.strip().replace('# ', '')
            break
            
    return title, digest

def publish_draft():
    """
    主流程：读取 output.html -> 上传图片 -> 新建草稿
    """
    print("\n🚀 启动自动发布流程 (Publisher Agent)...")
    
    if not check_dependencies():
        return
    
    # 初始化客户端
    try:
        client = WeChatClient(WECHAT_APP_ID, WECHAT_APP_SECRET)
        # 测试连接
        client.material.get_count()
        print("   ✅ 微信接口连接成功")
    except Exception as e:
        print(f"   ❌ 连接失败: {e}")
        print("   请检查 AppID, AppSecret 及 IP白名单配置")
        return

    # 读取 HTML
    html_file = get_html_file()
    if not os.path.exists(html_file):
        print(f"   ❌ 找不到文件: {html_file}")
        return
        
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
        
    # 1. 处理图片
    # 注意：output.html 里的 CSS 是内联的，微信草稿接口支持带 style 的 HTML
    final_html, uploaded_ids = upload_images(client, html_content)
    
    # 2. 准备元数据
    title, digest = extract_title_digest()
    print(f"   📝 文章标题: {title}")
    
    # 自动选择封面图 (使用第一张上传成功的图片)
    thumb_media_id = ""
    if uploaded_ids:
        thumb_media_id = uploaded_ids[0]
        print(f"   🖼️ 自动选择封面图: {thumb_media_id}")
    else:
        print("   ⚠️ 未找到可用图片作为封面，草稿创建可能会失败 (Error 40007)")

    # 3. 上传草稿
    # 微信草稿接口: draft.add(articles)
    # wechatpy 1.8.18 暂无 draft 封装，使用 client.post 手动调用
    # API文档: https://developers.weixin.qq.com/doc/offiaccount/Draft_Box/Add_draft.html
    
    article_data = {
        "title": title,
        "author": "王往AI",
        "digest": digest,
        "content": final_html,
        "content_source_url": "",
        "thumb_media_id": thumb_media_id, 
        "need_open_comment": 1,
        "only_fans_can_comment": 0
    }
    
    payload = {"articles": [article_data]}
    
    print("   📤正在创建草稿...")
    try:
        # 手动调用 draft/add 接口
        res = client.post('draft/add', data=payload)
        media_id = res.get('media_id') or res.get('item')[0]['media_id']
        
        print(f"\n✅ 草稿创建成功！")
        print(f"🆔 Media ID: {media_id}")
        print("👉 请登录公众号后台 -> 草稿箱 查看并发布")
        
    except Exception as e:
        print(f"   ❌ 创建草稿失败: {e}")
        if "thumb_media_id" in str(e) or "40001" in str(e):
             print("   💡 常见错误提示：")
             print("   1. thumb_media_id 缺失: 必须提供封面图ID。请在公众号后台上传一张图片到素材库，复制其 media_id 填入代码中（临时方案）。")
             print("   2. 接口权限: 请确认公众号是否已获得草稿箱接口权限（通常订阅号都有）。")

if __name__ == "__main__":
    publish_draft()
