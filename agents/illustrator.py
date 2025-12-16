"""
🎨 配图智能体 (Illustrator Agent) v4.2 (SiliconFlow Edition)
核心功能：
1. 自动生成文章封面图（支持英文 COVER_PROMPT）
2. 自动生成文章内素材图（英文描述效果更佳）
3. 调用 SiliconFlow Flux.1-schnell 模型，下载图片到本地
4. v4.2: 光影质感流风格后缀 (cinematic lighting, volumetric fog, 8k)

使用方式：
- 封面图：IllustratorAgent().generate_cover("DeepSeek 隐藏玩法")
- 封面图(英文)：IllustratorAgent().generate_cover("Abstract AI neural network...", use_raw_prompt=True)
- 素材图：IllustratorAgent().generate_material("A glowing AI chip floating in space")
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from datetime import datetime
from typing import Optional
from openai import OpenAI

from config import get_logger, get_assets_dir

logger = get_logger(__name__)


# ================= 配置 =================

# 尝试从 config.py 导入 SiliconFlow 配置，兼容未配置的情况
try:
    from config import SILICONFLOW_API_KEY, SILICONFLOW_BASE_URL
except ImportError:
    SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY") or ""
    SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"

# Flux 模型配置 (免费/高性价比版本)
FLUX_MODEL = "black-forest-labs/FLUX.1-schnell"

# v4.2: 光影质感流风格后缀（适用于 Flux 模型）
# 要点：电影感光照、体积雾效果、高分辨率、禁止文字
STYLE_SUFFIX = ", hyper-realistic, cinematic lighting, volumetric fog, 8k resolution, unreal engine 5 render, no text, no words, clean composition"

# 封面图风格增强（v4.2 升级）
COVER_STYLE_SUFFIX = ", hyper-realistic, cinematic lighting, volumetric fog, 8k resolution, unreal engine 5 render, hero image, vibrant colors, no text, no words, no title, clean background"

# 素材图风格增强（v4.2 升级）
MATERIAL_STYLE_SUFFIX = ", hyper-realistic, cinematic lighting, volumetric fog, 8k resolution, concept art, digital illustration, no text, no words, clean composition"


class IllustratorAgent:
    """
    配图智能体：调用 SiliconFlow Flux 模型生成 AI 配图
    
    特点：
    - 优雅降级：如果 SILICONFLOW_API_KEY 未配置，打印警告并跳过生成
    - 图片本地化：下载生成的图片到 5_assets 目录，避免 URL 过期
    - 风格一致：自动追加科技风格词，确保配图风格统一
    - 使用 OpenAI SDK 兼容接口调用 SiliconFlow
    """
    
    def __init__(self):
        self.enabled = bool(SILICONFLOW_API_KEY)
        self.client = None
        
        if not SILICONFLOW_API_KEY:
            logger.warning("⚠️ SILICONFLOW_API_KEY 未配置，配图功能已禁用。")
        else:
            self.client = OpenAI(
                api_key=SILICONFLOW_API_KEY,
                base_url=SILICONFLOW_BASE_URL
            )
            logger.info("✅ IllustratorAgent 已启用 (SiliconFlow Flux.1-schnell)")
    
    def _generate_and_save(
        self,
        prompt: str,
        filename_prefix: str,
        size: str = "1024x1024"
    ) -> Optional[str]:
        """
        核心方法：调用 SiliconFlow Flux 生成图片并保存到本地
        
        Args:
            prompt: 图片描述
            filename_prefix: 文件名前缀 (如 "cover", "material")
            size: 图片尺寸 (如 "1024x1024", "1024x768")
        
        Returns:
            图片相对路径 (如 "5_assets/cover_1234.png") 或 None
        """
        if not self.enabled or not self.client:
            logger.warning(f"⏭️ 跳过配图生成: {prompt[:30]}...")
            return None
        
        # 生成唯一文件名
        timestamp = datetime.now().strftime("%H%M%S")
        filename = f"{filename_prefix}_{timestamp}.png"
        
        # 获取保存目录
        assets_dir = get_assets_dir()
        filepath = os.path.join(assets_dir, filename)
        
        # 优化 prompt
        enhanced_prompt = prompt + STYLE_SUFFIX
        if filename_prefix == "cover":
            enhanced_prompt = prompt + COVER_STYLE_SUFFIX
        elif filename_prefix == "material":
            enhanced_prompt = prompt + MATERIAL_STYLE_SUFFIX
        
        logger.info(f"🎨 正在生成配图: {prompt[:50]}...")
        logger.info(f"   📐 尺寸: {size}")
        
        try:
            # 调用 SiliconFlow Flux 模型 (OpenAI 兼容接口)
            response = self.client.images.generate(
                model=FLUX_MODEL,
                prompt=enhanced_prompt,
                size=size,
                response_format="url"
            )
            
            # 提取图片 URL
            image_url = response.data[0].url
            
            logger.info(f"   ✅ 图片已生成，正在下载...")
            
            # 下载图片到本地
            with httpx.Client(timeout=60) as client:
                download_response = client.get(image_url)
                download_response.raise_for_status()
                
                with open(filepath, "wb") as f:
                    f.write(download_response.content)
            
            # 计算相对路径 (用于 Markdown)
            relative_path = os.path.join("5_assets", filename)
            logger.info(f"   💾 已保存: {relative_path}")
            
            return relative_path
            
        except Exception as e:
            logger.error(f"   ❌ 配图生成失败: {e}")
            return None
    
    def generate_cover(self, title_or_prompt: str, use_raw_prompt: bool = False) -> Optional[str]:
        """
        生成文章封面图
        
        Args:
            title_or_prompt: 文章标题（中文）或已构建好的英文 prompt
            use_raw_prompt: v4.2 新增。如果为 True，直接使用传入的 prompt，不再包装
        
        Returns:
            封面图相对路径或 None
        """
        if use_raw_prompt:
            # v4.2: 直接使用用户提供的英文 COVER_PROMPT
            cover_prompt = title_or_prompt
        else:
            # 降级：从中文标题构建 prompt
            cover_prompt = f"A visually striking tech-themed cover image representing: {title_or_prompt}. Abstract digital art, modern, sleek"
        
        return self._generate_and_save(
            prompt=cover_prompt,
            filename_prefix="cover",
            size="1024x1024"
        )
    
    def generate_material(
        self,
        description: str,
        size: str = "1024x1024"
    ) -> Optional[str]:
        """
        生成文章内素材图
        
        Args:
            description: 画面描述 (如 "一个发光的 AI 芯片")
            size: 图片尺寸，默认 1024x1024
        
        Returns:
            素材图相对路径或 None
        """
        return self._generate_and_save(
            prompt=description,
            filename_prefix="material",
            size=size
        )
    
    def is_enabled(self) -> bool:
        """检查配图功能是否可用"""
        return self.enabled


# ================= 测试入口 =================

def main():
    """测试配图生成"""
    logger.info("=" * 60)
    logger.info("🎨 配图智能体测试 (SiliconFlow)")
    logger.info("=" * 60)
    
    agent = IllustratorAgent()
    
    if not agent.is_enabled():
        logger.warning("配图功能未启用，请检查 SILICONFLOW_API_KEY 配置")
        return
    
    # 测试封面生成
    cover_path = agent.generate_cover("DeepSeek 隐藏玩法大揭秘")
    if cover_path:
        logger.info(f"封面图: {cover_path}")
    
    # 测试素材图生成
    material_path = agent.generate_material("一个发光的蓝色 AI 芯片漂浮在黑暗的空间中")
    if material_path:
        logger.info(f"素材图: {material_path}")
    
    logger.info("✅ 测试完成")


if __name__ == "__main__":
    main()
