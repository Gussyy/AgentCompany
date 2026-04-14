# Backend Build — CORE

Backend implementation for FlowLock v1. Provides API endpoints to handle Linear webhooks, execute agent rules, manage rules via slash command, and serve reliability data. Uses FastAPI with PostgreSQL, JWT for authentication, and integrates with Linear and OpenAI APIs.

## Files
- main.py
- database.py
- models/user.py
- models/agent_rule.py
- models/reliability_ledger.py
- schemas/user.py
- schemas/agent_rule.py
- schemas/reliability_ledger.py
- routers/auth.py
- routers/webhooks.py
- routers/agent.py
- routers/ledger.py
- routers/setup.py
- core/config.py
- core/security.py
- core/dependencies.py
- services/linear_service.py
- services/llm_service.py
- services/rule_executor.py
- tests/test_main.py
- tests/test_auth.py
- tests/test_webhooks.py
- tests/test_agent.py
- tests/test_ledger.py
- tests/test_setup.py
- tests/test_services_linear.py
- tests/test_services_llm.py
- tests/test_services_rule_executor.py

## Notes
Flag: The POST /api/webhooks/linear endpoint has no authentication, relying solely on Linear's webhook secret for validation. This is acceptable but must be documented as a security consideration. Flag: The 'trigger_condition_plain_text' and 'action_plain_text' fields are stored as plain text; we assume the LLM will parse them at execution time. This is a v1 simplification but may need a more structured condition/action representation later for complex rules.