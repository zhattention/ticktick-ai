import os
import base64
import logging
from datetime import datetime
import openai

logger = logging.getLogger(__name__)

class AudioProcessor:
    def __init__(self, audio_dir="audio_files"):
        self.audio_dir = audio_dir
        if not os.path.exists(self.audio_dir):
            os.makedirs(self.audio_dir)
            logger.info(f"Created audio directory: {self.audio_dir}")
    
    def process_audio(self, audio_data):
        """
        处理音频数据并转换为文本
        
        Args:
            audio_data (str): Base64编码的音频数据
            
        Returns:
            str: 转录的文本
        """
        try:
            # 解析MIME类型和Base64数据
            mime_type = audio_data.split(',')[0].split(':')[1].split(';')[0]
            logger.info(f"Received audio MIME type: {mime_type}")
            
            audio_bytes = base64.b64decode(audio_data.split(',')[1])
            logger.info(f"Decoded base64 data size: {len(audio_bytes)} bytes")
            
            # 保存原始数据到临时文件
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_audio = f"{self.audio_dir}/temp_{timestamp}.webm"
            
            with open(temp_audio, 'wb') as f:
                f.write(audio_bytes)
            
            try:
                # 使用OpenAI Whisper API进行转录
                logger.info("Starting transcription with OpenAI Whisper API...")
                with open(temp_audio, 'rb') as audio_file:
                    response = openai.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file
                    )
                
                text = response.text
                logger.info(f"Final transcription: {text}")
                
                return text
                
            finally:
                # 清理临时文件
                if os.path.exists(temp_audio):
                    os.remove(temp_audio)
                    
        except Exception as e:
            logger.error(f"Error processing audio: {e}", exc_info=True)
            raise 