# AI TickTick Project

An intelligent task management system that integrates TickTick with OpenAI's GPT for natural language task processing. Features voice input support and real-time AI processing.

## Features

- **Voice Task Creation**: Create tasks using voice input with real-time speech recognition
- **Natural Language Processing**: Convert speech and text to structured tasks using GPT-4
- **TickTick Integration**: Full integration with TickTick's task management features
- **Real-time AI Processing**: Instant token calculation and processing with OpenAI's API
- **Web Interface**: Modern, responsive web interface for task management

## Project Structure

```
├── server.py           # Main server entry point
├── server/            # Server functionality modules
│   ├── __init__.py
│   └── oai_realtime.py  # OpenAI real-time processing
├── static/            # Web assets
│   ├── asr.html       # Speech recognition interface
│   └── index1.html    # Main web interface
├── tools/             # Tool implementations
│   └── ticktick.py    # TickTick task management tools
├── clients/           # API clients
│   └── ticktick/      # TickTick API client
│       ├── client.py      # Main client implementation
│       └── authenticate.py # Authentication handling
└── tests/             # Test files
    └── test_ticktick_full.py  # TickTick integration tests
```

## Prerequisites

- Python 3.11+
- TickTick Developer Account
- OpenAI API Key

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd ticktick-ai 
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file with your credentials:
```env
TICKTICK_CLIENT_ID=your_client_id
TICKTICK_CLIENT_SECRET=your_client_secret
OPENAI_API_KEY=your_openai_api_key
```

## Running the Server

1. Start the server:
```bash
python server.py
```

2. Access the web interface:
   - Main interface: `http://localhost:8000`
   - Voice input interface: `http://localhost:8000/static/asr.html`

3. Using the voice interface:
   - Click the "开始录音" button to start recording
   - Speak clearly into your microphone
   - The transcribed text will appear in real-time
   - Click the button again to stop recording

4. Server Features:
   - WebSocket-based real-time communication
   - Automatic audio format conversion
   - Integrated OpenAI token processing
   - TickTick API integration

## Testing

Run the test suite:
```bash
python -m pytest tests/
```

## Features

### TickTick Integration
- Create, read, update, and delete tasks
- Project management
- Task prioritization
- Due date and reminder settings

### Natural Language Processing
- Convert natural language to structured tasks
- Intelligent task parsing
- Context-aware task creation

### Web Interface
- **Voice Input**: Real-time speech-to-text conversion
  - 16kHz sampling rate for optimal speech recognition
  - WebSocket-based real-time communication
  - Automatic reconnection handling
- **Task Management**:
  - Real-time task updates and status tracking
  - Interactive task creation and editing
  - Voice and text input support
- **User Experience**:
  - Modern, responsive design
  - Visual feedback for recording status
  - Error handling and recovery

## API Documentation

### TickTick Client
```python
from clients.ticktick import TickTickClient

client = TickTickClient(client_id, client_secret)
client.authenticate()
```

### Task Manager
```python
from tools.ticktick import TaskManager

manager = TaskManager(client_id, client_secret)
manager.create_task("Complete project documentation", priority=3)
```

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
