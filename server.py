import os
import time
from autogen_agentchat.messages import TextMessage
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn
import base64
import logging
import asyncio
from datetime import datetime
from typing import Awaitable, Callable, Optional, Dict, Tuple
from autogen_core import CancellationToken
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.teams import MagenticOneGroupChat
from autogen_agentchat.ui import Console
from tools.ticktick import TaskManager
from session import Session, SessionResult

import openai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create console handler with formatting
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)

# Add handler to logger
logger.addHandler(console_handler)

# Disable propagation to root logger
logger.propagate = False

# Initialize FastAPI app
app = FastAPI()

# Add CORS support
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Create audio directory
AUDIO_DIR = "audio_files"
if not os.path.exists(AUDIO_DIR):
    os.makedirs(AUDIO_DIR)
    logger.info(f"Created audio directory: {AUDIO_DIR}")

# Set up OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')
if not openai.api_key:
    raise ValueError("OPENAI_API_KEY not found in environment variables")

# Global session storage
sessions: Dict[int, Session] = {}

class UserInputHelper:
    def __init__(self):
        self.user_input_queue = asyncio.Queue()

    def get_user_input_func(self) -> Callable[[str, Optional[CancellationToken]], Awaitable[str]]:
        async def user_input(prompt: str, cancellation_token: Optional[CancellationToken]) -> str:
            return await self.user_input_queue.get()

        return user_input

    async def recv_user_input(self, text: str):
        await self.user_input_queue.put(text)

def process_audio(audio_bytes):
    try:
        # Save raw data to temporary file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_audio = f"{AUDIO_DIR}/temp_{timestamp}.webm"
        
        with open(temp_audio, 'wb') as f:
            f.write(audio_bytes)
        
        try:
            # Use OpenAI Whisper API for transcription
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
            # Clean up temporary file
            if os.path.exists(temp_audio):
                os.remove(temp_audio)
                
    except Exception as e:
        logger.error(f"Error processing audio: {e}", exc_info=True)
        raise

def task_prompt(user_request: str, history_digest: str) -> str:
    """Generate a task prompt based on the user's request"""
     # Define task description with available tools
    task_description = """
Available TickTick Task Management Tools:

1. create_task
   - Purpose: Create a new task in Inbox
   - Required Parameters:
     * title: Task title
   - Optional Parameters:
     * content: Task description
     * due_date: Due date (YYYY-MM-DD)
     * start_date: Start date (YYYY-MM-DD)
     * is_all_day: Whether it's an all-day task (default: True)
     * priority: Task priority (0=none, 1=low, 3=medium, 5=high)
   - Returns: Created task information

2. list_tasks
   - Purpose: List tasks from Inbox
   - Returns: List of all tasks

3. complete_task
   - Purpose: Mark a task as completed
   - Required Parameters:
     * task_id: ID of the task to complete
   - Returns: None

4. delete_task
   - Purpose: Delete a task from Inbox
   - Required Parameters:
     * task_id: ID of the task to delete
   - Returns: None

5. get_tasks_by_date
   - Purpose: Get tasks within a date range
   - Required Parameters:
     * start_date: Start date (YYYY-MM-DD)
   - Optional Parameters:
     * end_date: End date (YYYY-MM-DD)
   - Returns: List of tasks within the date range

6. get_completed_tasks
   - Purpose: Get all completed tasks
   - Returns: List of completed tasks

Important Notes:
- All operations are performed in the Inbox
- Dates must be in YYYY-MM-DD format
- Task IDs are required for completing and deleting tasks
- Priority levels: 0=none, 1=low, 3=medium, 5=high
"""
    if history_digest:
        task_description += """
## Background Information
User's previous requests have been summarized as follows:
{history_digest}
"""
    task_description += """
User's new request: {user_request}
"""
    return task_description.format(user_request=user_request, history_digest=history_digest)


