from flask import Blueprint, request, jsonify, send_from_directory
import openai
import os
import requests
from dotenv import load_dotenv
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()

# 初始化 OpenAI 客户端
api_key = os.getenv('OPENAI_API_KEY')
if not api_key:
    raise ValueError('OPENAI_API_KEY environment variable is not set')

client = openai.OpenAI(api_key=api_key)

# 创建 Blueprint
oai_bp = Blueprint('oai', __name__)

# 添加静态文件路由
@oai_bp.route('/')
def serve_index():
    return send_from_directory('static', 'index1.html')

@oai_bp.route('/get_token', methods=['GET'])
def get_token():
    try:
        # 请求OpenAI的ephemeral token
        response = requests.post(
            'https://api.openai.com/v1/realtime/sessions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'gpt-4o-realtime-preview-2024-12-17',
                'voice': 'verse'
            }
        )
        response.raise_for_status()
        data = response.json()
        
        logger.info('Successfully obtained ephemeral token')
        # 直接返回OpenAI的响应
        return jsonify(data)
    except Exception as e:
        logger.error(f'Error getting token: {str(e)}')
        return jsonify({'error': str(e)}), 500

@oai_bp.route('/process_command', methods=['POST'])
def process_command():
    try:
        data = request.json
        command = data.get('command')
        if not command:
            return jsonify({'error': 'No command provided'}), 400

        logger.info(f'Received command: {command}')
        # 这里可以调用app.py中的相应功能来处理命令
        # TODO: 集成你的Ticktick功能处理逻辑
        
        return jsonify({'status': 'success', 'message': f'Processing command: {command}'})
    except Exception as e:
        logger.error(f'Error processing command: {str(e)}')
        return jsonify({'error': 'Failed to process command'}), 500

