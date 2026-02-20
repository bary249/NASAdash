# AI Tool Use Plan — RealPage Report Generation

## Overview
Give the AI chat agent the ability to generate RealPage reports on-demand when it needs data that isn't in the database. This enables the AI to self-heal data gaps and answer historical/ad-hoc questions autonomously.

## Phase 1: Scoped MVP (Current Sprint)

### Scope
- **Report type**: Box Score only (occupancy snapshot)
- **Date range**: Last 12 months only
- **Rate limit**: Max 2 report requests per chat session
- **Cache-first**: Check if data exists in `unified_occupancy_metrics` before downloading
- **Properties**: Only properties the authenticated user has access to

### Architecture
```
User asks: "What was occupancy 6 months ago?"
    ↓
Claude detects it needs historical data
    ↓
Claude calls tool: fetch_historical_box_score(property_id, target_date)
    ↓
Backend checks: is data already in unified_occupancy_metrics for that date?
    ├── YES → return cached data immediately
    └── NO  → trigger pipeline:
              create_instance → poll → download → parse → import → sync
              return fresh data (~30-60s)
    ↓
Claude receives the data and answers the question
```

### Implementation Details

#### 1. Tool Definition (in `chat_service.py`)
```python
TOOLS = [
    {
        "name": "fetch_historical_occupancy",
        "description": "Fetch historical occupancy data (box score) for a property at a specific date. Use this when the user asks about past occupancy, vacancy trends, or historical comparisons. Returns occupancy metrics for the requested month.",
        "input_schema": {
            "type": "object",
            "properties": {
                "property_id": {
                    "type": "string",
                    "description": "The property identifier (e.g., 'nexus_east')"
                },
                "target_month": {
                    "type": "string",
                    "description": "The target month in YYYY-MM format (e.g., '2025-08')"
                }
            },
            "required": ["property_id", "target_month"]
        }
    }
]
```

#### 2. Tool Executor (new `backend/app/services/report_tool_service.py`)
```python
class ReportToolService:
    """Executes AI-requested report downloads with caching and rate limiting."""
    
    def fetch_historical_occupancy(self, property_id: str, target_month: str) -> dict:
        """
        1. Check unified_occupancy_metrics for existing data
        2. If missing, trigger box_score download pipeline
        3. Return occupancy metrics dict
        """
        
    def _check_cache(self, property_id, target_month) -> Optional[dict]:
        """Check if we already have box_score data for this property/month."""
        
    def _download_box_score(self, property_id, end_date) -> dict:
        """Run: create → poll → download → parse → import → sync for one report."""
```

#### 3. Chat Loop with Tool Use (in `chat_service.py`)
```python
async def chat(self, message, property_data, history):
    # First call — may return tool_use
    response = self.client.messages.create(
        model=self.model,
        max_tokens=1024,
        system=system_prompt,
        messages=messages,
        tools=TOOLS,
    )
    
    # Handle tool use loop (max 2 iterations)
    tool_calls = 0
    while response.stop_reason == "tool_use" and tool_calls < 2:
        tool_block = [b for b in response.content if b.type == "tool_use"][0]
        result = self._execute_tool(tool_block.name, tool_block.input, property_data)
        
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": tool_block.id, "content": json.dumps(result)}
        ]})
        
        response = self.client.messages.create(
            model=self.model, max_tokens=1024,
            system=system_prompt, messages=messages, tools=TOOLS,
        )
        tool_calls += 1
    
    return response.content[0].text
```

#### 4. Auth Token Access
- Read from `backend/realpage_token.json` (refreshed every 6h by GH Actions)
- If token is expired, return error message instead of failing silently

#### 5. Rate Limiting
- Per-session counter in ChatService (reset on new session)
- Global hourly counter in SQLite (`ai_report_requests` table)
- Max 2 per session, max 10 per hour globally

### Files to Create/Modify
| File | Action |
|------|--------|
| `backend/app/services/report_tool_service.py` | **NEW** — Tool executor with cache check + pipeline trigger |
| `backend/app/services/chat_service.py` | **MODIFY** — Add tool definitions, tool use loop |
| `backend/app/api/routes.py` | **MODIFY** — Pass token path to chat service |

### Testing
1. Ask "What was occupancy in October 2025?" → should trigger tool → download → answer
2. Ask same question again → should hit cache → instant answer
3. Ask 3 tool-use questions in one session → 3rd should be refused (rate limit)

---

## Phase 2: Multi-Report Tools (Future)

### Additional Tools
| Tool | Report | Use Case |
|------|--------|----------|
| `fetch_historical_delinquency` | Report 4009 | "How has delinquency trended?" |
| `fetch_historical_leasing` | Activity Report | "Compare leasing activity Q3 vs Q4" |
| `fetch_income_statement` | Report 3836 | "What was revenue last quarter?" |
| `fetch_rent_roll_snapshot` | Rent Roll | "Show me the unit mix from 3 months ago" |

### Scaling Considerations
- **Queue system**: For heavy use, add a task queue (Redis/Celery) instead of blocking
- **Streaming**: Use SSE to show "Generating report..." progress to the frontend
- **Pre-emptive caching**: AI could suggest "I notice you often ask about monthly trends — should I pre-load the last 12 months?"
- **Cost tracking**: Log each API call with estimated cost (RealPage API has quotas)
- **Multi-property**: Allow "Compare occupancy across all properties in Q4" (batch download)

### Frontend Changes (Phase 2)
- Show a "🔄 Pulling data from RealPage..." spinner when tool is executing
- Display a "Data freshness" indicator showing when each metric was last updated
- Allow users to manually trigger report refresh from the UI

---

## Dependencies
- Valid RealPage JWT token (auto-refreshed by `auto_token.py` every 6h)
- Anthropic API with tool use support (Claude 3.5 Sonnet+)
- Existing pipeline: `report_parsers.py`, `import_reports.py`, `sync_realpage_to_unified.py`

## Risks
- **Latency**: 30-60s per report download. Mitigated by cache-first approach.
- **Token expiry**: If GH Actions refresh fails, tool calls fail. Mitigated by graceful error message.
- **Rate limits**: RealPage may throttle. Mitigated by per-session + global rate limits.
- **Data quality**: Historical box_scores may differ from current (e.g., unit counts changed). AI should note the snapshot date.
