"""Main entry point for the voice window agent."""

import sys
import time
from typing import Optional, Tuple
from .stt import transcribe_while_held
from .stt.factory import set_cached_engine
from .ai_agent import AIAgent
from .window_control import list_running_apps, list_installed_apps
from .tab_control import list_chrome_tabs_with_content
from .api_server import send_request, wait_for_response, trigger_palette
from .commands import CommandExecutor
from .config import (
    LLM_ENDPOINT, STT_ENGINE, HOTKEY, TEXT_HOTKEY, WHISPER_MODEL,
    CACHE_ENABLED, CACHE_HISTORY_SIZE, CACHE_HISTORY_PATH,
    AUTOCOMPLETE_ENABLED, AUTOCOMPLETE_MAX_SUGGESTIONS, LLM_CACHE_ENABLED,
    FILE_CONTEXT_ENABLED
)
from .cache import initialize_cache_manager, get_cache_manager
from .hotkey import HotkeyListener
from .presets import load_presets, list_presets


def print_help():
    """Print welcome message and help text."""
    print("=" * 60)
    print("Talker")
    print("=" * 60)
    print(f"\n⌨️  Hotkeys:")
    print(f"  - Voice mode: Press {HOTKEY} to activate (works from any window)")
    print(f"  - Text mode: Press {TEXT_HOTKEY} to activate (works from any window)")
    print("\n🎤 Voice Commands / 📝 Text Commands:")
    print("  - 'Bring [App] to view' / 'Focus [App]' / 'Show [App]'")
    print("  - 'Put [App] on [main/right/left] monitor' / 'Move [App] to [main/right/left] screen'")
    print("  - 'Place [App] on [monitor] and maximize'")
    print("  - 'List apps' / 'What's running'")
    print("  - 'Switch to [Tab]' / 'Go to tab [Number]' / 'List tabs'")
    print("  - 'Close [App]' / 'Quit [App]'")
    print("  - 'Close tab [Number]' / 'Close [Tab Name]'")
    print("  - 'Activate [Preset]' / '[Preset]' / 'Set up [Preset]' (preset window layouts)")
    print("  - 'quit' or 'exit' to stop")
    print(f"\nUsing LLM endpoint: {LLM_ENDPOINT}")
    print(f"Using STT engine: {STT_ENGINE.upper()}")
    print("=" * 60)
    print(f"\nVoice mode: Hold {HOTKEY} to speak, release to process command.")
    print(f"Text mode: Press {TEXT_HOTKEY} to open text input dialog.\n")


def time_operation(operation_name: str, func, *args, **kwargs):
    """
    Time an operation and print the duration.
    
    Args:
        operation_name: Name of the operation for display
        func: Function to call
        *args, **kwargs: Arguments to pass to the function
        
    Returns:
        Result of the function call
    """
    start_time = time.time()
    result = func(*args, **kwargs)
    elapsed = time.time() - start_time
    print(f"⏱️  {operation_name} took: {elapsed:.2f}s")
    return result


