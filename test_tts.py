#!/usr/bin/env python3
"""
测试TTS API的简单脚本
"""

import sys
import os
sys.path.append('/home/palomiku/Github/takagi3_chatbot_django')

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_chatbot.settings')

import django
django.setup()

from chatbot.tts_utils import tts_service

def test_tts_api():
    """测试TTS API"""
    test_text = "你好，这是一个测试。"
    print(f"正在测试TTS API...")
    print(f"测试文本: {test_text}")
    
    try:
        success, audio_path, error = tts_service.generate_speech(
            text=test_text,
            language="中文",
            noise_scale=0.6,
            noise_scale_w=0.668,
            length_scale=1.2
        )
        
        print(f"成功: {success}")
        print(f"音频路径: {audio_path}")
        print(f"错误信息: {error}")
        
        if success and audio_path:
            print(f"TTS生成成功！音频文件: {audio_path}")
        else:
            print(f"TTS生成失败: {error}")
            
    except Exception as e:
        print(f"测试异常: {e}")

if __name__ == "__main__":
    test_tts_api()
