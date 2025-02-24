import os
import logging
import uvicorn
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import openai
from dotenv import load_dotenv
from server.session_handler import SessionHandler

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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Set up OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')
if not openai.api_key:
    raise ValueError("OPENAI_API_KEY not found in environment variables")

# Create session handler
session_handler = SessionHandler()

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    client_id = id(websocket)
    logger.info(f"New WebSocket connection: {client_id}")

    try:
        while True:
            # Receive data
            data = await websocket.receive_text()
            
            # Handle message
            status, message = await session_handler.handle_message(client_id, data)
            
            # Send response
            if status and message:
                await websocket.send_text(f"[{status}] {message}")
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {e}", exc_info=True)
    finally:
        logger.info(f"WebSocket connection closed: {client_id}")

# Root route
@app.get("/")
async def root():
    return FileResponse("static/asr.html")

# Run the server
if __name__ == "__main__":
    logger.info("Starting server on http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)