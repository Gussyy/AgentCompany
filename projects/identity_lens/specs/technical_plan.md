# Technical Plan — Identity Lens

## Tech Stack
- **backend**: Python/FastAPI
- **database**: PostgreSQL
- **frontend**: React + TypeScript + D3.js
- **hosting**: Railway
- **auth_library**: Auth0 or OAuthLib
- **pdf_generation**: ReportLab

## Database Tables
### users
Columns: id, email, auth_provider_id, created_at
Indexes: email, auth_provider_id
### core_saas_connections
Columns: id, user_id, saas_platform, oauth_access_token, oauth_refresh_token, connection_status, last_synced_at, created_at
Indexes: user_id, saas_platform
### third_party_integrations
Columns: id, core_connection_id, app_name, app_id, auth_type, is_service_account, discovered_at
Indexes: core_connection_id, app_id
### granted_scopes
Columns: id, integration_id, scope_name, risk_level, granted_at
Indexes: integration_id, risk_level
### risk_library
Columns: id, scope_pattern, risk_level, description
Indexes: scope_pattern

## API Routes
- `POST /api/auth/callback/{saas_platform}` 🔓 — OAuth callback endpoint for SaaS platform connection
- `GET /api/connections` 🔒 — List user's SaaS platform connections
- `POST /api/connections/{connection_id}/sync` 🔒 — Trigger sync of integrations and permissions from connected SaaS platform
- `GET /api/visualization/graph` 🔒 — Get force-directed graph data for visualization
- `GET /api/non-human-identities` 🔒 — Get list of integrations using service accounts/API keys
- `POST /api/reports/generate` 🔒 — Generate PDF report snapshot

## V1 Scope
- Single SaaS connector with read-only OAuth
- Permission extraction for third-party integrations
- Static risk library for scope classification
- Force-directed graph visualization
- Non-human identity detection via auth metadata
- Single-page PDF report generation
- User authentication and management

## Deferred to V2
- Multiple SaaS platform connectors
- Real-time monitoring and alerting
- Historical trend analysis
- Custom risk scoring models
- SIEM/ticketing system integrations
- Remediation actions
- Log analysis and UBA
- Internal code/infrastructure scanning