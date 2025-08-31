# 语音合成功能使用指南

## 概述

为聊天机器人添加了基于 Gradio Client 的语音合成功能，可以将AI的文字回复转换为语音。

## 功能特性

### 1. 语音合成设置
- **开关控制**: 可在用户设置中启用/禁用语音合成功能
- **语言选择**: 支持中文和日语两种语言
- **参数调节**: 可调节音频噪音、音频噪音权重、音频长度缩放等参数

### 2. 使用方式
- 启用语音合成后，AI回复的消息会自动显示"🔊 播放语音"按钮
- 点击按钮即可播放生成的语音
- 语音生成时会显示加载提示

### 3. 技术实现
- 后端使用 Gradio Client 调用语音合成API
- 支持实际API和模拟服务两种模式
- 音频文件保存在Django媒体目录中
- 前端使用WebSocket和AJAX进行实时通信

## 配置说明

### 1. 访问设置
1. 点击右上角头像
2. 选择"用户设置"
3. 在设置面板中找到"启用语音合成"选项

### 2. 参数调节
- **语言**: 选择"中文"或"日语"
- **音频噪音**: 0.1-1.0，默认0.6
- **音频噪音权重**: 0.1-1.0，默认0.668  
- **音频长度缩放**: 0.5-2.0，默认1.2

### 3. 实际API配置
如需使用实际的TTS服务，需要修改 `chatbot/tts_utils.py` 文件：

```python
# 在TTSService类的__init__方法中
self.use_mock = False  # 改为False使用实际API
self.client_url = "你的实际API地址"  # 更改为实际API地址
```

## API说明

### 新增API端点

1. **生成TTS音频**
   - URL: `/api/tts/generate`
   - 方法: POST
   - 参数: `text` (要转换的文本)
   - 返回: JSON格式的结果和音频URL

2. **获取TTS设置**
   - URL: `/api/tts/settings`
   - 方法: GET
   - 返回: 用户的TTS配置信息

3. **更新用户设置**
   - URL: `/user/settings/update`
   - 方法: POST
   - 新增TTS相关参数的支持

### 数据库变更

在 `UserSetting` 模型中新增字段：
- `tts_enabled`: 语音合成开关
- `tts_language`: 语言选择
- `tts_noise_scale`: 音频噪音
- `tts_noise_scale_w`: 音频噪音权重
- `tts_length_scale`: 音频长度缩放

## 文件说明

### 新增文件
- `chatbot/tts_utils.py`: TTS服务工具类
- `media/tts/`: 音频文件存储目录

### 修改文件
- `chatbot/models.py`: 添加TTS设置字段
- `chatbot/views.py`: 添加TTS相关视图和API
- `chatbot/urls.py`: 添加TTS API路由
- `templates/chatbot.html`: 添加TTS设置界面和播放功能
- `chatbot/consumers.py`: WebSocket支持TTS状态传递

## 注意事项

1. **模拟服务**: 当前默认使用模拟TTS服务生成简单音频，用于演示功能
2. **音频格式**: 生成的音频为WAV格式，22050Hz采样率
3. **文件清理**: 建议定期清理媒体目录中的临时音频文件
4. **性能考虑**: 语音生成可能需要较长时间，已加入加载提示
5. **浏览器兼容**: 使用HTML5 Audio API，需要现代浏览器支持

## 自定义开发

### 集成其他TTS服务
修改 `tts_utils.py` 中的 `generate_speech` 方法，替换为你需要的TTS API调用：

```python
def generate_speech(self, text, language, ...):
    # 替换为你的TTS API调用逻辑
    # 确保返回 (success, audio_url, error_message) 格式
    pass
```

### 添加更多语言支持
1. 在模型中修改 `tts_language` 字段的 choices
2. 在前端设置面板中添加新的语言选项
3. 在TTS服务中处理新的语言参数

### 音频格式自定义
根据需要修改音频生成参数，如采样率、声道数、编码格式等。

## 故障排除

1. **语音播放失败**: 检查浏览器音频权限和音频文件URL可访问性
2. **TTS生成失败**: 查看Django日志获取详细错误信息
3. **设置保存失败**: 检查表单数据格式和参数范围
4. **按钮不显示**: 确认TTS功能已启用且WebSocket连接正常

## 更新历史

- 添加基础TTS功能支持
- 集成用户设置界面
- 支持实时语音生成和播放
- 添加模拟TTS服务用于演示
