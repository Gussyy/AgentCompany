# Technical Plan — FlowLock

## Tech Stack
- **backend**: Python/FastAPI
- **database**: PostgreSQL
- **frontend**: React + TypeScript (for hidden sidebar only)
- **hosting**: Railway
- **agent_framework**: LangChain
- **llm_provider**: OpenAI (GPT-4o)
- **integration_sdk**: Linear SDK / GitHub API v4 (GraphQL)

## Database Tables
### users
Columns: id, email, linear_access_token_encrypted, created_at
Indexes: email
### agent_rules
Columns: id, user_id, trigger_tool, trigger_condition_plain_text, action_plain_text, is_active, created_at
Indexes: user_id, is_active
### reliability_ledger
Columns: id, agent_rule_id, execution_trigger_id, status, failure_reason_one_line, executed_at
Indexes: agent_rule_id, executed_at

## API Routes
- `POST /api/webhooks/linear` 🔓 — Receives Linear webhook events (issue updates). Primary trigger source.
- `POST /api/agent/execute` 🔒 — Internal endpoint. Processes a triggered rule: reads context, calls LLM, writes result back to tool.
- `GET /api/ledger` 🔒 — Returns the Reliability Ledger entries for the authenticated user. For hidden sidebar.
- `POST /api/setup/rule` 🔒 — Creates an agent rule from a plain-English trigger-action definition provided via slash command.

## V1 Scope
- Silent Trigger Setup via Linear slash command
- Background Execution for a single Linear-to-Linear rule (e.g., 'When ticket moves to In Review, draft a summary comment')
- Reliability Ledger accessible via hidden browser sidebar
- Single-tool (Linear-only) read-write integration

## Deferred to V2
- Cross-tool workflows (e.g., Linear to GitHub)
- Support for a second core tool (e.g., GitHub)
- General chat interface or dashboard
- Team collaboration features
- Analytics or reports
- Mobile app
- Notification system
- Custom model fine-tuning