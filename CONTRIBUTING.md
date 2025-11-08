# Contributing to macOS Voice Window Agent

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to the project.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/your-username/talk-to-computer.git
   cd talk-to-computer
   ```
3. **Create a virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On macOS/Linux
   ```
4. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
5. **Install in development mode** (optional):
   ```bash
   pip install -e .
   ```

## Development Setup

### Prerequisites

- macOS (required for AppleScript support)
- Python 3.7 or higher
- A local LLM server running an OpenAI-compatible API (e.g., Ollama, llama.cpp)

### macOS Dependencies

You may need to install PortAudio:
```bash
brew install portaudio
```

### Configuration

Set up environment variables for development:
```bash
export VOICE_AGENT_LLM_ENDPOINT="http://localhost:8000/v1"
export VOICE_AGENT_LLM_MODEL="your-model-name"
export VOICE_AGENT_STT_ENGINE="whisper"  # or "macos" or "sphinx"
```

## Making Changes

1. **Create a branch** for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```

2. **Make your changes** following the coding style guidelines below

3. **Test your changes**:
   - Run the agent and test the functionality you modified
   - Ensure existing functionality still works

4. **Commit your changes**:
   ```bash
   git add .
   git commit -m "Description of your changes"
   ```
   
   Use clear, descriptive commit messages. Follow the format:
   - `feat: Add new feature`
   - `fix: Fix bug description`
   - `docs: Update documentation`
   - `refactor: Refactor code`
   - `test: Add tests`

5. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```

6. **Create a Pull Request** on GitHub

## Coding Style

- Follow **PEP 8** Python style guidelines
- Use **type hints** where appropriate
- Write **docstrings** for functions and classes (Google style)
- Keep functions focused and single-purpose
- Use meaningful variable and function names

### Example:

```python
def focus_app(app_name: str, running_apps: list) -> bool:
    """
    Focus an application by name.
    
    Args:
        app_name: Name of the application to focus
        running_apps: List of currently running applications
        
    Returns:
        True if the app was successfully focused, False otherwise
    """
    # Implementation
    pass
```

## Project Structure

```
voice_agent/
  __init__.py          # Package initialization
  main.py              # Entry point
  ai_agent.py          # AI client for intent parsing
  config.py            # Configuration
  commands/            # Command implementations
  stt/                 # Speech-to-text engines
  utils/               # Utility functions
```

## Testing

While automated tests are not yet set up, please:

- Manually test your changes before submitting
- Test edge cases and error conditions
- Ensure backward compatibility when possible

## Pull Request Guidelines

- **Keep PRs focused**: One feature or fix per PR
- **Write clear descriptions**: Explain what changes you made and why
- **Reference issues**: Link to any related issues
- **Update documentation**: If you add features, update the README
- **Test thoroughly**: Make sure your changes work as expected

## Reporting Issues

When reporting bugs or requesting features:

- Use the GitHub issue tracker
- Provide a clear description
- Include steps to reproduce (for bugs)
- Specify your macOS version and Python version
- Include relevant error messages or logs

## Questions?

Feel free to open an issue for questions or discussions about the project.

Thank you for contributing! 🎉

