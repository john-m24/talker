# System API Contract

## Overview

The system exposes a set of operations that can be called via structured JSON. The LLM acts as a client that matches user intent to these operations and provides specific parameters.

**Core Principle:** LLM = Smart Matcher, System = Dumb Executor

- **LLM Responsibilities:** Understand natural language, match user intent against context, extract specific parameters, return structured API calls
- **System Responsibilities:** Validate inputs, execute operations reliably, handle errors, manage state, optimize performance

---

## Architecture

```
┌─────────────────┐
│   User Input    │
│  (Natural Lang) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   LLM Client    │  ← Smart Matcher
│                 │
│ - Understands   │
│ - Matches       │
│ - Extracts      │
│ - Returns API   │
│   calls         │
└────────┬────────┘
         │
         │ JSON API Calls
         ▼
┌─────────────────┐
│  API Server     │  ← Dumb Executor
│  (System)       │
│                 │
│ - Validates     │
│ - Executes      │
│ - Returns       │
└─────────────────┘
```

---

## Available Operations

### 1. `list_apps`
**Description:** List all running applications

**Parameters:** None

**Example:**
```json
{
  "type": "list_apps"
}
```

---

### 2. `focus_app`
**Description:** Bring an application to the front (launches if not running)

**Parameters:**
- `app_name` (string, required): Exact application name from running/installed apps (non-empty string)

**Type Definitions:**
- `string`: Non-empty string

**Example:**
```json
{
  "type": "focus_app",
  "app_name": "Google Chrome"
}
```

---

### 3. `place_app`
**Description:** Move an application window to a specific monitor or position

**Parameters:**
- `app_name` (string, required): Exact application name (non-empty string)
- `monitor` (enum, optional): One of "main", "right", "left". Optional if bounds provided.
- `bounds` (array<integer>, optional): Exact window bounds `[left, top, right, bottom]` in absolute screen coordinates. AI calculates these based on monitor dimensions and user intent.

**Type Definitions:**
- `string`: Non-empty string
- `enum`: One of the specified values
- `array<integer>`: Array of 4 integers representing [left, top, right, bottom] coordinates

**Example (monitor-based placement):**
```json
{
  "type": "place_app",
  "app_name": "Google Chrome",
  "monitor": "left"
}
```

**Example (bounds-based placement - left half):**
```json
{
  "type": "place_app",
  "app_name": "Google Chrome",
  "monitor": "right",
  "bounds": [1920, 0, 2880, 1080]
}
```

**Example (bounds-based placement - maximize):**
```json
{
  "type": "place_app",
  "app_name": "Google Chrome",
  "bounds": [0, 0, 1920, 1080]
}
```

**Example (bounds-based placement - specific size, centered):**
```json
{
  "type": "place_app",
  "app_name": "Terminal",
  "monitor": "left",
  "bounds": [360, 140, 1560, 940]
}
```

**Note:** The AI receives monitor context (dimensions) and calculates bounds based on user intent. For example:
- "left half" → `bounds: [monitor_x, monitor_y, monitor_x + monitor_w/2, monitor_y + monitor_h]`
- "right half" → `bounds: [monitor_x + monitor_w/2, monitor_y, monitor_x + monitor_w, monitor_y + monitor_h]`
- "1200x800" → `bounds: [monitor_x + (monitor_w-1200)/2, monitor_y + (monitor_h-800)/2, ...]` (centered)
- "maximize" → `bounds: [monitor_x, monitor_y, monitor_x + monitor_w, monitor_y + monitor_h]`

---

### 4. `close_app`
**Description:** Quit/close an application completely

**Parameters:**
- `app_name` (string, required): Exact application name (non-empty string)

**Type Definitions:**
- `string`: Non-empty string

**Example:**
```json
{
  "type": "close_app",
  "app_name": "Google Chrome"
}
```

---

### 5. `list_tabs`
**Description:** List all open Chrome tabs

**Parameters:** None

