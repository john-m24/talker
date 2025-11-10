"""Predictive caching system for pre-computing likely commands."""

import time
import threading
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple, Callable, Any
from datetime import datetime, timedelta
from .cache import get_cache_manager, CacheKeys
from .pattern_matcher import PatternMatcher
from .fuzzy_matcher import match_app_name, match_preset_name


class CommandPatternAnalyzer:
    """Analyzes command history for patterns, sequences, and frequency."""
    
    def __init__(self, cache_manager=None):
        """
        Initialize the command pattern analyzer.
        
        Args:
            cache_manager: CacheManager instance for storing analysis results
        """
        self.cache_manager = cache_manager or get_cache_manager()
        self._frequency: Dict[str, int] = {}
        self._sequences: Dict[str, List[str]] = defaultdict(list)
        self._time_patterns: Dict[int, List[str]] = defaultdict(list)  # hour -> commands
        self._context_patterns: Dict[str, List[str]] = defaultdict(list)  # context -> commands
        
    def analyze_frequency(self, history: List[str]) -> Dict[str, int]:
        """
        Count command frequency.
        
        Args:
            history: List of command texts
            
        Returns:
            Dictionary mapping command text to frequency count
        """
        self._frequency = Counter(history)
        
        # Store in cache for fast access
        if self.cache_manager:
            self.cache_manager.set(CacheKeys.COMMAND_FREQUENCY, dict(self._frequency), ttl=0)
        
        return dict(self._frequency)
    
    def analyze_sequences(self, history: List[str]) -> Dict[str, List[str]]:
        """
        Find common command sequences (after command A, often comes command B).
        
        Args:
            history: List of command texts
            
        Returns:
            Dictionary mapping command to list of likely next commands
        """
        self._sequences = defaultdict(list)
        
        # Analyze sequences (command A -> command B)
        for i in range(len(history) - 1):
            current = history[i]
            next_cmd = history[i + 1]
            
            if next_cmd not in self._sequences[current]:
                self._sequences[current].append(next_cmd)
        
        # Store in cache for fast access
        if self.cache_manager:
            self.cache_manager.set(CacheKeys.COMMAND_SEQUENCES, dict(self._sequences), ttl=0)
        
        return dict(self._sequences)
    
    def analyze_time_patterns(self, history: List[Dict]) -> Dict[int, List[str]]:
        """
        Find time-based patterns (user often does X at 9am).
        
        Args:
            history: List of command dicts with 'command' and 'timestamp' keys
            
        Returns:
            Dictionary mapping hour (0-23) to list of common commands at that hour
        """
        self._time_patterns = defaultdict(list)
        
        for entry in history:
            if isinstance(entry, dict):
                command = entry.get('command', '')
                timestamp = entry.get('timestamp', time.time())
            else:
                # Fallback: treat as string command
                command = str(entry)
                timestamp = time.time()
            
            hour = datetime.fromtimestamp(timestamp).hour
            
            if command and command not in self._time_patterns[hour]:
                self._time_patterns[hour].append(command)
        
        return dict(self._time_patterns)
    
    def analyze_context_patterns(self, history: List[Dict]) -> Dict[str, List[str]]:
        """
        Find context-based patterns (if tab X is open, likely to switch to it).
        
        Args:
            history: List of command dicts with 'command' and 'context' keys
            
        Returns:
            Dictionary mapping context key to list of commands in that context
        """
        self._context_patterns = defaultdict(list)
        
        for entry in history:
            if isinstance(entry, dict):
                command = entry.get('command', '')
                context = entry.get('context', {})
            else:
                # Fallback: treat as string command
                command = str(entry)
                context = {}
            
            # Extract context keys (e.g., "tab:github.com", "app:chrome")
            for key, value in context.items():
                context_key = f"{key}:{value}"
                if command and command not in self._context_patterns[context_key]:
                    self._context_patterns[context_key].append(command)
        
        return dict(self._context_patterns)
    
    def get_top_commands(self, n: int = 10) -> List[str]:
        """
        Return top N most frequent commands.
        
        Args:
            n: Number of top commands to return
            
        Returns:
            List of top N command texts
        """
        if not self._frequency:
            # Try to load from cache
            if self.cache_manager:
                cached = self.cache_manager.get(CacheKeys.COMMAND_FREQUENCY)
                if cached:
                    self._frequency = cached
        
        if not self._frequency:
            return []
        
        # Sort by frequency (descending) and return top N
        sorted_commands = sorted(self._frequency.items(), key=lambda x: x[1], reverse=True)
        return [cmd for cmd, _ in sorted_commands[:n]]
    
    def get_next_likely_commands(self, current_command: str) -> List[str]:
        """
        Return likely next commands based on sequences.
        
        Args:
            current_command: Current command text
            
        Returns:
            List of likely next commands
        """
        if not self._sequences:
            # Try to load from cache
            if self.cache_manager:
                cached = self.cache_manager.get(CacheKeys.COMMAND_SEQUENCES)
                if cached:
                    self._sequences = defaultdict(list, cached)
        
        return self._sequences.get(current_command, [])
    
    def update_incremental(self, command: str, context: Optional[Dict] = None):
        """
        Update analysis incrementally with a new command.
        
        Args:
            command: New command text
            context: Optional context dict
        """
        # Update frequency
        self._frequency[command] = self._frequency.get(command, 0) + 1
        
        # Update cache
        if self.cache_manager:
            self.cache_manager.set(CacheKeys.COMMAND_FREQUENCY, dict(self._frequency), ttl=0)
        
        # Note: Sequences and context patterns require full history, so we'll update those
        # when we have access to full history. For now, just update frequency.


