"""AI agent for parsing voice commands into structured intents."""

import json
import openai
from typing import Dict, List, Optional
from .config import LLM_ENDPOINT, LLM_MODEL


class AIAgent:
    """AI agent that uses OpenAI-compatible API to parse user commands."""
    
    def __init__(self, endpoint: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize the AI agent.
        
        Args:
            endpoint: LLM endpoint URL (defaults to config value)
            model: Model name (defaults to config value)
        """
        self.endpoint = endpoint or LLM_ENDPOINT
        self.model = model or LLM_MODEL
        
        # Initialize OpenAI client with custom endpoint
        self.client = openai.OpenAI(
            base_url=self.endpoint,
            api_key="not-needed"  # Local endpoints don't require real API keys
        )
    
    def parse_intent(
        self, 
        text: str, 
        running_apps: List[str], 
        installed_apps: Optional[List[str]] = None
    ) -> Dict[str, str]:
        """
        Parse user command text into a structured intent.
        
        Args:
            text: User's command text
            running_apps: List of currently running applications
            installed_apps: Optional list of installed applications
            
        Returns:
            Dictionary with 'type' and optionally 'app_name' keys
            Example: {"type": "focus_app", "app_name": "Docker Desktop"}
        """
        # Build context for the AI
        context_parts = [
            "You are a macOS window control assistant. Parse the user's command and return a JSON response.",
            "",
            "Available commands:",
            "- 'list_apps' or 'list applications' - list running applications",
            "- 'focus_app' - bring an application to the front",
            "",
            f"Currently running applications: {', '.join(running_apps) if running_apps else 'None'}",
        ]
        
        if installed_apps:
            # Limit to first 50 apps to avoid token limits
            apps_preview = installed_apps[:50]
            context_parts.append(
                f"Some installed applications (for reference): {', '.join(apps_preview)}"
            )
        
        context_parts.extend([
            "",
            "User command:",
            text,
            "",
            "Return a JSON object with:",
            "- 'type': either 'list_apps' or 'focus_app'",
            "- 'app_name': (only for focus_app) the exact application name from the running apps list",
            "",
            "If the user wants to focus an app, match their fuzzy input to the exact app name from the running apps list.",
            "If no matching app is found in running apps, use the closest match from installed apps.",
            "If the command is unclear, default to 'list_apps'.",
        ])
        
        prompt = "\n".join(context_parts)
        
        try:
            # Try with response_format first (for models that support JSON mode)
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a helpful assistant that parses commands into structured JSON. Always return valid JSON only."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.1,  # Low temperature for consistent parsing
                    response_format={"type": "json_object"}  # Request JSON response
                )
            except Exception as format_error:
                # Fallback if response_format is not supported
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a helpful assistant that parses commands into structured JSON. Always return valid JSON only, wrapped in a code block or as plain JSON."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.1
                )
            
            # Extract JSON from response
            content = response.choices[0].message.content.strip()
            
            # Try to extract JSON from code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            # Parse JSON
            try:
                intent = json.loads(content)
                
                # Validate structure
                if "type" not in intent:
                    return {"type": "list_apps"}
                
                return intent
            except json.JSONDecodeError as e:
                print(f"Error parsing AI response as JSON: {e}")
                print(f"Response was: {content}")
                return {"type": "list_apps"}
                
        except Exception as e:
            print(f"Error calling AI agent: {e}")
            return {"type": "list_apps"}