**Example:**
```json
{
  "type": "list_tabs"
}
```

---

### 6. `switch_tab`
**Description:** Switch to a specific Chrome tab

**Parameters:**
- `tab_index` (integer, required): Global tab index (1-based, across all windows, positive integer)

**Type Definitions:**
- `integer`: Positive integer (1-based indexing)

**Example:**
```json
{
  "type": "switch_tab",
  "tab_index": 3
}
```

**Note:** LLM must match user intent ("reddit", "github", etc.) to specific tab index using available tab data.

---

### 7. `open_url`
**Description:** Open a URL in Chrome by creating a new tab

**Parameters:**
- `url` (string, required): URL to open (non-empty string). The system will normalize the URL if needed (e.g., adds https:// if missing, handles common site names like "chatgpt" → "chatgpt.com")

**Type Definitions:**
- `string`: Non-empty string

**Example:**
```json
{
  "type": "open_url",
  "url": "https://chatgpt.com"
}
```

**Example (site name, will be normalized):**
```json
{
  "type": "open_url",
  "url": "chatgpt"
}
```

**Note:** 
- This command always creates a new tab. The AI should decide between `switch_tab` (for existing tabs) and `open_url` (for new tabs) based on user intent.
- Use `switch_tab` when user wants to go to an existing tab (e.g., "go to github", "switch to reddit tab").
- Use `open_url` when user explicitly wants to open a new tab (e.g., "open chatgpt in chrome", "open a new tab for github").

---

### 8. `close_tab`
**Description:** Close one or more Chrome tabs

**Parameters:**
- `tab_indices` (array<integer>, required): Array of global tab indices (1-based, across all windows). For single tab, use array with one element: `[3]`

**Type Definitions:**
- `array<integer>`: Array of integers, non-empty, all values must be positive integers (1-based)

**Example (single tab):**
```json
{
  "type": "close_tab",
  "tab_indices": [3]
}
```

**Example (bulk operation):**
```json
{
  "type": "close_tab",
  "tab_indices": [2, 5, 8]
}
```

**Note:** LLM must match user intent ("all reddit tabs", "tabs 1, 3, and 5", etc.) to specific tab indices. System will optimize execution (close from highest to lowest to avoid index shifting).

---

### 9. `activate_preset`
**Description:** Activate a named preset window layout

**Parameters:**
- `preset_name` (string, required): Exact preset name from available presets (non-empty string)

**Type Definitions:**
- `string`: Non-empty string

**Example:**
```json
{
  "type": "activate_preset",
  "preset_name": "code space"
}
```

---

### 10. `query`
**Description:** Answer general questions about system state (tabs, apps, files, projects, history) using available context. Returns natural-language answers; does not execute any command.

**Parameters:**
- `question` (string, required): The user's question

**Example:**
```json
{
  "type": "query",
  "question": "What are my oldest tabs right now?"
}
```

**Notes:**
- The system answers based on current context (running apps, installed apps, tabs, recent files, projects).
- Recent query Q&A are kept in memory for follow-up context within the current run.

---

## Request Format

All operations are called via a JSON object with:
- `commands` (array): Array of operation objects
- `needs_clarification` (boolean): Whether clarification is needed
- `clarification_reason` (string, optional): Reason for clarification

**Example (single operation):**
```json
{
  "commands": [
    {
      "type": "switch_tab",
      "tab_index": 3
    }
  ],
  "needs_clarification": false,
  "clarification_reason": null
}
```

**Example (multiple operations):**
```json
{
  "commands": [
    {
      "type": "place_app",
      "app_name": "Google Chrome",
      "monitor": "left"
    },
    {
      "type": "place_app",
      "app_name": "Cursor",
      "monitor": "right"
    }
  ],
  "needs_clarification": false,
  "clarification_reason": null
}
```

**Example (needs clarification):**
```json
{
  "commands": [
    {
      "type": "switch_tab"
    }
  ],
  "needs_clarification": true,
  "clarification_reason": "Could not find a tab matching 'xyz'. Did you mean one of these tabs?"
}
```

---

## Context Provided to LLM

The LLM receives the following context to make matching decisions:

1. **Running Applications:** List of currently running apps
2. **Installed Applications:** List of installed apps (for fuzzy matching)
3. **Chrome Tabs (Raw):** Raw AppleScript output with all tab data
4. **Chrome Tabs (Parsed):** Parsed tab data with:
   - `index`: Global tab index
   - `title`: Tab title
   - `url`: Full URL
   - `domain`: Extracted domain
   - `content_summary`: Page content summary
   - `is_active`: Whether tab is active
   - `window_index`: Window index
   - `local_index`: Local tab index within window
5. **Available Presets:** List of available preset names

---

## LLM Responsibilities

The LLM acts as an intelligent API client:

1. **Understand Natural Language:** Parse user intent from natural language
2. **Match Context:** Match user intent against available context (apps, tabs, presets)
3. **Extract Parameters:** Extract specific parameters (app names, tab indices, etc.)
4. **Call API:** Return structured API calls with specific parameters
5. **Handle Ambiguity:** Detect when clarification is needed

**Example Flow:**
```
User: "switch to reddit"
  ↓
LLM:
  - Parses "reddit"
  - Matches against tab data
  - Finds: Tab 3 has domain "reddit.com"
  - Returns: {"type": "switch_tab", "tab_index": 3}
  ↓
System:
  - Receives API call
  - Validates tab_index: 3 exists
  - Executes switch_to_chrome_tab(tab_index=3)
```

**Example Flow (Bulk Operation):**
```
User: "close all reddit tabs"
  ↓
LLM:
  - Parses "all reddit tabs"
  - Matches against tab data
  - Finds: Tabs 2, 5, 8 have domain "reddit.com"
  - Returns: {"type": "close_tab", "tab_indices": [2, 5, 8]}
  ↓
System:
  - Receives API call
  - Validates tab_indices exist
  - Executes close_chrome_tabs_by_indices([2, 5, 8])
```

---

## System Responsibilities

The system acts as a reliable API server:

1. **Validate Inputs:** Validate all parameters before execution
2. **Execute Operations:** Execute operations reliably
3. **Handle Errors:** Provide clear error messages
4. **Manage State:** Handle state changes (tab indices shifting, etc.)
5. **Optimize Performance:** Optimize execution (bulk operations, etc.)

---

## Key Principles

1. **LLM = Smart Matcher:** LLM matches user intent to specific identifiers
2. **System = Dumb Executor:** System executes operations with specific parameters
3. **No Filters:** LLM should return specific indices/names, not filters
4. **Clear Contract:** API contract is well-defined and documented
5. **Separation of Concerns:** LLM handles matching, system handles execution

---

## Error Handling

**If LLM can't find a match:**
```json
{
  "commands": [{"type": "switch_tab"}],
  "needs_clarification": true,
  "clarification_reason": "Could not find a tab matching 'xyz'. Did you mean one of these tabs?"
}
```

**If system receives invalid parameters:**
- System validates before execution
- Returns error if validation fails
- Provides clear error message to user

---

## Benefits of API Approach

1. **Clear Contract:** Well-defined operations and parameters
2. **Separation of Concerns:** LLM matches, system executes
3. **Testability:** Can test API operations independently
4. **Extensibility:** Easy to add new operations
5. **Reliability:** System execution is deterministic
6. **Debugging:** Clear boundaries for debugging

---

## MCP Server Analogy

This architecture follows the Model Context Protocol (MCP) pattern:

1. **Tools/Functions:** System operations (like MCP tools)
2. **Tool Descriptions:** API contract documentation
3. **Tool Calls:** LLM returns structured calls
4. **Tool Execution:** System executes tools
5. **Tool Results:** System returns results

The system acts as an MCP server, exposing tools that the LLM can call with specific parameters.

