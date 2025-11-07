"""Command to activate a preset window layout."""

from typing import Dict, Any
from .base import Command
from ..window_control import place_app_on_monitor, list_running_apps
from ..presets import get_preset, find_matching_presets, load_presets, list_presets


class ActivatePresetCommand(Command):
    """Command to activate a preset window layout."""
    
    def can_handle(self, intent_type: str) -> bool:
        """Check if this command can handle the intent type."""
        return intent_type == "activate_preset"
    
    def execute(self, intent: Dict[str, Any]) -> bool:
        """Execute the activate preset command."""
        preset_name = intent.get("preset_name")
        
        if not preset_name:
            print("Error: Missing preset name in intent\n")
            return False
        
        # Load presets
        presets = load_presets()
        
        # Try to get the preset (handles case-insensitive and partial matching)
        preset = get_preset(preset_name, presets)
        
        if preset is None:
            # Check if there are multiple matches (ambiguity)
            matches = find_matching_presets(preset_name, presets)
            if matches:
                print(f"Error: Multiple presets match '{preset_name}': {', '.join(matches)}\n")
            else:
                available = list_presets(presets) if presets else []
                if available:
                    print(f"Error: Preset '{preset_name}' not found. Available presets: {', '.join(available)}\n")
                else:
                    print(f"Error: Preset '{preset_name}' not found. No presets are configured.\n")
            return False
        
        # Get the apps list from the preset
        apps = preset.get("apps", [])
        if not apps:
            print(f"Error: Preset '{preset_name}' has no apps configured\n")
            return False
        
        print(f"Activating preset '{preset_name}'...")
        print(f"  Configuring {len(apps)} app(s)\n")
        
        # Get running apps to provide better feedback
        running_apps = list_running_apps()
        
        # Execute each app placement
        all_succeeded = True
        for i, app_config in enumerate(apps, 1):
            app_name = app_config.get("app_name")
            monitor = app_config.get("monitor")
            maximize = app_config.get("maximize", False)
            
            if not app_name or not monitor:
                print(f"  ⚠️  Skipping invalid app config {i}: missing app_name or monitor")
                all_succeeded = False
                continue
            
            # Check if app is running to provide better feedback
            is_running = app_name in running_apps
            
            # Place the app (will launch if not running)
            monitor_display = monitor.replace("_", " ").title()
            maximize_text = " and maximizing" if maximize else ""
            
            if is_running:
                print(f"  [{i}/{len(apps)}] Placing '{app_name}' on {monitor_display} monitor{maximize_text}...")
            else:
                print(f"  [{i}/{len(apps)}] Opening '{app_name}' and placing on {monitor_display} monitor{maximize_text} (app is not currently running)...")
            
            success = place_app_on_monitor(app_name, monitor, maximize=maximize)
            if success:
                print(f"    ✓ Successfully placed '{app_name}' on {monitor_display} monitor")
            else:
                print(f"    ✗ Failed to place '{app_name}' on {monitor_display} monitor")
                all_succeeded = False
        
        if all_succeeded:
            print(f"\n✓ Successfully activated preset '{preset_name}'\n")
        else:
            print(f"\n⚠️  Preset '{preset_name}' activated with some errors\n")
        
        return all_succeeded

