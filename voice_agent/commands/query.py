"""Command to answer general questions using AI with available context."""

from typing import Dict, Any, List
from .base import Command


class QueryCommand(Command):
    """Command to answer questions about tabs, apps, files, projects, etc."""
    
    def can_handle(self, intent_type: str) -> bool:
        """Check if this command can handle the intent type."""
        return intent_type == "query"
    
    def produces_results(self) -> bool:
        """This command produces results to display."""
        return True
    
    def _format_tabs_for_context(self, chrome_tabs: List[Dict[str, Any]]) -> List[str]:
        lines: List[str] = []
        for tab in chrome_tabs or []:
            domain = tab.get('domain', 'N/A')
            title = tab.get('title', 'N/A')
            url = tab.get('url', '')
            index = tab.get('index', '?')
            active = " (ACTIVE)" if tab.get('is_active') else ""
            window = f" [Window {tab.get('window_index', '?')}]" if tab.get('window_index') else ""
            
            tab_str = f"Tab {index} [{domain}]{active}{window}: {title}"
            if url:
                tab_str += f" | {url}"
            lines.append(tab_str)
        return lines
    
    def execute(self, intent: Dict[str, Any]) -> bool:
        """Execute the query command."""
        question = intent.get("question", "")
        if not question or not isinstance(question, str):
            print("Error: No question provided\n")
            return False
        
        running_apps = intent.get("running_apps", []) or []
        chrome_tabs = intent.get("chrome_tabs", []) or []
        recent_files = intent.get("recent_files", []) or []
        active_projects = intent.get("active_projects", []) or []
        current_project = intent.get("current_project")
        
        # Get installed apps (best-effort) from cache if available
        installed_apps: List[str] = []
        available_presets: List[str] = []
        command_history: List[str] = []
        recent_queries: List[Dict[str, Any]] = []
        try:
            from ..cache import get_cache_manager, CacheKeys
            cache_manager = get_cache_manager()
            if cache_manager:
                installed_apps = cache_manager.get(CacheKeys.INSTALLED_APPS, []) or []
                presets_dict = cache_manager.get(CacheKeys.PRESETS, {}) or {}
                if isinstance(presets_dict, dict):
                    available_presets = list(presets_dict.keys())
                command_history = cache_manager.get_history()
                # Use new helper if available
                if hasattr(cache_manager, "get_recent_queries"):
                    recent_queries = cache_manager.get_recent_queries(max_count=10)  # type: ignore[assignment]
        except Exception:
            pass
        
        # Answer the question using AI
        from ..ai_agent import AIAgent
        agent = AIAgent()
        
        tabs_info = self._format_tabs_for_context(chrome_tabs)
        answer = agent.answer_query(
            question=question,
            running_apps=running_apps,
            installed_apps=installed_apps,
            chrome_tabs=chrome_tabs,
            recent_files=recent_files,
            active_projects=active_projects,
            current_project=current_project,
            available_presets=available_presets,
            command_history=command_history,
            recent_queries=recent_queries,
        )
        
        # Persist Q&A to recent queries (best-effort)
        try:
            from ..cache import get_cache_manager
            cm = get_cache_manager()
            if cm:
                cm.add_query_response(question, answer)
        except Exception:
            pass
        
        # Send results to Electron client via API
        try:
            from ..api_server import send_results
            # Split answer into lines for display while keeping it compact
            lines = [line.strip() for line in (answer or "").split("\n") if line.strip()]
            lines = lines if lines else [answer]
            send_results(f"Q: {question}", lines)
        except Exception:
            pass
        
        # Also print to console
        print(f"\n❓ Question: {question}")
        print("💡 Answer:")
        print(answer.strip() if isinstance(answer, str) else answer)
        print()
        return True