def handle_clarification(
    text: str,
    intent: dict,
    agent: AIAgent,
    running_apps: list,
    installed_apps: list,
    chrome_tabs: Optional[list],
    chrome_tabs_raw: Optional[str],
    available_presets: Optional[list] = None,
    recent_files: Optional[list] = None,
    active_projects: Optional[list] = None,
    current_project: Optional[dict] = None
) -> Tuple[str, dict]:
    """
    Handle clarification dialog if needed.
    
    Args:
        text: Original transcribed text
        intent: Parsed intent dictionary (with 'commands' array for multiple commands)
        agent: AI agent instance
        running_apps: List of running apps
        installed_apps: List of installed apps
        chrome_tabs: List of Chrome tabs
        
    Returns:
        Tuple of (final_text, final_intent)
    """
    needs_clarification = intent.get("needs_clarification", False)
    if not needs_clarification:
        return text, intent
    
    clarification_reason = intent.get("clarification_reason")
    commands_count = len(intent.get("commands", []))
    
    print("⚠️  Command needs clarification...")
    if commands_count > 1:
        print(f"   Detected {commands_count} commands")
    if clarification_reason:
        print(f"   Reason: {clarification_reason}")
    
    # Send clarification request to Electron client
    trigger_palette()  # Ensure Electron window is visible
    send_request("clarification", {"text": text, "reason": clarification_reason})
    
    # Wait for user response
    response = wait_for_response()
    
    if response is None or response.get("cancelled", False):
        # User cancelled
        print("   Clarification cancelled, skipping command.\n")
        return None, None
    
    confirmed_text = response.get("text", "").strip()
    # If empty text, treat as "use original text" (confirm without changes)
    if not confirmed_text:
        confirmed_text = text
    
    if confirmed_text != text:
        # User corrected the text, re-parse intent
        print(f"   Corrected text: '{confirmed_text}'")
        text = confirmed_text
        
        # Re-parse intent with corrected text
        start_llm = time.time()
        intent = agent.parse_intent(
            text, running_apps, installed_apps, 
            chrome_tabs=chrome_tabs, chrome_tabs_raw=chrome_tabs_raw, 
            available_presets=available_presets,
            recent_files=recent_files, active_projects=active_projects, 
            current_project=current_project
        )
        llm_time = time.time() - start_llm
        print(f"⏱️  LLM (Re-parsing) took: {llm_time:.2f}s\n")
    else:
        # User confirmed, proceed with original intent
        print("   Text confirmed, proceeding with command.\n")
    
    return text, intent


def process_command(
    text: str,
    agent: AIAgent,
    running_apps: list,
    installed_apps: list,
    chrome_tabs: Optional[list],
    chrome_tabs_raw: Optional[str],
    available_presets: Optional[list],
    command_executor: CommandExecutor,
    recent_files: Optional[list] = None,
    active_projects: Optional[list] = None,
    current_project: Optional[dict] = None
) -> bool:
    """
    Process a command from text input (voice or text mode).
    
    Args:
        text: Command text to process
        agent: AI agent instance
        running_apps: List of running apps
        installed_apps: List of installed apps
        chrome_tabs: List of Chrome tabs (if available)
        chrome_tabs_raw: Raw AppleScript output for Chrome tabs (if available)
        available_presets: List of available preset names
        command_executor: Command executor instance
        recent_files: List of recently opened files (optional)
        active_projects: List of active projects (optional)
        current_project: Current project dict (optional)
        
    Returns:
        True if command was processed successfully, False otherwise
    """
    # Check for quit commands
    if text.lower() in ["quit", "exit", "q"]:
        return False
    
    # Chrome tabs should already be pre-loaded with content from main loop
    # No need to fetch again here
    
    # Parse intent using AI agent
    print(f"\n📝 Processing: '{text}'...")
    intent_result = time_operation(
        "LLM (Intent Parsing)",
        agent.parse_intent,
        text, running_apps, installed_apps, 
        chrome_tabs=chrome_tabs, chrome_tabs_raw=chrome_tabs_raw, 
        available_presets=available_presets,
        recent_files=recent_files, active_projects=active_projects, 
        current_project=current_project
    )
    
    # Handle clarification if needed
    text, intent_result = handle_clarification(
        text, intent_result, agent, running_apps, installed_apps, 
        chrome_tabs, chrome_tabs_raw, available_presets,
        recent_files=recent_files, active_projects=active_projects, 
        current_project=current_project
    )
    
    if text is None or intent_result is None:
        # User cancelled clarification
        return True
    
    # Show feedback for multiple commands
    commands_list = intent_result.get("commands", [])
    if len(commands_list) > 1:
        print(f"✓ Detected {len(commands_list)} commands\n")
    
    # Execute command(s) using command executor
    command_executor.execute(
        intent_result, 
        running_apps=running_apps, 
        chrome_tabs=chrome_tabs,
        recent_files=recent_files,
        active_projects=active_projects,
        current_project=current_project
    )
    
    # Track command in history (if cache is enabled)
    cache_manager = get_cache_manager()
    if cache_manager:
        try:
            cache_manager.add_to_history(text)
        except Exception as e:
            # Silently fail if cache is not available
            pass
    
    return True


