"""Global hotkey listener for triggering voice commands."""

import threading
from queue import Queue
from typing import Optional
from pynput import keyboard


class HotkeyListener:
    """Global hotkey listener that works from any application."""
    
    def __init__(self, hotkey: Optional[str] = None):
        """
        Initialize hotkey listener.
        
        Args:
            hotkey: Hotkey combination (e.g., 'ctrl+alt' or 'cmd+shift+v')
                   Default: 'ctrl+alt'
        """
        self.hotkey = hotkey or 'ctrl+alt'
        self.event_queue = Queue()
        self.listener = None
        self.running = False
        self.pressed_modifiers = set()
        self.is_pressed = False  # Track if hotkey is currently pressed
        
    def _on_hotkey_press(self):
        """Called when hotkey is pressed."""
        if not self.is_pressed:
            self.is_pressed = True
            self.event_queue.put('hotkey_pressed')
        return False  # Don't suppress the event
    
    def _on_hotkey_release(self):
        """Called when hotkey is released."""
        if self.is_pressed:
            self.is_pressed = False
            self.event_queue.put('hotkey_released')
    
    def start(self):
        """Start listening for hotkey in background thread."""
        if self.running:
            return
        
        self.running = True
        
        # Parse hotkey string into pynput format
        pynput_hotkey = self._parse_hotkey(self.hotkey)
        
        # Check if it's a modifier-only combination (no regular key)
        parts = self.hotkey.lower().split('+')
        has_regular_key = False
        regular_keys = {'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12',
                       'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z',
                       '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'space', 'enter', 'tab', 'esc'}
        
        for part in parts:
            if part.strip() in regular_keys:
                has_regular_key = True
                break
        
        # Create hotkey listener
        try:
            if has_regular_key:
                # Use GlobalHotKeys for combinations with regular keys
                self.listener = keyboard.GlobalHotKeys({
                    pynput_hotkey: self._on_hotkey_press
                })
            else:
                # For modifier-only combinations, use a regular Listener
                # Track which modifiers are currently pressed
                self.pressed_modifiers = set()
                
                def on_press(key):
                    try:
                        # Track modifier keys
                        if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
                            self.pressed_modifiers.add('ctrl')
                        elif key == keyboard.Key.alt_l or key == keyboard.Key.alt_r:
                            self.pressed_modifiers.add('alt')
                        elif key == keyboard.Key.cmd_l or key == keyboard.Key.cmd_r:
                            self.pressed_modifiers.add('cmd')
                        elif key == keyboard.Key.shift_l or key == keyboard.Key.shift_r:
                            self.pressed_modifiers.add('shift')
                        
                        # Check if all required modifiers are pressed
                        required_modifiers = set()
                        for part in parts:
                            part = part.strip()
                            if part in ['ctrl', 'control']:
                                required_modifiers.add('ctrl')
                            elif part in ['alt', 'option']:
                                required_modifiers.add('alt')
                            elif part == 'cmd':
                                required_modifiers.add('cmd')
                            elif part == 'shift':
                                required_modifiers.add('shift')
                        
                        if required_modifiers.issubset(self.pressed_modifiers):
                            self._on_hotkey_press()
                    except:
                        pass
                
                def on_release(key):
                    try:
                        # Remove modifier from set when released
                        if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
                            self.pressed_modifiers.discard('ctrl')
                        elif key == keyboard.Key.alt_l or key == keyboard.Key.alt_r:
                            self.pressed_modifiers.discard('alt')
                        elif key == keyboard.Key.cmd_l or key == keyboard.Key.cmd_r:
                            self.pressed_modifiers.discard('cmd')
                        elif key == keyboard.Key.shift_l or key == keyboard.Key.shift_r:
                            self.pressed_modifiers.discard('shift')
                        
                        # Check if all required modifiers are still pressed
                        required_modifiers = set()
                        for part in parts:
                            part = part.strip()
                            if part in ['ctrl', 'control']:
                                required_modifiers.add('ctrl')
                            elif part in ['alt', 'option']:
                                required_modifiers.add('alt')
                            elif part == 'cmd':
                                required_modifiers.add('cmd')
                            elif part == 'shift':
                                required_modifiers.add('shift')
                        
                        # If modifiers are no longer all pressed, release hotkey
                        if not required_modifiers.issubset(self.pressed_modifiers):
                            self._on_hotkey_release()
                    except:
                        pass
                
                self.listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        except Exception as e:
            raise RuntimeError(
                f"Failed to register hotkey '{self.hotkey}': {e}\n"
                "On macOS, you may need to grant Accessibility permissions:\n"
                "System Settings > Privacy & Security > Accessibility > Add Terminal"
            )
        
        # Start listener in background thread
        def run_listener():
            try:
                self.listener.start()
                self.listener.join()
            except KeyError as e:
                # Suppress KeyError from pynput's accessibility check (e.g., 'AXIsProcessTrusted')
                # This is a known issue with pynput on macOS - the listener may still work
                if 'AXIsProcessTrusted' in str(e):
                    # This is expected if accessibility permissions aren't granted
                    # The listener will still work, but may have limited functionality
                    pass
                else:
                    print(f"Error in hotkey listener: {e}")
            except Exception as e:
                print(f"Error in hotkey listener: {e}")
        
        thread = threading.Thread(target=run_listener, daemon=True)
        thread.start()
        
        print(f"⌨️  Global hotkey registered: {self.hotkey}")
        print("   Press the hotkey from any window to activate voice command.\n")
    
    def stop(self):
        """Stop listening for hotkey."""
        if self.listener:
            try:
                self.listener.stop()
            except:
                pass
        self.running = False
    
    def wait_for_hotkey(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for hotkey press.
        
        Args:
            timeout: Maximum seconds to wait (None = wait forever)
            
        Returns:
            True if hotkey was pressed, False if timeout
        """
        try:
            event = self.event_queue.get(timeout=timeout)
            return event == 'hotkey_pressed'
        except:
            return False
    
    def wait_for_hotkey_release(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for hotkey release (after it's been pressed).
        
        Args:
            timeout: Maximum seconds to wait (None = wait forever)
            
        Returns:
            True if hotkey was released, False if timeout
        """
        try:
            event = self.event_queue.get(timeout=timeout)
            return event == 'hotkey_released'
        except:
            return False
    
    def is_hotkey_pressed(self) -> bool:
        """
        Check if hotkey is currently pressed.
        
        Returns:
            True if hotkey is currently pressed, False otherwise
        """
        return self.is_pressed
    
    def _parse_hotkey(self, hotkey_str: str) -> str:
        """
        Parse hotkey string into pynput format.
        
        Examples:
            'ctrl+alt' -> '<ctrl>+<alt>'
            'cmd+shift+v' -> '<cmd>+<shift>+v'
            'f8' -> 'f8'
        """
        parts = hotkey_str.lower().split('+')
        parsed = []
        
        # Map common key names to pynput format
        key_map = {
            'cmd': '<cmd>',
            'ctrl': '<ctrl>',
            'control': '<ctrl>',
            'alt': '<alt>',
            'option': '<alt>',
            'shift': '<shift>',
            'space': '<space>',
        }
        
        for part in parts:
            part = part.strip()
            # Use mapped key if available, otherwise use as-is
            parsed.append(key_map.get(part, part))
        
        return '+'.join(parsed)

