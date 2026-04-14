# Backend Build — CORE

Backend implementation for Identity Lens v1. Single SaaS connector (GitHub or Slack) with read-only OAuth. Permission extraction, static risk library, force-directed graph data, non-human identity detection, PDF report generation. User authentication via Auth0/OAuthLib. PostgreSQL database with defined tables. Redis for async job queue for sync operations and PDF generation.

## Files
- main.py
- config/database.py
- config/redis.py
- models/user.py
- models/core_saas_connections.py
- models/third_party_integrations.py
- models/granted_scopes.py
- models/risk_library.py
- schemas/user.py
- schemas/connection.py
- schemas/integration.py
- schemas/visualization.py
- schemas/report.py
- routers/auth.py
- routers/connections.py
- routers/visualization.py
- routers/non_human_identities.py
- routers/reports.py
- services/oauth_service.py
- services/sync_service.py
- services/visualization_service.py
- services/report_service.py
- workers/sync_worker.py
- workers/report_worker.py
- tests/test_auth.py
- tests/test_connections.py
- tests/test_visualization.py
- tests/test_non_human_identities.py
- tests/test_reports.py
- tests/test_models.py
- tests/test_services.py

## Notes
Flag: v1 specifies single SaaS connector but API route /api/auth/callback/{saas_platform} implies multiple. Will implement with placeholder for one (e.g., GitHub). Risk library is static—no update mechanism in v1. PDF generation and sync are async via Redis queue; ensure Railway supports Redis add-on. Auth mechanism uses Auth0/OAuthLib for user authentication, but SaaS platform OAuth (GitHub/Slack) uses separate OAuth flow. Ensure scopes are read-only as per v1.