# Initialize agents
def init_agents() -> Tuple[AssistantAgent, UserProxyAgent, OpenAIChatCompletionClient, UserInputHelper]:
    # Get environment variables
    api_key = os.getenv("OPENAI_API_KEY")
    ticktick_client_id = os.getenv("TICKTICK_CLIENT_ID")
    ticktick_client_secret = os.getenv("TICKTICK_CLIENT_SECRET")
    
    if not all([api_key, ticktick_client_id, ticktick_client_secret]):
        raise ValueError("Missing required environment variables")
    
    if not isinstance(ticktick_client_id, str) or not isinstance(ticktick_client_secret, str):
        raise TypeError("TickTick client_id and client_secret must be strings")

    # Initialize task manager
    task_manager = TaskManager(ticktick_client_id, ticktick_client_secret)

    # model_client = OpenAIChatCompletionClient(
    #     model="gpt-4o-mini",
    #     api_key=openai.api_key,
    # )

    model_client = OpenAIChatCompletionClient(
        model="llama-3.3-70b",
        api_key=os.getenv("CEREBRAS_API_KEY"),
        base_url="https://api.cerebras.ai/v1",
        model_info={
            "vision": False,
            "function_calling": True,
            "json_output": True,
            "family": "unknown",
        },
        llm_config={
            "cache_seed": 42,  # Enable caching with seed 42
            "cache_path_root": ".cache/llm_cache"  # Specify cache directory
        }
    )

    # Create the task management assistant
    assistant = AssistantAgent(
        name="task_assistant",
        system_message="""
        You are an expert task management assistant for TickTick's Inbox. You help users manage their tasks efficiently using the following capabilities:

        Available Functions:

        1. create_task(title, content='', due_date=None, start_date=None, is_all_day=True, priority=0)
           - Creates a new task in Inbox with the following parameters:
             * title: Task title (required)
             * content: Task description
             * due_date: Due date in 'YYYY-MM-DD' format
             * start_date: Start date in 'YYYY-MM-DD' format
             * is_all_day: Whether it's an all-day task
             * priority: Task priority (0=none, 1=low, 3=medium, 5=high)

        2. list_tasks()

        3. complete_task(task_id)
           - Marks a task as completed
           - Requires task_id from list_tasks

        4. delete_task(task_id)
           - Removes a task from Inbox
           - Requires task_id from list_tasks

        5. get_tasks_by_date(start_date, end_date=None)
           - Gets tasks within a date range:
             * start_date: Start date 'YYYY-MM-DD'
             * end_date: Optional end date 'YYYY-MM-DD'

        6. get_completed_tasks()
           - Retrieves all completed tasks from Inbox

        Always follow these steps:
        1. UNDERSTAND: Analyze the user's request carefully
        2. VALIDATE: Ensure you have all required information
        3. EXECUTE: Perform the requested operation
        4. VERIFY: Check the result and provide clear feedback

        Important Notes:
        - All dates must be in 'YYYY-MM-DD' format
        - Priority levels: 0=none, 1=low, 3=medium, 5=high
        - All operations are performed in the Inbox
        - Task IDs are required for complete_task and delete_task

        Say 'goodbye' to end the conversation.
        """,
        tools=[
            task_manager.create_task,
            task_manager.list_tasks,
            task_manager.complete_task,
            task_manager.delete_task,
            task_manager.get_tasks_by_date,
            task_manager.get_completed_tasks
        ],
        model_client=model_client,
    )

    user_input_helper = UserInputHelper()

    # Create the user proxy
    user_proxy = UserProxyAgent(
        name="user",
        input_func=user_input_helper.get_user_input_func(),
    )

    return assistant, user_proxy, model_client, user_input_helper

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    client_id = id(websocket)
    logger.info(f"New WebSocket connection: {client_id}")

    # Initialize agents and team
    assistant, user_proxy, model_client, user_input_helper = init_agents()
    team = MagenticOneGroupChat(
        participants=[user_proxy, assistant],
        model_client=model_client,
        max_turns=20,
        max_stalls=3,
        final_answer_prompt="Based on our analysis of your request, here is the response:"
    )
    
    history_digest = ""        

    session = Session(team, model_client)

    while True:
        # Receive audio data
        try:
            data = await websocket.receive_text()
            # Decode base64 audio data

            mime_type = data.split(',')[0].split(':')[1].split(';')[0]
            logger.info(f"Received audio MIME type: {mime_type}")
            
            audio_bytes = base64.b64decode(data.split(',')[1])
            logger.info(f"Decoded base64 data size: {len(audio_bytes)} bytes")
            
            # Process audio to text
            text = process_audio(audio_bytes)

            if text is None or text == "":
                continue

            if not session.is_active:
                session.start(task_prompt(text, history_digest))
            else:
                await user_input_helper.recv_user_input(text)
            
            # continue the inference
            result: SessionResult = await session.run_until_stop()
            print(result)
            if result == SessionResult.FINISHED:
                history_digest = await session.digest()
                logger.info(f"History digest: {history_digest}")
                await websocket.send_text(f"[{result.status}] {history_digest}")
                session = Session(team, model_client)
            
            if result.last_message:
                await websocket.send_text(f"[{result.status}] {result.last_message}")
                logger.info(f"Sent result to client {client_id}: [{result.status}] {result.last_message}")
                
        except Exception as e:
            error_msg = f"Error processing request: {str(e)}"
            logger.error(error_msg, exc_info=True)
            await websocket.send_text(f"Error: {error_msg}")
            
# Root route
@app.get("/")
async def root():
    return FileResponse("static/asr.html")


async def test_run():
    # Initialize agents
    assistant, user_proxy, model_client = init_agents()
    
    # Create the team
    team = MagenticOneGroupChat(
        participants=[user_proxy, assistant],
        model_client=model_client,
        max_turns=20,
        max_stalls=3,
        final_answer_prompt="Based on our analysis of your request, here is the response:"
    )
    
    # Run the test command
    test_command = "当前最近的task是什么"
    await Console(team.run_stream(task=task_prompt(test_command)))
    

# Run the server
if __name__ == "__main__":
    logger.info("Starting server on http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)