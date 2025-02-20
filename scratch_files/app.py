from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn
import base64
import logging
import os
from datetime import datetime

import openai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# 配置日志记录
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

app = FastAPI()

# 添加CORS支持
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")

# 添加根路由重定向
@app.get("/")
async def root():
    return FileResponse("static/asr.html")

# 创建音频文件保存目录
AUDIO_DIR = "audio_files"
if not os.path.exists(AUDIO_DIR):
    os.makedirs(AUDIO_DIR)
    logging.info(f"Created audio directory: {AUDIO_DIR}")

# 从环境变量设置OpenAI API密钥
openai.api_key = os.getenv('OPENAI_API_KEY')
if not openai.api_key:
    raise ValueError("OPENAI_API_KEY not found in environment variables")

def process_audio(audio_bytes):
    try:
        # 保存原始数据到临时文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_audio = f"{AUDIO_DIR}/temp_{timestamp}.webm"
        
        with open(temp_audio, 'wb') as f:
            f.write(audio_bytes)
        
        try:
            # 使用OpenAI Whisper API进行转录
            logging.info("Starting transcription with OpenAI Whisper API...")
            with open(temp_audio, 'rb') as audio_file:
                response = openai.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="zh"
                )
            
            text = response.text
            logging.info(f"Final transcription: {text}")
            
            return text
            
        finally:
            # 清理临时文件
            if os.path.exists(temp_audio):
                os.remove(temp_audio)
                
    except Exception as e:
        logging.error(f"Error processing audio: {e}", exc_info=True)
        raise

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    client_id = id(websocket)
    logging.info(f"New WebSocket connection: {client_id}")
    await websocket.accept()
    
    try:
        while True:
            # 接收音频数据
            data = await websocket.receive_text()
            try:
                try:
                    # 解码base64音频数据
                    mime_type = data.split(',')[0].split(':')[1].split(';')[0]
                    logging.info(f"Received audio MIME type: {mime_type}")
                    
                    audio_bytes = base64.b64decode(data.split(',')[1])
                    logging.info(f"Decoded base64 data size: {len(audio_bytes)} bytes")
                    
                    # 检查数据大小
                    if len(audio_bytes) == 0:
                        logging.error("Received empty audio data")
                        continue
                    
                    # 保存原始数据到临时文件
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    temp_webm = f"{AUDIO_DIR}/temp_{timestamp}_client_{client_id}.webm"
                    wav_filename = f"{AUDIO_DIR}/audio_{timestamp}_client_{client_id}.wav"
                    
                    with open(temp_webm, 'wb') as f:
                        f.write(audio_bytes)
                    
                    try:
                        # 直接处理音频数据
                        text = process_audio(audio_bytes)
                        if text:
                            # 发送转录结果回客户端
                            await websocket.send_text(text)
                            logging.info(f"Sent transcription to client {client_id}")
                    except Exception as e:
                        logging.error(f"Error processing audio: {e}")
                        if os.path.exists(temp_webm):
                            os.remove(temp_webm)
                        continue
                except Exception as e:
                    logging.error(f"Error processing audio data: {e}")
                    continue
            except Exception as e:
                error_msg = f"Error processing audio: {str(e)}"
                logging.error(error_msg, exc_info=True)
                await websocket.send_text(f"Error: {error_msg}")
    except Exception as e:
        logging.error(f"WebSocket error for client {client_id}: {e}", exc_info=True)
    finally:
        try:
            await websocket.close()
            logging.info(f"WebSocket connection closed: {client_id}")
        except:
            pass

if __name__ == "__main__":
    logging.info("Starting server on http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)