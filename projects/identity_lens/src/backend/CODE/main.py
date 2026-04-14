import os
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Depends, status, Query
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field, EmailStr
import asyncpg
from authlib.integrations.starlette_client import OAuth
from starlette.requests import Request
from starlette.config import Config
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import json

app = FastAPI(title="Identity Lens API", version="1.0.0")

# Database connection pool
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/identity_lens")
pool = None

async def get_db():
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(DATABASE_URL)
    return pool

# OAuth configuration
config = Config('.env')
oauth = OAuth(config)

# Configure OAuth clients (example for Slack)
oauth.register(
    name='slack',
    client_id=os.getenv('SLACK_CLIENT_ID'),
    client_secret=os.getenv('SLACK_CLIENT_SECRET'),
    authorize_url='https://slack.com/oauth/v2/authorize',
    access_token_url='https://slack.com/api/oauth.v2.access',
    client_kwargs={'scope': 'admin'}
)

# Pydantic Models
class UserBase(BaseModel):
    email: EmailStr
    auth_provider_id: str

class UserCreate(UserBase):
    pass

class UserResponse(UserBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True

class SaaSConnectionBase(BaseModel):
    saas_platform: str
    oauth_access_token: str
    oauth_refresh_token: Optional[str] = None
    connection_status: str = "active"

class SaaSConnectionCreate(SaaSConnectionBase):
    user_id: UUID

class SaaSConnectionResponse(SaaSConnectionBase):
    id: UUID
    user_id: UUID
    last_synced_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True

class ThirdPartyIntegrationBase(BaseModel):
    app_name: str
    app_id: str
    auth_type: str
    is_service_account: bool = False

class ThirdPartyIntegrationCreate(ThirdPartyIntegrationBase):
    core_connection_id: UUID

class ThirdPartyIntegrationResponse(ThirdPartyIntegrationBase):
    id: UUID
    core_connection_id: UUID
    discovered_at: datetime

    class Config:
        from_attributes = True

class GrantedScopeBase(BaseModel):
    scope_name: str
    risk_level: str

class GrantedScopeCreate(GrantedScopeBase):
    integration_id: UUID

class GrantedScopeResponse(GrantedScopeBase):
    id: UUID
    integration_id: UUID
    granted_at: datetime

    class Config:
        from_attributes = True

class RiskLibraryBase(BaseModel):
    scope_pattern: str
    risk_level: str
    description: str

class RiskLibraryResponse(RiskLibraryBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True

class SyncRequest(BaseModel):
    force_refresh: bool = False

class GraphNode(BaseModel):
    id: str
    name: str
    type: str
    risk_level: Optional[str] = None

class GraphLink(BaseModel):
    source: str
    target: str
    scope: str
    risk_level: str

class GraphResponse(BaseModel):
    nodes: List[GraphNode]
    links: List[GraphLink]

class NonHumanIdentityResponse(BaseModel):
    integration_id: UUID
    app_name: str
    app_id: str
    auth_type: str
    discovered_at: datetime
    connection_platform: str

class ReportRequest(BaseModel):
    connection_ids: List[UUID]
    include_risk_summary: bool = True

# Dependency to get current user (simplified - in production use proper Auth0 integration)
async def get_current_user(request: Request) -> dict:
    # This is a placeholder - implement proper Auth0/JWT validation
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Not authenticated")
    # In production, validate JWT with Auth0
    return {"user_id": "test-user-id", "email": "test@example.com"}

# API Routes
@app.post("/api/auth/callback/{saas_platform}")
async def oauth_callback(
    saas_platform: str,
    request: Request,
    db=Depends(get_db)
):
    """OAuth callback endpoint for SaaS platform connection"""
    if saas_platform not in ["slack", "salesforce", "github"]:
        raise HTTPException(status_code=400, detail="Unsupported SaaS platform")
    
    token = await oauth.slack.authorize_access_token(request)
    # Store token and create connection in database
    async with db.acquire() as conn:
        # Get user from session or token
        user_email = token.get("user", {}).get("email", "unknown@example.com")
        
        # Check if user exists
        user = await conn.fetchrow(
            "SELECT id FROM users WHERE email = $1",
            user_email
        )
        
        if not user:
            user = await conn.fetchrow(
                "INSERT INTO users (email, auth_provider_id) VALUES ($1, $2) RETURNING id",
                user_email, f"{saas_platform}_{token.get('user_id', 'unknown')}"
            )
        
        # Create or update connection
        connection = await conn.fetchrow("""
            INSERT INTO core_saas_connections 
            (user_id, saas_platform, oauth_access_token, oauth_refresh_token, connection_status)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (user_id, saas_platform) 
            DO UPDATE SET 
                oauth_access_token = EXCLUDED.oauth_access_token,
                oauth_refresh_token = EXCLUDED.oauth_refresh_token,
                connection_status = EXCLUDED.connection_status
            RETURNING id, user_id, saas_platform, connection_status, created_at
        """, 
        user["id"], saas_platform, token["access_token"], 
        token.get("refresh_token"), "active")
        
        return {
            "connection_id": str(connection["id"]),
            "platform": saas_platform,
            "status": "connected"
        }

@app.get("/api/connections")
async def list_connections(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """List user's SaaS platform connections"""
    async with db.acquire() as conn:
        connections = await conn.fetch("""
            SELECT id, user_id, saas_platform, connection_status, last_synced_at, created_at
            FROM core_saas_connections 
            WHERE user_id = $1::uuid
            ORDER BY created_at DESC
        """, UUID(current_user["user_id"]))
        
        return [
            {
                "id": str(row["id"]),
                "saas_platform": row["saas_platform"],
                "connection_status": row["connection_status"],
                "last_synced_at": row["last_synced_at"],
                "created_at": row["created_at"]
            }
            for row in connections
        ]

@app.post("/api/connections/{connection_id}/sync")
async def trigger_sync(
    connection_id: UUID,
    sync_request: SyncRequest,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """Trigger sync of integrations and permissions from connected SaaS platform"""
    async with db.acquire() as conn:
        # Verify connection belongs to user
        connection = await conn.fetchrow("""
            SELECT id, saas_platform, oauth_access_token 
            FROM core_saas_connections 
            WHERE id = $1 AND user_id = $2
        """, connection_id, UUID(current_user["user_id"]))
        
        if not connection:
            raise HTTPException(status_code=404, detail="Connection not found")
        
        # Update last_synced_at
        await conn.execute("""
            UPDATE core_saas_connections 
            SET last_synced_at = NOW() 
            WHERE id = $1
        """, connection_id)
        
        # In production, this would call the actual SaaS platform API
        # For now, simulate discovering some integrations
        if sync_request.force_refresh:
            # Clear existing integrations for this connection
            await conn.execute("""
                DELETE FROM third_party_integrations 
                WHERE core_connection_id = $1
            """, connection_id)
        
        # Simulate discovering integrations
        integrations = [
            ("Slack App", "A123", "oauth", False),
            ("Zapier", "Z456", "api_key", True),
            ("Google Calendar", "G789", "service_account", True)
        ]
        
        for app_name, app_id, auth_type, is_service_account in integrations:
            integration = await conn.fetchrow("""
                INSERT INTO third_party_integrations 
                (core_connection_id, app_name, app_id, auth_type, is_service_account)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
            """, connection_id, app_name, app_id, auth_type, is_service_account)
            
            # Add some sample scopes
            scopes = [
                ("channels:read", "low"),
                ("channels:write", "medium"),
                ("users:read", "low"),
                ("admin", "high")
            ]
            
            for scope_name, risk_level in scopes:
                await conn.execute("""
                    INSERT INTO granted_scopes (integration_id, scope_name, risk_level)
                    VALUES ($1, $2, $3)
                """, integration["id"], scope_name, risk_level)
        
        return {
            "status": "sync_triggered",
            "connection_id": str(connection_id),
            "message": "Sync completed successfully"
        }

@app.get("/api/visualization/graph")
async def get_visualization_graph(
    connection_id: Optional[UUID] = Query(None),
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """Get force-directed graph data for visualization"""
    async with db.acquire() as conn:
        # Build query based on whether connection_id is provided
        query = """
            SELECT 
                c.id as connection_id,
                c.saas_platform,
                i.id as integration_id,
                i.app_name,
                i.app_id,
                i.auth_type,
                i.is_service_account,
                gs.scope_name,
                gs.risk_level
            FROM core_saas_connections c
            LEFT JOIN third_party_integrations i ON c.id = i.core_connection_id
            LEFT JOIN granted_scopes gs ON i.id = gs.integration_id
            WHERE c.user_id = $1
        """
        params = [UUID(current_user["user_id"])]
        
        if connection_id:
            query += " AND c.id = $2"
            params.append(connection_id)
        
        rows = await conn.fetch(query, *params)
        
        nodes = []
        links = []
        node_ids = set()
        
        for row in rows:
            # Add SaaS platform node
            platform_node_id = f"platform_{row['connection_id']}"
            if platform_node_id not in node_ids:
                nodes.append(GraphNode(
                    id=platform_node_id,
                    name=row["saas_platform"],
                    type="platform"
                ))
                node_ids.add(platform_node_id)
            
            # Add integration node if exists
            if row["integration_id"]:
                integration_node_id = f"integration_{row['integration_id']}"
                if integration_node_id not in node_ids:
                    nodes.append(GraphNode(
                        id=integration_node_id,
                        name=row["app_name"],
                        type="integration",
                        risk_level="high" if row["is_service_account"] else "medium"
                    ))
                    node_ids.add(integration_node_id)
                
                # Add link between platform and integration
                if row["scope_name"]:
                    links.append(GraphLink(
                        source=platform_node_id,
                        target=integration_node_id,
                        scope=row["scope_name"],
                        risk_level=row["risk_level"] or "unknown"
                    ))
        
        return GraphResponse(nodes=nodes, links=links)

@app.get("/api/non-human-identities")
async def get_non_human_identities(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """Get list of integrations using service accounts/API keys"""
    async with db.acquire() as conn:
        rows = await conn.fetch("""
            SELECT 
                i.id as integration_id,
                i.app_name,
                i.app_id,
                i.auth_type,
                i.discovered_at,
                c.saas_platform as connection_platform
            FROM third_party_integrations i
            JOIN core_saas_connections c ON i.core_connection_id = c.id
            WHERE c.user_id = $1 
            AND (i.is_service_account = true OR i.auth_type IN ('api_key', 'service_account'))
            ORDER BY i.discovered_at DESC
        """, UUID(current_user["user_id"]))
        
        return [
            NonHumanIdentityResponse(
                integration_id=row["integration_id"],
                app_name=row["app_name"],
                app_id=row["app_id"],
                auth_type=row["auth_type"],
                discovered_at=row["discovered_at"],
                connection_platform=row["connection_platform"]
            )
            for row in rows
        ]

@app.post("/api/reports/generate")
async def generate_report(
    report_request: ReportRequest,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """Generate PDF report snapshot"""
    async with db.acquire() as conn:
        # Fetch data for report
        query = """
            SELECT 
                c.saas_platform,
                i.app_name,
                i.auth_type,
                i.is_service_account,
                gs.scope_name,
                gs.risk_level,
                COUNT(*) as scope_count
            FROM core_saas_connections c
            LEFT JOIN third_party_integrations i ON c.id = i.core_connection_id
            LEFT JOIN granted_scopes gs ON i.id = gs.integration_id
            WHERE c.user_id = $1 AND c.id = ANY($2::uuid[])
            GROUP BY c.saas_platform, i.app_name, i.auth_type, i.is_service_account, gs.scope_name, gs.risk_level
            ORDER BY c.saas_platform, i.app_name
        """
        
        rows = await conn.fetch(
            query, 
            UUID(current_user["user_id"]), 
            report_request.connection_ids
        )
        
        # Create PDF
        filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = f"/tmp/{filename}"
        
        c = canvas.Canvas(filepath, pagesize=letter)
        width, height = letter
        
        # Title
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, height - 50, "Identity Lens Security Report")
        c.setFont("Helvetica", 12)
        c.drawString(50, height - 80, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Summary
        y_position = height - 120
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y_position, "Summary")
        y_position -= 30
        
        c.setFont("Helvetica", 10)
        platforms = set(row["saas_platform"] for row in rows if row["saas_platform"])
        integrations = set(row["app_name"] for row in rows if row["app_name"])
        
        c.drawString(50, y_position, f"Platforms Analyzed: {len(platforms)}")
        y_position -= 20
        c.drawString(50, y_position, f"Third-Party Integrations: {len(integrations)}")
        y_position -= 20
        
        # Risk breakdown
        risk_counts = {}
        for row in rows:
            if row["risk_level"]:
                risk_counts[row["risk_level"]] = risk_counts.get(row["risk_level"], 0) + 1
        
        c.drawString(50, y_position, "Risk Level Distribution:")
        y_position -= 20
        
        for risk_level, count in risk_counts.items():
            c.drawString(70, y_position, f"{risk_level}: {count} scopes")
            y_position -= 15
        
        y_position -= 20
        
        # Detailed findings
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y_position, "Detailed Findings")
        y_position -= 30
        
        c.setFont("Helvetica", 10)
        current_platform = None
        
        for row in rows:
            if row["saas_platform"] != current_platform:
                if current_platform is not None:
                    y_position -= 20
                
                if y_position < 100:
                    c.showPage()
                    y_position = height - 50
                    c.setFont("Helvetica", 10)
                
                c.setFont("Helvetica-Bold", 12)
                c.drawString(50, y_position, f"Platform: {row['saas_platform']}")
                y_position -= 20
                current_platform = row["saas_platform"]
                c.setFont("Helvetica", 10)
            
            if row["app_name"]:
                if y_position < 100:
                    c.showPage()
                    y_position = height - 50
                    c.setFont("Helvetica", 10)
                
                c.drawString(70, y_position, f"Integration: {row['app_name']} ({row['auth_type']})")
                y_position -= 15
                
                if row["scope_name"]:
                    c.drawString(90, y_position, f"Scope: {row['scope_name']} - Risk: {row['risk_level']}")
                    y_position -= 15
                
                y_position -= 5
        
        c.save()
        
        return FileResponse(
            filepath, 
            media_type='application/pdf