class BackgroundContextUpdater:
    """Continuously updates context (apps, tabs) in background thread."""
    
    def __init__(self, update_interval: float = 2.0, on_context_change: Optional[Callable] = None):
        """
        Initialize the background context updater.
        
        Args:
            update_interval: How often to update context in seconds
            on_context_change: Optional callback when context changes significantly
        """
        self.update_interval = update_interval
        self.on_context_change = on_context_change
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.current_context: Dict[str, Any] = {
            'running_apps': [],
            'chrome_tabs': [],
            'available_presets': []
        }
        self._lock = threading.Lock()
    
    def start(self):
        """Start background thread that continuously updates context."""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._update_loop, daemon=True)
        self.thread.start()
    
    def stop(self):
        """Stop background thread gracefully."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
    
    def _update_loop(self):
        """Background loop that continuously updates context."""
        while self.running:
            try:
                self.update_context()
                time.sleep(self.update_interval)
            except Exception as e:
                print(f"Error in background context updater: {e}")
                time.sleep(self.update_interval)
    
    def update_context(self):
        """Fetch current context (apps, tabs, presets, files) and update cache."""
        from .window_control import list_running_apps, list_installed_apps
        from .tab_control import list_chrome_tabs_with_content
        from .presets import load_presets, list_presets
        from .config import FILE_CONTEXT_ENABLED
        
        # Fetch current context
        running_apps = list_running_apps()
        installed_apps = list_installed_apps()
        
        chrome_tabs = None
        chrome_tabs_raw = None
        if running_apps and "Google Chrome" in running_apps:
            chrome_tabs, chrome_tabs_raw = list_chrome_tabs_with_content()
        
        presets = load_presets()
        available_presets = list_presets(presets) if presets else []
        
        # Add file context if enabled
        recent_files = []
        active_projects = []
        current_project = None
        if FILE_CONTEXT_ENABLED:
            try:
                from .file_context import FileContextTracker
                from .cache import get_cache_manager
                file_tracker = FileContextTracker(cache_manager=get_cache_manager())
                recent_files = file_tracker.get_recent_files()
                active_projects = file_tracker.get_active_projects()
                current_project = file_tracker.get_current_project()
            except Exception as e:
                print(f"Warning: Failed to fetch file context: {e}")
        
        # Check if context changed significantly
        old_context = self.current_context.copy()
        new_context = {
            'running_apps': running_apps,
            'installed_apps': installed_apps,
            'chrome_tabs': chrome_tabs,
            'chrome_tabs_raw': chrome_tabs_raw,
            'available_presets': available_presets,
            'recent_files': recent_files,
            'active_projects': active_projects,
            'current_project': current_project
        }
        
        with self._lock:
            self.current_context = new_context
        
        # Check for significant changes
        if self._context_changed_significantly(old_context, new_context):
            if self.on_context_change:
                self.on_context_change(old_context, new_context)
    
    def _context_changed_significantly(self, old: Dict, new: Dict) -> bool:
        """Check if context changed significantly."""
        # Check if apps changed
        if set(old.get('running_apps', [])) != set(new.get('running_apps', [])):
            return True
        
        # Check if tabs changed (count or content)
        old_tabs = old.get('chrome_tabs', [])
        new_tabs = new.get('chrome_tabs', [])
        if len(old_tabs) != len(new_tabs):
            return True
        
        # Check if tab indices changed
        old_indices = {tab.get('index') for tab in old_tabs if isinstance(tab, dict)}
        new_indices = {tab.get('index') for tab in new_tabs if isinstance(tab, dict)}
        if old_indices != new_indices:
            return True
        
        # Check if presets changed
        if set(old.get('available_presets', [])) != set(new.get('available_presets', [])):
            return True
        
        # Check if current project changed
        old_project = old.get('current_project')
        new_project = new.get('current_project')
        if old_project != new_project:
            # Check if project path changed
            if old_project and new_project:
                if old_project.get('path') != new_project.get('path'):
                    return True
            elif old_project or new_project:
                return True
        
        # Check if recent files changed significantly (top 5)
        old_files = old.get('recent_files', [])[:5]
        new_files = new.get('recent_files', [])[:5]
        if len(old_files) != len(new_files):
            return True
        old_file_paths = {f.get('path') for f in old_files if isinstance(f, dict)}
        new_file_paths = {f.get('path') for f in new_files if isinstance(f, dict)}
        if old_file_paths != new_file_paths:
            return True
        
        return False
    
    def get_current_context(self) -> Dict[str, Any]:
        """Return current context snapshot."""
        with self._lock:
            return self.current_context.copy()


class NonAIPrecomputer:
    """Pre-computes commands using pattern matching and keyword matching."""
    
    def __init__(self, pattern_matcher: PatternMatcher):
        """
        Initialize the non-AI pre-computer.
        
        Args:
            pattern_matcher: PatternMatcher instance for pattern matching
        """
        self.pattern_matcher = pattern_matcher
    
    def precompute_for_apps(self, apps: List[str], context: Dict) -> Dict[str, Dict]:
        """
        Pre-compute commands for each app using pattern matching.
        
        Args:
            apps: List of app names
            context: Context dict with running_apps, installed_apps, etc.
            
        Returns:
            Dictionary mapping command text to parsed intent
        """
        results = {}
        running_apps = context.get('running_apps', [])
        installed_apps = context.get('installed_apps', [])
        available_presets = context.get('available_presets', [])
        
        for app in apps:
            # Generate command variations
            variations = self._generate_command_variations(app, 'app')
            
            for cmd in variations:
                # Pre-compute using pattern matcher (fast, no LLM)
                result = self.pattern_matcher.match_pattern(
                    cmd,
                    running_apps,
                    installed_apps,
                    available_presets
                )
                if result:
                    results[cmd] = result
        
        return results
    
    def precompute_for_tabs(self, tabs: List[Dict], context: Dict) -> Dict[str, Dict]:
        """
        Pre-compute commands for each tab using pattern matching and keyword matching.
        
        Args:
            tabs: List of tab dicts with 'index', 'domain', 'title', 'url' keys
            context: Context dict with running_apps, installed_apps, etc.
            
        Returns:
            Dictionary mapping command text to parsed intent
        """
        results = {}
        running_apps = context.get('running_apps', [])
        installed_apps = context.get('installed_apps', [])
        available_presets = context.get('available_presets', [])
        
        for tab in tabs:
            domain = tab.get('domain', '')
            title = tab.get('title', '')
            index = tab.get('index', 0)
            
            # Extract keywords from domain and title
            domain_keywords = self._extract_keywords(domain)
            title_keywords = self._extract_keywords(title)
            
            # Generate command variations
            variations = []
            
            # Domain-based commands
            for keyword in domain_keywords:
                variations.extend([
                    f"switch to {keyword}",
                    f"go to {keyword}",
                    f"open {keyword}",
                    f"show {keyword}",
                ])
            
            # Title-based commands
            for keyword in title_keywords[:3]:  # Limit to top 3 keywords
                variations.extend([
                    f"switch to {keyword}",
                    f"go to {keyword}",
                ])
            
            # Numeric commands
            if index > 0:
                variations.extend([
                    f"switch to tab {index}",
                    f"tab {index}",
                    f"close tab {index}",
                ])
            
            # Pre-compute using pattern matcher
            for cmd in variations:
                result = self.pattern_matcher.match_pattern(
                    cmd,
                    running_apps,
                    installed_apps,
                    available_presets
                )
                if result:
                    results[cmd] = result
        
        return results
    
    def precompute_for_presets(self, presets: List[str], context: Dict) -> Dict[str, Dict]:
        """
        Pre-compute commands for each preset using pattern matching.
        
        Args:
            presets: List of preset names
            context: Context dict with available_presets, etc.
            
        Returns:
            Dictionary mapping command text to parsed intent
        """
        results = {}
        running_apps = context.get('running_apps', [])
        installed_apps = context.get('installed_apps', [])
        available_presets = context.get('available_presets', [])
        
        for preset in presets:
            # Generate command variations
            variations = self._generate_command_variations(preset, 'preset')
            
            for cmd in variations:
                # Pre-compute using pattern matcher
                result = self.pattern_matcher.match_pattern(
                    cmd,
                    running_apps,
                    installed_apps,
                    available_presets
                )
                if result:
                    results[cmd] = result
        
        return results
    
    def _extract_keywords(self, text: str) -> List[str]:
        """
        Extract keywords from domain/title for matching.
        
        Args:
            text: Text to extract keywords from (e.g., "github.com", "Python Tutorial")
            
        Returns:
            List of keywords
        """
        if not text:
            return []
        
        # Remove common TLDs and separators
        text = text.lower()
        text = text.replace('.com', '').replace('.org', '').replace('.net', '')
        text = text.replace('.io', '').replace('.dev', '').replace('.co', '')
        text = text.replace('www.', '').replace('https://', '').replace('http://', '')
        
        # Split by common separators
        keywords = []
        for separator in [' ', '-', '_', '/']:
            if separator in text:
                parts = text.split(separator)
                keywords.extend([p.strip() for p in parts if p.strip()])
                break
        else:
            # No separator found, use whole text
            keywords.append(text)
        
        # Filter out very short keywords
        keywords = [k for k in keywords if len(k) >= 2]
        
        return keywords[:5]  # Limit to top 5 keywords
    
    def _generate_command_variations(self, entity: str, entity_type: str) -> List[str]:
        """
        Generate all command variations for an entity.
        
        Args:
            entity: Entity name (app, preset, etc.)
            entity_type: Type of entity ('app', 'preset')
            
        Returns:
            List of command variations
        """
        variations = []
        
        if entity_type == 'app':
            variations = [
                f"focus {entity}",
                f"open {entity}",
                f"bring {entity} to view",
                f"show {entity}",
                entity,  # Implicit focus
            ]
        elif entity_type == 'preset':
            variations = [
                f"activate {entity}",
                f"load {entity}",
                f"switch to {entity}",
                entity,  # Implicit preset activation
            ]
        
        return variations


class AIPrecomputer:
    """Pre-computes commands using AI (aggressive pre-computation for best UX)."""
    
    def __init__(self, agent, thread_pool_size: int = 5):
        """
        Initialize the AI pre-computer.
        
        Args:
            agent: AIAgent instance for LLM parsing
            thread_pool_size: Number of threads for parallel pre-computation
        """
        self.agent = agent
        self.thread_pool_size = thread_pool_size
        self.executor = ThreadPoolExecutor(max_workers=thread_pool_size)
    
    def precompute_commands(self, priority_commands: List[str], context: Dict) -> Dict[str, Dict]:
        """
        Pre-compute ALL priority commands using AI (aggressive pre-computation for best UX).
        
        Args:
            priority_commands: List of commands to pre-compute
            context: Context dict with running_apps, installed_apps, chrome_tabs, etc.
            
        Returns:
            Dictionary mapping command text to parsed intent
        """
        results = {}
        
        # Pre-compute in parallel using thread pool
        futures = {}
        for cmd in priority_commands:
            future = self.executor.submit(self._precompute_single, cmd, context)
            futures[future] = cmd
        
        # Collect results as they complete
        for future in as_completed(futures):
            cmd = futures[future]
            try:
                result = future.result()
                if result:
                    results[cmd] = result
            except Exception as e:
                print(f"Error pre-computing command '{cmd}': {e}")
        
        return results
    
    def precompute_for_tabs(self, tabs: List[Dict], context: Dict) -> Dict[str, Dict]:
        """
        Pre-compute commands for each tab using AI (aggressive pre-computation).
        
        Args:
            tabs: List of tab dicts with 'index', 'domain', 'title', 'url', 'content_summary' keys
            context: Context dict with running_apps, installed_apps, chrome_tabs, etc.
            
        Returns:
            Dictionary mapping command text to parsed intent
        """
        results = {}
        
        # Generate natural language variations for each tab
        variations = []
        for tab in tabs:
            domain = tab.get('domain', '')
            title = tab.get('title', '')
            index = tab.get('index', 0)
            
            # Generate all natural language variations
            tab_variations = self._generate_natural_variations(domain, title, index)
            variations.extend(tab_variations)
        
        # Pre-compute all variations in parallel
        futures = {}
        for cmd in variations:
            future = self.executor.submit(self._precompute_single, cmd, context)
            futures[future] = cmd
        
        # Collect results
        for future in as_completed(futures):
            cmd = futures[future]
            try:
                result = future.result()
                if result:
                    results[cmd] = result
            except Exception as e:
                print(f"Error pre-computing tab command '{cmd}': {e}")
        
        return results
    
    def precompute_for_apps(self, apps: List[str], context: Dict) -> Dict[str, Dict]:
        """
        Pre-compute commands for each app using AI (aggressive pre-computation).
        
        Args:
            apps: List of app names
            context: Context dict with running_apps, installed_apps, etc.
            
        Returns:
            Dictionary mapping command text to parsed intent
        """
        results = {}
        
        # Generate natural language variations for each app
        variations = []
        for app in apps:
            app_variations = self._generate_natural_variations(app, None, None, entity_type='app')
            variations.extend(app_variations)
        
        # Pre-compute all variations in parallel
        futures = {}
        for cmd in variations:
            future = self.executor.submit(self._precompute_single, cmd, context)
            futures[future] = cmd
        
        # Collect results
        for future in as_completed(futures):
            cmd = futures[future]
            try:
                result = future.result()
                if result:
                    results[cmd] = result
            except Exception as e:
                print(f"Error pre-computing app command '{cmd}': {e}")
        
        return results
    
    def precompute_common_commands(self, context: Dict) -> Dict[str, Dict]:
        """
        Pre-compute common command patterns from history using AI.
        
        Args:
            context: Context dict with running_apps, installed_apps, etc.
            
        Returns:
            Dictionary mapping command text to parsed intent
        """
        # This will be populated based on command history
        # For now, return empty dict - will be enhanced with history analysis
        return {}
    
    def _precompute_single(self, command: str, context: Dict) -> Optional[Dict]:
        """
        Pre-compute a single command using AI.
        
        Args:
            command: Command text to pre-compute
            context: Context dict
            
        Returns:
            Parsed intent dict or None if failed
        """
        try:
            result = self.agent.parse_intent(
                command,
                context.get('running_apps', []),
                context.get('installed_apps', []),
                chrome_tabs=context.get('chrome_tabs'),
                chrome_tabs_raw=context.get('chrome_tabs_raw'),
                available_presets=context.get('available_presets')
            )
            return result
        except Exception as e:
            print(f"Error pre-computing command '{command}': {e}")
            return None
    
    def _generate_natural_variations(self, entity: str, title: Optional[str] = None, index: Optional[int] = None, entity_type: str = 'tab') -> List[str]:
        """
        Generate ALL natural language variations for an entity.
        
        Args:
            entity: Entity name (domain, app, etc.)
            title: Optional title for tabs
            index: Optional index for tabs
            entity_type: Type of entity ('tab', 'app')
            
        Returns:
            List of natural language command variations
        """
        variations = []
        
        if entity_type == 'tab':
            # Domain-based variations
            variations.extend([
                f"switch to {entity}",
                f"go to {entity}",
                f"open {entity}",
                f"show {entity}",
                entity,  # Implicit focus
            ])
            
            # Title-based variations (if available)
            if title:
                title_keywords = self._extract_keywords(title)
                for keyword in title_keywords[:3]:
                    variations.extend([
                        f"switch to {keyword}",
                        f"go to {keyword}",
                    ])
            
            # Numeric variations (if available)
            if index and index > 0:
                variations.extend([
                    f"switch to tab {index}",
                    f"tab {index}",
                    f"close tab {index}",
                ])
        
        elif entity_type == 'app':
            variations.extend([
                f"focus {entity}",
                f"bring {entity} to view",
                f"show {entity}",
                f"open {entity}",
                f"show me {entity}",
                f"bring up {entity}",
                entity,  # Implicit focus
            ])
        
        return variations
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text for matching."""
        if not text:
            return []
        
        # Simple keyword extraction
        text = text.lower()
        # Split by common separators
        keywords = []
        for separator in [' ', '-', '_', '/']:
            if separator in text:
                parts = text.split(separator)
                keywords.extend([p.strip() for p in parts if p.strip()])
                break
        else:
            keywords.append(text)
        
        # Filter out very short keywords
        keywords = [k for k in keywords if len(k) >= 2]
        
        return keywords[:5]  # Limit to top 5 keywords
    
    def shutdown(self):
        """Shutdown thread pool executor."""
        self.executor.shutdown(wait=True)


