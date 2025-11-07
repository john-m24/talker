# macOS Voice Window Agent

A Python-based voice window agent that allows you to control macOS application windows using natural language commands. The agent uses a local AI model to parse your commands and AppleScript to control windows.

## Features

- **Natural Language Commands**: Speak or type commands like "Bring Docker to view" or "Focus Chrome"
- **AI-Powered Intent Parsing**: Uses a local OpenAI-compatible LLM to understand your commands
- **Fuzzy App Matching**: Automatically matches fuzzy app names to exact application names
- **Context-Aware**: Uses running and installed apps for better matching

## Requirements

- macOS (for AppleScript support)
- Python 3.7+
- Local LLM server running OpenAI-compatible API (e.g., Ollama, llama.cpp, etc.)

## Installation

1. Clone or download this repository

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

Or install manually:
```bash
pip install openai
```

3. Ensure your local LLM server is running and accessible at the configured endpoint (default: `http://192.168.1.198:10000/v1`)

## Configuration

The agent can be configured via environment variables:

- `VOICE_AGENT_LLM_ENDPOINT`: URL of your local LLM endpoint (default: `http://192.168.1.198:10000/v1`)
- `VOICE_AGENT_LLM_MODEL`: Model name to use (default: `local`)

Example:
```bash
export VOICE_AGENT_LLM_ENDPOINT="http://localhost:8000/v1"
export VOICE_AGENT_LLM_MODEL="llama2"
python3 -m voice_agent.main
```

## Usage

Run the agent:
```bash
python3 -m voice_agent.main
```

### Example Commands

- **Focus an app**: "Bring Docker to view", "Focus Chrome", "Show Slack"
- **List apps**: "List apps", "What's running", "Show me my open applications"
- **Quit**: "quit", "exit", or press Ctrl+C

The agent will:
1. Listen to your command (currently via text input)
2. Get context about running and installed apps
3. Use AI to parse your intent and extract the exact app name
4. Execute the appropriate AppleScript command

## Project Structure

```
voice_agent/
  __init__.py          # Package initialization
  main.py              # Entry point with main loop
  stt.py               # Speech-to-text abstraction (currently text input)
  ai_agent.py          # AI client for intent parsing
  window_control.py    # AppleScript helpers for window control
  config.py            # Configuration (LLM endpoint, etc.)
```

## Adding Real Speech-to-Text

Currently, the agent uses text input as a placeholder. To add real microphone transcription:

1. Install a speech-to-text library (e.g., `openai-whisper` or `whisper.cpp`)
2. Modify `voice_agent/stt.py` to use the library instead of `input()`

Example with OpenAI Whisper:
```python
import whisper

model = whisper.load_model("base")

def transcribe_once() -> str:
    # Record audio from microphone
    # Return transcribed text
    pass
```

## How It Works

1. **Input**: User provides command via text (or voice, once STT is integrated)
2. **Context Gathering**: Agent collects list of running apps and optionally installed apps
3. **AI Parsing**: Local LLM parses the command with context to extract:
   - Intent type (`list_apps` or `focus_app`)
   - Exact app name (matched from running/installed apps)
4. **Execution**: AppleScript commands are executed via `osascript` to control windows

## Troubleshooting

- **"Error initializing AI agent"**: Check that your LLM endpoint is running and accessible
- **"Failed to activate app"**: The app name might not match exactly. Check running apps with "list apps"
- **AppleScript errors**: Ensure Terminal has accessibility permissions in System Preferences > Security & Privacy

## License

MIT

