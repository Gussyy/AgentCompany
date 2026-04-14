"""
database.py - SQLAlchemy ORM models and setup for Identity Lens
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    create_engine, Column, Integer, String, DateTime, 
    Boolean, ForeignKey, Enum, Text
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import func
import enum

# Define enums
class ConnectionStatus(enum.Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    ERROR = "error"

class AuthType(enum.Enum):
    OAUTH2 = "oauth2"
    API_KEY = "api_key"
    SERVICE_ACCOUNT = "service_account"

class RiskLevel(enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

# Create declarative base
Base = declarative_base()

class User(Base):
    """User accounts for Identity Lens"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    auth_provider_id = Column(String(255), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    
    # Relationships
    core_connections = relationship("CoreSaaSConnection", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, email={self.email})>"

class CoreSaaSConnection(Base):
    """Core SaaS platform connections (e.g., Slack, Google Workspace)"""
    __tablename__ = 'core_saas_connections'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete="CASCADE"), nullable=False, index=True)
    saas_platform = Column(String(100), nullable=False, index=True)
    oauth_access_token = Column(Text, nullable=False)
    oauth_refresh_token = Column(Text, nullable=True)
    connection_status = Column(Enum(ConnectionStatus), nullable=False, default=ConnectionStatus.ACTIVE)
    last_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="core_connections")
    third_party_integrations = relationship("ThirdPartyIntegration", back_populates="core_connection", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<CoreSaaSConnection(id={self.id}, platform={self.saas_platform}, status={self.connection_status.value})>"

class ThirdPartyIntegration(Base):
    """Third-party apps discovered within core SaaS platforms"""
    __tablename__ = 'third_party_integrations'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    core_connection_id = Column(Integer, ForeignKey('core_saas_connections.id', ondelete="CASCADE"), nullable=False, index=True)
    app_name = Column(String(200), nullable=False, index=True)
    app_id = Column(String(255), nullable=False, index=True)
    auth_type = Column(Enum(AuthType), nullable=False)
    is_service_account = Column(Boolean, nullable=False, default=False)
    discovered_at = Column(DateTime, nullable=False, server_default=func.now())
    
    # Relationships
    core_connection = relationship("CoreSaaSConnection", back_populates="third_party_integrations")
    granted_scopes = relationship("GrantedScope", back_populates="integration", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<ThirdPartyIntegration(id={self.id}, app={self.app_name}, auth_type={self.auth_type.value})>"

class GrantedScope(Base):
    """Scopes/permissions granted to third-party integrations"""
    __tablename__ = 'granted_scopes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    integration_id = Column(Integer, ForeignKey('third_party_integrations.id', ondelete="CASCADE"), nullable=False, index=True)
    scope_name = Column(String(500), nullable=False, index=True)
    risk_level = Column(Enum(RiskLevel), nullable=False)
    granted_at = Column(DateTime, nullable=False, server_default=func.now())
    
    # Relationships
    integration = relationship("ThirdPartyIntegration", back_populates="granted_scopes")
    
    def __repr__(self):
        return f"<GrantedScope(id={self.id}, scope={self.scope_name}, risk={self.risk_level.value})>"

class RiskLibrary(Base):
    """Library of known scope patterns and their risk assessments"""
    __tablename__ = 'risk_library'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    scope_pattern = Column(String(500), nullable=False, unique=True, index=True)
    risk_level = Column(Enum(RiskLevel), nullable=False)
    description = Column(Text, nullable=True)
    
    def __repr__(self):
        return f"<RiskLibrary(id={self.id}, pattern={self.scope_pattern}, risk={self.risk_level.value})>"

# Database engine and session factory
def create_database_engine(database_url: str, echo: bool = False):
    """Create SQLAlchemy engine with PostgreSQL dialect"""
    return create_engine(database_url, echo=echo, pool_pre_ping=True)

def create_session_factory(engine):
    """Create session factory for database operations"""
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_database(engine):
    """Create all tables in the database"""
    Base.metadata.create_all(bind=engine)

# Example usage (commented out for production):
# DATABASE_URL = "postgresql://user:password@localhost/identity_lens"
# engine = create_database_engine(DATABASE_URL)
# SessionLocal = create_session_factory(engine)
# init_database(engine)