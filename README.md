# Talker

A Python-based voice window agent that allows you to control macOS application windows using natural language commands. The agent uses a local AI model to parse your commands and AppleScript to control windows.

## Features

- **Natural Language Commands**: Speak or type commands like "Bring Docker to view" or "Focus Chrome"
- **AI-Powered Intent Parsing**: Uses a local OpenAI-compatible LLM to understand your commands
- **Fuzzy App Matching**: Automatically matches fuzzy app names to exact application names
- **Context-Aware**: Uses running and installed apps for better matching
- **Preset Window Layouts**: Define and activate named presets to quickly arrange multiple apps across monitors

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

This installs:
- `openai` - For LLM API client
- `pyobjc` - For macOS native speech recognition (default on macOS, best performance)
- `sounddevice` - For microphone access
- `numpy` - For audio processing
- `SpeechRecognition` - For Sphinx speech recognition (fallback)
- `pyaudio` - For microphone access (used by Sphinx)
- `pocketsphinx` - For offline speech recognition (fallback)

**macOS Note**: You may need to install PortAudio:
```bash
brew install portaudio
```

3. Ensure your local LLM server is running and accessible at the configured endpoint (default: `http://localhost:8000/v1`)

## Configuration

The agent can be configured via environment variables:

- `VOICE_AGENT_LLM_ENDPOINT`: URL of your local LLM endpoint (default: `http://localhost:8000/v1`)
- `VOICE_AGENT_LLM_MODEL`: Model name to use (default: `qwen-30b`)
- `VOICE_AGENT_STT_ENGINE`: Speech-to-text engine - `macos` (default on macOS), `whisper`, or `sphinx`
- `VOICE_AGENT_HOTKEY`: Hotkey for voice mode (default: `cmd+alt`)
- `VOICE_AGENT_TEXT_HOTKEY`: Hotkey for text mode (default: `ctrl+alt`)
- `VOICE_AGENT_PRESETS_FILE`: Path to presets configuration file (optional, see Presets section below)

Example:
```bash
export VOICE_AGENT_LLM_ENDPOINT="http://localhost:8000/v1"
export VOICE_AGENT_LLM_MODEL="llama2"
python3 -m voice_agent.main
```

### Presets Configuration

You can define preset window layouts that arrange multiple applications across monitors. Presets are stored in a JSON configuration file.

**Preset File Location** (checked in order):
1. Path specified in `VOICE_AGENT_PRESETS_FILE` environment variable
2. `~/.voice_agent_presets.json` (user home directory)
3. `presets.json` in the project root

**Preset File Format**:

Create a JSON file with the following structure:

```json
{
  "code space": {
    "apps": [
      {
        "app_name": "Google Chrome",
        "monitor": "left",
        "maximize": false
      },
      {
        "app_name": "Cursor",
        "monitor": "right",
        "maximize": false
      }
    ]
  },
  "development": {
    "apps": [
      {
        "app_name": "Cursor",
        "monitor": "left",
        "maximize": true
      },
      {
        "app_name": "Terminal",
        "monitor": "right",
        "maximize": false
      }
    ]
  }
}
```

Each preset contains:
- **Preset name**: The key (e.g., "code space") - this is what you'll say to activate it
- **apps**: Array of app placement instructions, each with:
  - `app_name`: Exact application name (must match the app name as shown in "list apps")
  - `monitor`: One of `"main"`, `"left"`, or `"right"` (must match your monitor configuration in `config.py`)
  - `maximize`: Optional boolean (default: `false`) - whether to maximize the window to fill the monitor

See `presets.json.example` for a complete example.

## Usage

Run the agent:
```bash
python3 -m voice_agent.main
```

### Voice Mode

Press `cmd+alt` (or your configured `VOICE_AGENT_HOTKEY`) to activate voice mode. Hold the hotkey while speaking, then release to process your command.

The agent will:
1. Listen to your voice command via microphone
2. Transcribe your speech using macOS native Speech Recognition (default on macOS, best performance)
3. Get context about running and installed apps
4. Use AI to parse your intent and extract the exact app name
5. Execute the appropriate AppleScript command

**Note**: Uses offline speech recognition - no API keys, no internet connection, and no cloud services required! macOS native speech recognition provides the best performance and accuracy on macOS.

### Text Mode (Electron Command Palette)

Press `ctrl+alt` (or your configured `VOICE_AGENT_TEXT_HOTKEY`) to open the Electron command palette. The Electron client provides a reliable, global-hotkey command palette with live autocomplete.