class CommandPrioritizer:
    """Determines which commands to pre-compute based on likelihood (UX-focused)."""
    
    def __init__(self, pattern_analyzer: CommandPatternAnalyzer):
        """
        Initialize the command prioritizer.
        
        Args:
            pattern_analyzer: CommandPatternAnalyzer instance for pattern analysis
        """
        self.pattern_analyzer = pattern_analyzer
    
    def get_priority_commands(self, context: Dict, max_commands: int = 100) -> List[Tuple[str, float]]:
        """
        Return commands to pre-compute, ordered by priority (likelihood score).
        
        Args:
            context: Context dict with running_apps, chrome_tabs, available_presets, etc.
            max_commands: Maximum number of commands to return
            
        Returns:
            List of (command, priority_score) tuples, ordered by priority
        """
        commands_with_priority = []
        
        # 1. Context-based commands (highest priority - what's currently available)
        context_commands = self._get_context_based_commands(context)
        for cmd in context_commands:
            priority = self.calculate_priority(cmd, context)
            commands_with_priority.append((cmd, priority))
        
        # 2. History-based commands (most common commands)
        history_commands = self._get_history_based_commands()
        for cmd in history_commands:
            if cmd not in [c[0] for c in commands_with_priority]:
                priority = self.calculate_priority(cmd, context)
                commands_with_priority.append((cmd, priority))
        
        # 3. Sequence-based commands (likely next commands)
        sequence_commands = self._get_sequence_based_commands()
        for cmd in sequence_commands:
            if cmd not in [c[0] for c in commands_with_priority]:
                priority = self.calculate_priority(cmd, context)
                commands_with_priority.append((cmd, priority))
        
        # 4. Time-based commands (time of day patterns)
        time_commands = self._get_time_based_commands()
        for cmd in time_commands:
            if cmd not in [c[0] for c in commands_with_priority]:
                priority = self.calculate_priority(cmd, context)
                commands_with_priority.append((cmd, priority))
        
        # Sort by priority (descending) and return top N
        commands_with_priority.sort(key=lambda x: x[1], reverse=True)
        return commands_with_priority[:max_commands]
    
    def calculate_priority(self, command: str, context: Dict) -> float:
        """
        Calculate priority score (0.0 to 1.0) based on all factors.
        
        Args:
            command: Command text
            context: Context dict
            
        Returns:
            Priority score (higher = more likely to be used)
        """
        score = 0.0
        
        # 1. Context availability (highest weight - 0.4)
        if self._is_context_available(command, context):
            score += 0.4
        
        # 2. Frequency in history (0.3)
        frequency = self.pattern_analyzer._frequency.get(command, 0)
        if frequency > 0:
            max_freq = max(self.pattern_analyzer._frequency.values()) if self.pattern_analyzer._frequency else 1
            score += 0.3 * (frequency / max_freq)
        
        # 3. Recent usage (0.2)
        # Check if command is in recent history (last 10 commands)
        cache_manager = get_cache_manager()
        if cache_manager:
            history = cache_manager.get_history()[:10]
            if command in history:
                score += 0.2
        
        # 4. Time patterns (0.1)
        current_hour = datetime.now().hour
        time_commands = self.pattern_analyzer._time_patterns.get(current_hour, [])
        if command in time_commands:
            score += 0.1
        
        return min(score, 1.0)  # Cap at 1.0
    
    def _is_context_available(self, command: str, context: Dict) -> bool:
        """Check if command's context is currently available."""
        # Check if command mentions an app that's running
        running_apps = context.get('running_apps', [])
        for app in running_apps:
            if app.lower() in command.lower():
                return True
        
        # Check if command mentions a tab that's open
        chrome_tabs = context.get('chrome_tabs', [])
        for tab in chrome_tabs:
            domain = tab.get('domain', '').lower()
            title = tab.get('title', '').lower()
            if domain and domain in command.lower():
                return True
            if title and any(word in command.lower() for word in title.split()[:3]):
                return True
        
        # Check if command mentions a preset that's available
        available_presets = context.get('available_presets', [])
        for preset in available_presets:
            if preset.lower() in command.lower():
                return True
        
        return False
    
    def _get_context_based_commands(self, context: Dict) -> List[str]:
        """Get commands based on current context (what's available)."""
        commands = []
        
        # Commands for running apps
        running_apps = context.get('running_apps', [])
        for app in running_apps:
            commands.extend([
                f"focus {app}",
                f"open {app}",
                f"close {app}",
                app,  # Implicit focus
            ])
        
        # Commands for open tabs
        chrome_tabs = context.get('chrome_tabs', [])
        for tab in chrome_tabs:
            domain = tab.get('domain', '')
            index = tab.get('index', 0)
            if domain:
                commands.extend([
                    f"switch to {domain}",
                    f"go to {domain}",
                    f"open {domain}",
                ])
            if index > 0:
                commands.extend([
                    f"switch to tab {index}",
                    f"tab {index}",
                    f"close tab {index}",
                ])
        
        # Commands for available presets
        available_presets = context.get('available_presets', [])
        for preset in available_presets:
            commands.extend([
                f"activate {preset}",
                f"load {preset}",
                preset,  # Implicit preset activation
            ])
        
        return commands
    
    def _get_history_based_commands(self) -> List[str]:
        """Get commands based on history (most common commands)."""
        return self.pattern_analyzer.get_top_commands(20)
    
    def _get_sequence_based_commands(self) -> List[str]:
        """Get commands based on sequences (likely next commands)."""
        # Get recent command from history
        cache_manager = get_cache_manager()
        if cache_manager:
            history = cache_manager.get_history()
            if history:
                last_command = history[0]
                return self.pattern_analyzer.get_next_likely_commands(last_command)
        return []
    
    def _get_time_based_commands(self) -> List[str]:
        """Get commands based on time patterns."""
        current_hour = datetime.now().hour
        return self.pattern_analyzer._time_patterns.get(current_hour, [])


