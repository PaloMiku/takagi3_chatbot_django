import asyncio
import logging
from typing import Optional, Tuple
from gradio_client import Client
import tempfile
import os
import hashlib
import time
from django.conf import settings
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)

class TTSService:
    """语音合成服务类"""
    
    def __init__(self, client_url="https://www.takagi3.ai/vits/"):
        self.client_url = client_url
        self.speaker_id = "takagi3"
        self.use_mock = False  # 默认使用模拟服务，可以在设置中更改
    
    def _create_mock_audio(self, text: str) -> str:
        """创建模拟音频文件（用于演示）"""
        import wave
        import struct
        import math
        
        # 生成文件名
        text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()[:8]
        timestamp = str(int(time.time()))
        filename = f"tts_{text_hash}_{timestamp}.wav"
        
        # 在媒体目录中创建文件
        tts_dir = os.path.join(settings.MEDIA_ROOT, 'tts')
        os.makedirs(tts_dir, exist_ok=True)
        audio_path = os.path.join(tts_dir, filename)
        
        # 生成简单的正弦波音频（模拟语音）
        sample_rate = 22050
        duration = min(len(text) * 0.1 + 1, 10)  # 根据文本长度计算时长，最长10秒
        
        with wave.open(audio_path, 'w') as wav_file:
            wav_file.setnchannels(1)  # 单声道
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            
            for i in range(int(sample_rate * duration)):
                # 生成多频率混合的音频（模拟人声）
                value = 0
                for freq in [220, 440, 660]:  # 混合多个频率
                    value += math.sin(2 * math.pi * freq * i / sample_rate) * 0.3
                # 添加一些随机性模拟语音变化
                value *= (0.8 + 0.4 * math.sin(i / 100))
                wav_file.writeframes(struct.pack('<h', int(value * 16383)))
        
        return audio_path
    
    def _get_audio_url(self, audio_path: str) -> str:
        """将本地音频文件路径转换为可访问的URL"""
        if audio_path.startswith(settings.MEDIA_ROOT):
            # 如果文件在媒体目录中，返回媒体URL
            relative_path = os.path.relpath(audio_path, settings.MEDIA_ROOT)
            return settings.MEDIA_URL + relative_path.replace('\\', '/')
        else:
            # 如果文件在其他位置，需要复制到媒体目录
            try:
                text_hash = hashlib.md5(audio_path.encode('utf-8')).hexdigest()[:8]
                timestamp = str(int(time.time()))
                filename = f"tts_copy_{text_hash}_{timestamp}.wav"
                
                tts_dir = os.path.join(settings.MEDIA_ROOT, 'tts')
                os.makedirs(tts_dir, exist_ok=True)
                new_path = os.path.join(tts_dir, filename)
                
                # 复制文件
                import shutil
                shutil.copy2(audio_path, new_path)
                
                relative_path = os.path.relpath(new_path, settings.MEDIA_ROOT)
                return settings.MEDIA_URL + relative_path.replace('\\', '/')
            except Exception as e:
                logger.error(f"复制音频文件失败: {e}")
                return audio_path  # 如果复制失败，返回原路径
    
    def generate_speech(
        self, 
        text: str, 
        language: str = "中文",
        noise_scale: float = 0.6,
        noise_scale_w: float = 0.668,
        length_scale: float = 1.2
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        生成语音
        
        Args:
            text: 要转换的文本
            language: 语言选择 ("中文" 或 "日语")
            noise_scale: 音频噪音
            noise_scale_w: 音频噪音权重 
            length_scale: 音频长度缩放
            
        Returns:
            (成功标志, 音频URL或None, 错误信息或None)
        """
        if self.use_mock:
            # 使用模拟TTS服务
            try:
                logger.info(f"使用模拟TTS服务生成语音: {text[:50]}...")
                audio_path = self._create_mock_audio(text)
                audio_url = self._get_audio_url(audio_path)
                return True, audio_url, None
            except Exception as e:
                logger.error(f"模拟TTS生成失败: {e}")
                return False, None, f"模拟语音生成失败：{str(e)}"
        
        # 使用实际的gradio TTS服务
        try:
            client = Client(self.client_url)
            
            # 调用语音合成API
            result = client.predict(
                text=text,
                language=language,
                speaker_id=self.speaker_id,
                noise_scale=noise_scale,
                noise_scale_w=noise_scale_w,
                length_scale=length_scale,
                api_name="/GetSpeech"
            )
            
            logger.info(f"TTS API result: {result}, type: {type(result)}")
            
            # 处理不同类型的返回结果
            if result:
                audio_path = None
                if isinstance(result, str):
                    audio_path = result
                elif isinstance(result, (list, tuple)) and len(result) > 0:
                    audio_path = result[0] if result[0] else None
                elif hasattr(result, 'name'):
                    audio_path = result.name
                
                if audio_path:
                    audio_url = self._get_audio_url(audio_path)
                    return True, audio_url, None
                else:
                    logger.warning(f"Unexpected result format: {result}")
                    return False, None, f"API返回格式异常: {type(result)}"
            else:
                return False, None, "语音合成失败：API返回空结果"
                
        except Exception as e:
            logger.error(f"语音合成错误: {e}")
            # 如果实际服务失败，尝试使用模拟服务
            if not self.use_mock:
                logger.info("实际TTS服务失败，尝试使用模拟服务")
                try:
                    audio_path = self._create_mock_audio(text)
                    audio_url = self._get_audio_url(audio_path)
                    return True, audio_url, "注意：使用模拟语音服务"
                except Exception as mock_e:
                    logger.error(f"模拟TTS也失败: {mock_e}")
            return False, None, f"语音合成失败：{str(e)}"
    
    async def generate_speech_async(
        self, 
        text: str, 
        language: str = "中文",
        noise_scale: float = 0.6,
        noise_scale_w: float = 0.668,
        length_scale: float = 1.2
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """异步生成语音"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, 
            self.generate_speech,
            text, language, noise_scale, noise_scale_w, length_scale
        )