**Setup:**
1) Backend API is started automatically by the agent on `127.0.0.1:$VOICE_AGENT_API_PORT` (default `8770`).
2) In a separate terminal:
```bash
cd electron-client
npm install
npm start
```
3) Press `ctrl+alt` (or your configured `VOICE_AGENT_TEXT_HOTKEY`) to open the palette, type to see suggestions, Enter to submit, Esc to hide.

**Features:**
- Live autocomplete as you type
- Results display for list commands (keeps palette open for follow-up)
- Auto-closes after action commands
- Always-on-top window that focuses reliably

**Env vars:**
```bash
export VOICE_AGENT_API_PORT=8770            # Backend API port
export VOICE_AGENT_TEXT_HOTKEY="ctrl+alt"   # Hotkey to trigger palette
```

**Notes:**
- The Electron client uses local-only HTTP to fetch suggestions (`GET /suggest?text=...`) and submit commands (`POST /submit`).
- The agent processes submitted commands immediately in the main loop.
- List commands (list apps, list tabs, etc.) display results in the palette and keep it open for follow-up commands.
- Action commands (focus, place, close, etc.) auto-close the palette after execution.

Both voice and text modes work simultaneously - use whichever is more convenient!

### Example Commands

- **Focus an app**: "Bring Docker to view", "Focus Chrome", "Show Slack"
- **Place app on monitor**: "Put Chrome on left monitor", "Move Cursor to right screen", "Place Terminal on main monitor"
- **Window resizing and snapping**: "Put Chrome on left half of right monitor", "Snap Cursor to right side", "Resize Terminal to 1200x800", "Center Slack on left monitor", "Maximize Chrome"
- **List apps**: "List apps", "What's running", "Show me my open applications"
- **Activate preset**: "Activate code space", "code space", "Set up development", "Load browsing"
- **Switch Chrome tabs**: "Switch to Gmail", "Go to tab 3", "List tabs"
- **Close app/tab**: "Close Chrome", "Close tab 2", "Quit Docker"
- **Quit**: "quit", "exit", or press Ctrl+C

## Project Structure

```
voice_agent/
  __init__.py          # Package initialization
  main.py              # Entry point with main loop
  stt.py               # Speech-to-text abstraction (macOS native/Whisper/Sphinx)
  ai_agent.py          # AI client for intent parsing
  window_control.py    # AppleScript helpers for window control
  config.py            # Configuration (LLM endpoint, etc.)
  presets.py           # Preset window layout management
  commands/            # Command implementations
    activate_preset.py # Preset activation command
    ...
```

## Microphone Permissions

On macOS, you'll need to grant microphone permissions to Terminal (or your Python interpreter):
1. System Preferences > Security & Privacy > Privacy > Microphone
2. Enable Terminal (or your IDE/terminal app)

**macOS native / Whisper**: Speak your command, then press Enter when done.
**Sphinx**: The agent will automatically detect when you start and stop speaking.

## How It Works

1. **Input**: User provides command via voice (hold hotkey and speak) or text (press text hotkey and type)
2. **Context Gathering**: Agent collects list of running apps, installed apps, Chrome tabs (if applicable), and available presets
3. **AI Parsing**: Local LLM parses the command with context to extract:
   - Intent type (`list_apps`, `focus_app`, `place_app`, `activate_preset`, `switch_tab`, `close_app`, `close_tab`, etc.)
   - Exact app name (matched from running/installed apps)
   - Monitor placement (for `place_app`)
   - Preset name (for `activate_preset`)
4. **Execution**: AppleScript commands are executed via `osascript` to control windows, or preset commands execute multiple app placements

## Planned Features

### High Priority
- **Window resizing commands**: "Resize Chrome to half screen", "Make this window bigger"
- **Multi-browser support**: Extend tab switching to Firefox, Safari, and Edge
- **Window snapping**: "Snap to left", "Tile windows", "Cascade all"
- **Custom voice aliases**: Define shortcuts for frequently used commands
- **Dynamic preset creation**: "Save current layout as [name]"

### Medium Priority
- **macOS Spaces integration**: Control and switch between desktop spaces
- **Voice feedback**: Spoken confirmations for executed commands
- **Command history**: Review and repeat recent commands
- **Window state management**: Undo last action, restore previous window positions
- **Auto-detect monitors**: Automatic multi-monitor configuration detection
- **Multi-OS support**: Extend functionality to Linux and Windows

Many more features to be added!

## Troubleshooting

- **"Error initializing AI agent"**: Check that your LLM endpoint is running and accessible
- **"Failed to activate app"**: The app name might not match exactly. Check running apps with "list apps"
- **AppleScript errors**: Ensure Terminal has accessibility permissions in System Preferences > Security & Privacy

## License

MIT

