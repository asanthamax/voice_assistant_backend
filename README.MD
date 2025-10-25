# Intelligent Voice Assistant for Medical Appointments

An AI-powered voice assistant that helps patients schedule medical appointments through natural conversation. Built with FastAPI, LangGraph, and Google Cloud services.

## Features

- 🎙️ Real-time speech-to-text conversion
- 🗣️ Natural language understanding for appointment scheduling
- 📅 Intelligent calendar management
- 🤖 Autonomous appointment scheduling with Google Calendar integration
- 🔊 Text-to-speech responses
- 💬 WebSocket-based streaming for real-time communication

## Prerequisites

- Python 3.11 or higher
- Poetry package manager
- Google Cloud account with:
  - Speech-to-Text API enabled
  - Text-to-Speech API enabled
  - Calendar API enabled
  - Valid service account credentials

## Installation

1. Clone the repository:
```sh
git clone <repository-url>
cd voice_assistant
```

2. Install dependencies using Poetry:
```sh
poetry install
```

3. Set up Google Cloud credentials:
   - Place your service account JSON file in a secure location
   - Update the `GOOGLE_APPLICATION_CREDENTIALS` path in `.vscode/launch.json`
   - Set your Google API key in the environment variables

## Configuration

The project uses environment variables for configuration. Make sure to set:

```sh
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/service-account.json
GOOGLE_API_KEY=your_api_key
GOOGLE_CALENDAR_ID=<your-email@gmail.com>
```

## Running the Application

1. Using Poetry:
```sh
poetry run uvicorn app.server:app --reload
```

2. Using VS Code:
   - Open the project in VS Code
   - Navigate to the Run and Debug panel
   - Select "Python Debugger: FastAPI"
   - Press F5 or click "Start Debugging"

The server will start at `http://localhost:8000`

## API Endpoints

- `GET /` - Root endpoint to check if service is running
- `GET /health` - Health check endpoint
- `WebSocket /ws/voice` - WebSocket endpoint for voice streaming

## WebSocket Events

### Client to Server:
- `start_listening` - Begin audio capture
- `stop_listening` - End audio capture
- Binary audio data - Raw audio chunks

### Server to Client:
- `listening` - Confirmation of listening start
- `final_transcript` - Complete transcribed text
- `agent_response` - AI assistant's text response
- `audio_response` - Text-to-speech audio data

## Project Structure

```
app/
├── server.py                    # FastAPI application entry point
├── system_prompt.md            # AI assistant system instructions
├── agent_builder/
│   └── agent.py               # LangGraph agent implementation
├── routes/
│   └── voice_route.py         # WebSocket route handlers
├── utils/
│   └── speech_utils.py        # Speech-to-text and text-to-speech utilities
└── voice_manager/
    └── audio_stream_manager.py # Audio streaming management
```

## Technical Details

- **Framework**: FastAPI
- **AI/ML**: LangGraph, LangChain
- **Speech Services**: Google Cloud Speech-to-Text, Text-to-Speech
- **Calendar Integration**: Google Calendar API
- **WebSocket Protocol**: For real-time audio streaming
- **Package Management**: Poetry

## Development

To contribute to the project:

1. Create a new branch
2. Make your changes
3. Write/update tests
4. Submit a pull request

## Testing

Run tests using Poetry:

```sh
poetry run pytest
```