def main():
    """Main loop for the voice agent."""
    print_help()
    
    # Pre-load Whisper model if using Whisper engine (reduces delay on hotkey press)
    whisper_engine = None
    if STT_ENGINE.lower() == "whisper":
        try:
            from .stt.engines.whisper_engine import preload_whisper_model, WhisperSTTEngine
            print("🔄 Pre-loading Whisper model...")
            preload_whisper_model(WHISPER_MODEL)
            print("🔄 Starting persistent microphone stream...")
            whisper_engine = WhisperSTTEngine.initialize_persistent_stream()
            # Set the cached engine so factory uses the initialized instance
            set_cached_engine(whisper_engine)
            print()
        except Exception as e:
            print(f"⚠️  Warning: Could not initialize Whisper: {e}")
            print("   Model will be loaded on first use.\n")
    
    # Initialize cache manager first (needed for AI agent if LLM cache is enabled)
    if CACHE_ENABLED:
        try:
            initialize_cache_manager(
                enabled=CACHE_ENABLED,
                history_size=CACHE_HISTORY_SIZE,
                history_path=CACHE_HISTORY_PATH
            )
            print("Cache manager initialized.\n")
        except Exception as e:
            print(f"Warning: Could not initialize cache manager: {e}\n")
    
    # Initialize AI agent
    try:
        agent = AIAgent(cache_manager=get_cache_manager() if LLM_CACHE_ENABLED else None)
        print("AI agent initialized successfully.\n")
    except Exception as e:
        print(f"Error initializing AI agent: {e}")
        print("Please check your LLM endpoint configuration.")
        sys.exit(1)
    
    # Initialize autocomplete engine
    autocomplete_engine = None
    if AUTOCOMPLETE_ENABLED:
        try:
            from .autocomplete import AutocompleteEngine
            autocomplete_engine = AutocompleteEngine(max_suggestions=AUTOCOMPLETE_MAX_SUGGESTIONS)
            print("Auto-complete engine initialized.\n")
        except Exception as e:
            print(f"Warning: Could not initialize auto-complete engine: {e}\n")
    
    # Get installed apps once (for context)
    installed_apps = list_installed_apps()
    
    # Load presets at startup
    presets = load_presets()
    available_presets = list_presets(presets) if presets else []
    if available_presets:
        print(f"📋 Loaded {len(available_presets)} preset(s): {', '.join(available_presets)}\n")
    else:
        print("📋 No presets configured. Create ~/.voice_agent_presets.json or presets.json to use presets.\n")
    
    # Initialize command executor
    command_executor = CommandExecutor()
    
    # Start local API server for external UI clients (e.g., Electron)
    try:
        from .api_server import start_api_server
        from .config import API_PORT
        start_api_server(autocomplete_engine=autocomplete_engine, port=API_PORT)
        print(f"Local API server started on http://127.0.0.1:{API_PORT}\n")
    except Exception as e:
        print(f"Warning: Could not start local API server: {e}\n")

    # Initialize hotkey listeners
    try:
        voice_hotkey_listener = HotkeyListener(hotkey=HOTKEY)
        voice_hotkey_listener.start()
    except Exception as e:
        print(f"Error initializing voice hotkey listener: {e}")
        print("Please check your Accessibility permissions in System Settings.")
        sys.exit(1)
    
    try:
        text_hotkey_listener = HotkeyListener(hotkey=TEXT_HOTKEY)
        text_hotkey_listener.start()
    except Exception as e:
        print(f"Error initializing text hotkey listener: {e}")
        print("Please check your Accessibility permissions in System Settings.")
        sys.exit(1)
    
    # Initialize file context tracker if enabled
    file_tracker = None
    if FILE_CONTEXT_ENABLED:
        try:
            from .file_context import FileContextTracker
            cache_manager = get_cache_manager()
            file_tracker = FileContextTracker(cache_manager=cache_manager)
            print("📁 File context tracking enabled\n")
        except Exception as e:
            print(f"Warning: Failed to initialize file context tracker: {e}\n")
            file_tracker = None
    
    # Main loop - wait for hotkey, then process command
    print(f"👂 Waiting for hotkeys ({HOTKEY} for voice, {TEXT_HOTKEY} for text)...\n")
    
    while True:
        try:
            # Get current running apps for context (before waiting for hotkey)
            running_apps = list_running_apps()
            
            # Get Chrome tabs with content if Chrome is running (for tab switching context)
            chrome_tabs = None
            chrome_tabs_raw = None
            if running_apps and "Google Chrome" in running_apps:
                chrome_tabs, chrome_tabs_raw = list_chrome_tabs_with_content()
            
            # Get file context if enabled
            recent_files = None
            active_projects = None
            current_project = None
            if file_tracker:
                try:
                    recent_files = file_tracker.get_recent_files()
                    active_projects = file_tracker.get_active_projects()
                    current_project = file_tracker.get_current_project()
                except Exception as e:
                    print(f"Warning: Failed to fetch file context: {e}")
            
            # Drain any queued commands submitted via local API (e.g., Electron)
            try:
                from .command_queue import drain_commands
                queued_commands = drain_commands(max_items=10)
                for text in queued_commands:
                    should_continue = process_command(
                        text, agent, running_apps, installed_apps, chrome_tabs, chrome_tabs_raw, available_presets, command_executor,
                        recent_files=recent_files, active_projects=active_projects,
                        current_project=current_project
                    )
                    if not should_continue:
                        print("Goodbye!")
                        voice_hotkey_listener.stop()
                        text_hotkey_listener.stop()
                        if whisper_engine is not None:
                            whisper_engine._stop_persistent_stream()
                        break
            except Exception as e:
                print(f"Warning: Failed to process queued commands: {e}")

            # Check for voice hotkey press
            voice_pressed = voice_hotkey_listener.wait_for_hotkey(timeout=0.1)
            
            # Check for text hotkey press
            text_pressed = text_hotkey_listener.wait_for_hotkey(timeout=0.1)
            
            if voice_pressed:
                # Voice mode: record audio and transcribe
                print("✅ Voice hotkey pressed! Listening... (hold to speak, release to process)\n")
                
                # Build context for Whisper transcription (pre-built, no delay)
                context_parts = [
                    "macOS window control commands.",
                    "Commands: bring to view, focus, list apps, switch tab, place on monitor, move to screen, activate preset.",
                    "Monitor terms: main monitor, right monitor, left monitor, main screen, right screen, left screen."
                ]
                
                if available_presets:
                    context_parts.append(f"Available presets: {', '.join(available_presets)}.")
                
                if running_apps:
                    # Limit to first 20 apps to keep context manageable
                    apps_list = ", ".join(running_apps[:20])
                    context_parts.append(f"Running applications: {apps_list}.")
                
                context = " ".join(context_parts)
                
                # Record while hotkey is held (starts immediately, no delay)
                text = time_operation(
                    "STT (Speech Recognition)",
                    transcribe_while_held,
                    voice_hotkey_listener.is_hotkey_pressed,
                    context
                )
                
                if not text:
                    print(f"👂 Waiting for hotkeys ({HOTKEY} for voice, {TEXT_HOTKEY} for text)...\n")
                    continue
                
                # Process the command
                should_continue = process_command(
                    text, agent, running_apps, installed_apps, chrome_tabs, chrome_tabs_raw, available_presets, command_executor,
                    recent_files=recent_files, active_projects=active_projects,
                    current_project=current_project
                )
                
                if not should_continue:
                    # Quit command
                    print("Goodbye!")
                    voice_hotkey_listener.stop()
                    text_hotkey_listener.stop()
                    if whisper_engine is not None:
                        whisper_engine._stop_persistent_stream()
                    break
                
                print(f"\n👂 Waiting for hotkeys ({HOTKEY} for voice, {TEXT_HOTKEY} for text)...\n")
                
            elif text_pressed:
                # Text hotkey - trigger Electron palette
                try:
                    from .api_server import trigger_palette
                    trigger_palette()
                    print("✅ Text hotkey pressed! Electron palette triggered.\n")
                except Exception as e:
                    print(f"Warning: Could not trigger Electron palette: {e}\n")
                
        except KeyboardInterrupt:
            print("\n\nInterrupted. Goodbye!")
            voice_hotkey_listener.stop()
            text_hotkey_listener.stop()
            if whisper_engine is not None:
                whisper_engine._stop_persistent_stream()
            break
        except Exception as e:
            print(f"Error: {e}\n")
            print(f"👂 Waiting for hotkeys ({HOTKEY} for voice, {TEXT_HOTKEY} for text)...\n")


if __name__ == "__main__":
    main()

