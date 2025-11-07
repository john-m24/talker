"""Configuration for the voice agent."""

import os

# Local LLM endpoint configuration
LLM_ENDPOINT = os.getenv("VOICE_AGENT_LLM_ENDPOINT", "http://192.168.1.198:10000/v1")
LLM_MODEL = os.getenv("VOICE_AGENT_LLM_MODEL", "qwen-30b")