class PredictiveCommandCache:
    """Manages pre-computed commands and coordinates all components (UX-focused, aggressive)."""
    
    def __init__(
        self,
        cache_manager,
        pattern_analyzer: CommandPatternAnalyzer,
        non_ai_precomputer: NonAIPrecomputer,
        ai_precomputer: AIPrecomputer,
        prioritizer: CommandPrioritizer,
        agent
    ):
        """
        Initialize the predictive command cache.
        
        Args:
            cache_manager: CacheManager instance
            pattern_analyzer: CommandPatternAnalyzer instance
            non_ai_precomputer: NonAIPrecomputer instance
            ai_precomputer: AIPrecomputer instance
            prioritizer: CommandPrioritizer instance
            agent: AIAgent instance
        """
        self.cache_manager = cache_manager or get_cache_manager()
        self.pattern_analyzer = pattern_analyzer
        self.non_ai_precomputer = non_ai_precomputer
        self.ai_precomputer = ai_precomputer
        self.prioritizer = prioritizer
        self.agent = agent
        self.precomputed_commands: Dict[str, Dict] = {}
        self._lock = threading.Lock()
    
    def get_precomputed(self, command: str) -> Optional[Dict]:
        """
        Check if command is pre-computed and return result.
        
        Args:
            command: Command text
            
        Returns:
            Parsed intent dict if pre-computed, None otherwise
        """
        normalized = command.lower().strip()
        
        with self._lock:
            return self.precomputed_commands.get(normalized)
    
    def precompute_for_context(self, context: Dict):
        """
        Pre-compute commands for current context (aggressive pre-computation for best UX).
        
        Args:
            context: Context dict with running_apps, chrome_tabs, available_presets, etc.
        """
        # Get priority commands from prioritizer
        priority_commands = self.prioritizer.get_priority_commands(context, max_commands=100)
        commands_to_precompute = [cmd for cmd, _ in priority_commands]
        
        # Pre-compute non-AI commands first (fast)
        non_ai_results = {}
        if context.get('running_apps'):
            non_ai_results.update(
                self.non_ai_precomputer.precompute_for_apps(context.get('running_apps', []), context)
            )
        if context.get('chrome_tabs'):
            non_ai_results.update(
                self.non_ai_precomputer.precompute_for_tabs(context.get('chrome_tabs', []), context)
            )
        if context.get('available_presets'):
            non_ai_results.update(
                self.non_ai_precomputer.precompute_for_presets(context.get('available_presets', []), context)
            )
        
        # Pre-compute AI commands in background (aggressive pre-computation)
        # Pre-compute ALL commands with AI for best UX
        ai_results = {}
        if commands_to_precompute:
            ai_results = self.ai_precomputer.precompute_commands(commands_to_precompute, context)
        
        # Also pre-compute for all tabs and apps aggressively
        if context.get('chrome_tabs'):
            ai_results.update(
                self.ai_precomputer.precompute_for_tabs(context.get('chrome_tabs', []), context)
            )
        if context.get('running_apps'):
            ai_results.update(
                self.ai_precomputer.precompute_for_apps(context.get('running_apps', []), context)
            )
        
        # Merge results
        with self._lock:
            self.precomputed_commands.update(non_ai_results)
            self.precomputed_commands.update(ai_results)
    
    def precompute_aggressively(self, context: Dict):
        """
        Aggressive pre-computation for best UX (pre-compute everything).
        
        Args:
            context: Context dict with running_apps, chrome_tabs, available_presets, etc.
        """
        # Pre-compute commands for ALL open tabs (all variations, all natural language forms)
        if context.get('chrome_tabs'):
            tab_results = self.ai_precomputer.precompute_for_tabs(context.get('chrome_tabs', []), context)
            with self._lock:
                self.precomputed_commands.update(tab_results)
        
        # Pre-compute commands for ALL running apps (all variations, all natural language forms)
        if context.get('running_apps'):
            app_results = self.ai_precomputer.precompute_for_apps(context.get('running_apps', []), context)
            with self._lock:
                self.precomputed_commands.update(app_results)
        
        # Pre-compute commands for ALL presets (all variations)
        if context.get('available_presets'):
            preset_results = self.non_ai_precomputer.precompute_for_presets(
                context.get('available_presets', []), context
            )
            with self._lock:
                self.precomputed_commands.update(preset_results)
        
        # Pre-compute common command sequences from history
        common_results = self.ai_precomputer.precompute_common_commands(context)
        with self._lock:
            self.precomputed_commands.update(common_results)
        
        # Pre-compute likely next commands based on current context
        priority_commands = self.prioritizer.get_priority_commands(context, max_commands=100)
        commands_to_precompute = [cmd for cmd, _ in priority_commands]
        if commands_to_precompute:
            priority_results = self.ai_precomputer.precompute_commands(commands_to_precompute, context)
            with self._lock:
                self.precomputed_commands.update(priority_results)
    
    def invalidate_on_context_change(self, old_context: Dict, new_context: Dict):
        """
        Immediately invalidate affected pre-computed commands when context changes.
        
        Args:
            old_context: Previous context dict
            new_context: New context dict
        """
        # Detect what changed
        old_apps = set(old_context.get('running_apps', []))
        new_apps = set(new_context.get('running_apps', []))
        removed_apps = old_apps - new_apps
        added_apps = new_apps - old_apps
        
        old_tabs = {tab.get('index') for tab in old_context.get('chrome_tabs', []) if isinstance(tab, dict)}
        new_tabs = {tab.get('index') for tab in new_context.get('chrome_tabs', []) if isinstance(tab, dict)}
        removed_tabs = old_tabs - new_tabs
        added_tabs = new_tabs - old_tabs
        
        # Invalidate commands for removed apps/tabs
        with self._lock:
            commands_to_remove = []
            for cmd in self.precomputed_commands.keys():
                # Check if command is for removed app
                for app in removed_apps:
                    if app.lower() in cmd:
                        commands_to_remove.append(cmd)
                        break
                
                # Check if command is for removed tab
                for tab_index in removed_tabs:
                    if f"tab {tab_index}" in cmd or f"tab {tab_index}" in cmd:
                        commands_to_remove.append(cmd)
                        break
            
            # Remove invalidated commands
            for cmd in commands_to_remove:
                self.precomputed_commands.pop(cmd, None)
        
        # Trigger aggressive re-computation for new context
        self.precompute_aggressively(new_context)
    
    def update_after_command(self, command: str, result: Dict):
        """
        Update predictive cache after a command is executed.
        
        NOTE: We don't store executed commands in predictive cache - they go to LLM cache.
        This method only updates pattern analysis and triggers pre-computation of likely next commands.
        Executed commands should use LLM cache (text-only keys) to avoid parameter conflicts.
        The predictive cache is only for pre-computed commands from background pre-computation.
        
        Args:
            command: Command text that was executed
            result: Parsed intent result
        """
        # Update pattern analyzer with new command
        self.pattern_analyzer.update_incremental(command)
        
        # DON'T store executed commands in predictive cache
        # Executed commands should use LLM cache (text-only keys) to avoid parameter conflicts
        # The predictive cache is only for pre-computed commands from background pre-computation
        
        # Pre-compute likely next commands (aggressively, using AI)
        # Get current context from background updater or cache
        cache_manager = get_cache_manager()
        if cache_manager:
            # Try to get context from cache
            running_apps = cache_manager.get(CacheKeys.RUNNING_APPS, [])
            chrome_tabs = cache_manager.get(CacheKeys.CHROME_TABS, [])
            presets = cache_manager.get(CacheKeys.PRESETS, {})
            available_presets = list(presets.keys()) if presets else []
            
            context = {
                'running_apps': running_apps,
                'chrome_tabs': chrome_tabs,
                'available_presets': available_presets
            }
            
            # Get likely next commands
            next_commands = self.pattern_analyzer.get_next_likely_commands(command)
            if next_commands:
                # Pre-compute likely next commands using AI
                next_results = self.ai_precomputer.precompute_commands(next_commands, context)
                with self._lock:
                    self.precomputed_commands.update(next_results)
    
    def clear(self):
        """Clear all pre-computed commands."""
        with self._lock:
            self.precomputed_commands.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about pre-computed commands."""
        with self._lock:
            return {
                'total_commands': len(self.precomputed_commands),
                'commands': list(self.precomputed_commands.keys())[:20]  # First 20 for debugging
            }