# 全局TTS服务实例
tts_service = TTSService()


def get_user_tts_settings(user_setting):
    """获取用户的TTS设置"""
    return {
        'enabled': user_setting.tts_enabled,
        'language': user_setting.tts_language,
        'noise_scale': user_setting.tts_noise_scale,
        'noise_scale_w': user_setting.tts_noise_scale_w,
        'length_scale': user_setting.tts_length_scale,
    }


def generate_tts_for_user(text: str, user_setting) -> Tuple[bool, Optional[str], Optional[str]]:
    """为用户生成TTS音频"""
    if not user_setting.tts_enabled:
        return False, None, "TTS功能未启用"
    
    # 使用用户自定义的API地址或默认地址
    api_url = user_setting.tts_api_url if user_setting.tts_api_url else "https://www.takagi3.ai/vits/"
    
    # 创建专用的TTS服务实例
    user_tts_service = TTSService(client_url=api_url)
    user_tts_service.use_mock = False  # 用户设置了API就使用真实服务
    
    try:
        return user_tts_service.generate_speech(
            text=text,
            language=user_setting.tts_language,
            noise_scale=user_setting.tts_noise_scale,
            noise_scale_w=user_setting.tts_noise_scale_w,
            length_scale=user_setting.tts_length_scale
        )
    except Exception as e:
        logger.error(f"用户TTS生成失败: {e}")
        # 如果失败，尝试使用模拟服务
        try:
            fallback_service = TTSService()
            fallback_service.use_mock = True
            success, audio_url, _ = fallback_service.generate_speech(
                text=text,
                language=user_setting.tts_language,
                noise_scale=user_setting.tts_noise_scale,
                noise_scale_w=user_setting.tts_noise_scale_w,
                length_scale=user_setting.tts_length_scale
            )
            if success:
                return True, audio_url, f"API调用失败，使用模拟服务: {str(e)}"
        except Exception as fallback_e:
            logger.error(f"模拟TTS也失败: {fallback_e}")
        
        return False, None, f"TTS生成失败: {str(e)}"
