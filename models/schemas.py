"""
Pydantic data models — the structured contracts that agents pass to each other.
Every chamber input/output is typed. No loose dicts between agents.
"""
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from enum import Enum
from datetime import datetime


# ── Enums ──────────────────────────────────────────────────────

class GateVerdict(str, Enum):
    GO    = "GO"
    KILL  = "KILL"
    PIVOT = "PIVOT"

class LoopClassification(str, Enum):
    CRITICAL_BUG        = "CRITICAL_BUG"
    FEATURE_IMPROVEMENT = "FEATURE_IMPROVEMENT"
    STRATEGIC_PIVOT     = "STRATEGIC_PIVOT"

class AgentStatus(str, Enum):
    IDLE       = "idle"
    RUNNING    = "running"
    DONE       = "done"
    BLOCKED    = "blocked"
    ERROR      = "error"


# ── Chamber 1: Truth Seekers ───────────────────────────────────

class FrictionPoint(BaseModel):
    title:          str
    description:    str
    frequency:      int = Field(..., ge=1, le=10, description="How often is this complained about")
    severity:       int = Field(..., ge=1, le=10, description="How painful is this for users")
    emotional_heat: int = Field(..., ge=1, le=10, description="Emotional intensity of complaints")
    willingness_to_pay: bool = Field(False, description="Do complaints mention willingness to pay for a fix")

class FrictionReport(BaseModel):
    """Output of ARIA (The Observer)"""
    industry:        str
    friction_points: List[FrictionPoint]
    top_opportunity: str
    sources:         List[str]
    timestamp:       str = Field(default_factory=lambda: datetime.now().isoformat())

class CustomerSegment(BaseModel):
    name:        str
    description: str
    job_to_be_done: str
    decision_speed: str  # "fast" | "medium" | "slow"

class MVPFeature(BaseModel):
    name:        str
    description: str
    priority:    int = Field(..., ge=1, le=3)  # 1=must, 2=should, 3=nice

    @field_validator("priority", mode="before")
    @classmethod
    def clamp_priority(cls, v):
        """LLMs sometimes return priority 4+. Clamp to valid range 1-3."""
        try:
            v = int(v)
        except (TypeError, ValueError):
            return 3
        return max(1, min(3, v))

class ProductBlueprint(BaseModel):
    """Output of NOVA (The Inventor)"""
    product_name:       str
    value_proposition:  str
    customer_segment:   CustomerSegment
    mvp_features:       List[MVPFeature]
    explicitly_out_of_scope: List[str]
    friction_addressed: str

class FinancialModel(BaseModel):
    """Output of QUANT (The Accountant) — exists in projected and real-data variants"""
    tam_usd:            float
    build_cost_usd:     float
    projected_cac_usd:  float
    real_cac_usd:       Optional[float] = None  # populated after Smoke Test
    price_per_user_usd: float
    monthly_revenue_target: float
    gross_margin_pct:   float
    payback_months:     int
    roi_12m_pct:        float
    is_post_smoke_test: bool = False
    notes:              str = ""

class GateScore(BaseModel):
    margin_pct_score:          float = Field(..., ge=0, le=10)
    tam_score:                 float = Field(..., ge=0, le=10)
    time_to_build_score:       float = Field(..., ge=0, le=10)
    competitive_density_score: float = Field(..., ge=0, le=10)
    composite_score:           float = Field(..., ge=0, le=10)

    @field_validator(
        "margin_pct_score", "tam_score", "time_to_build_score",
        "competitive_density_score", "composite_score",
        mode="before"
    )
    @classmethod
    def clamp_score(cls, v):
        try:
            v = float(v)
        except (TypeError, ValueError):
            return 5.0
        return max(0.0, min(10.0, v))

class GateDecision(BaseModel):
    """Output of GATE (The Gatekeeper)"""
    verdict:      GateVerdict
    score:        GateScore
    reason:       str
    pivot_brief:  Optional[str] = None   # populated if PIVOT
    approved_at:  str = Field(default_factory=lambda: datetime.now().isoformat())


# ── Chamber 1.5: Smoke Test ────────────────────────────────────

class SmokeTestResult(BaseModel):
    """Output of APEX running the Smoke Test"""
    ad_spend_usd:       float
    impressions:        int
    clicks:             int
    ctr:                float   # click-through rate
    buy_now_conversions: int
    conversion_rate:    float
    real_cac_usd:       float
    passed:             bool
    notes:              str = ""


# ── Chamber 2: The Factory ─────────────────────────────────────

class DatabaseTable(BaseModel):
    name:    str
    columns: List[str]
    indexes: List[str] = []

class APIRoute(BaseModel):
    method:      str   # GET | POST | PUT | DELETE
    path:        str
    description: str
    auth_required: bool = True

class TechnicalPlan(BaseModel):
    """Output of ARCH (The Blueprint Maker)"""
    product_name:    str
    tech_stack:      dict
    database_tables: List[DatabaseTable]
    api_routes:      List[APIRoute]
    dependencies:    List[str]
    v1_scope:        List[str]
    deferred_to_v2:  List[str]

class BuildArtifact(BaseModel):
    """Output of CORE or PIXEL"""
    agent:       str   # "CORE" or "PIXEL"
    description: str
    files:       List[str]   # list of filenames produced
    notes:       str = ""

class QAIssue(BaseModel):
    severity:    str   # "P0" | "P1" | "P2"
    component:   str   # "backend" | "frontend"
    description: str
    route_to:    str   # "CORE" | "PIXEL"

class QAReport(BaseModel):
    """Output of VIGIL (The Inspector)"""
    test_coverage_pct:         float
    critical_vulnerabilities:  int
    performance_passed:        bool
    p0_bugs:                   List[QAIssue]
    p1_bugs:                   List[QAIssue]
    definition_of_done_passed: bool
    notes:                     str = ""


# ── Chamber 2.5: Soft Launch ───────────────────────────────────

class SoftLaunchMetrics(BaseModel):
    """Output of HAVEN monitoring the Soft Launch cohort"""
    cohort_size:          int
    day7_retention_rate:  float
    activation_rate:      float
    nps:                  int
    top_complaints:       List[str]
    top_praises:          List[str]
    passed:               bool
    recommendation:       str


# ── Chamber 3: The Market ──────────────────────────────────────

class ProspectProfile(BaseModel):
    name:        str
    company:     str
    role:        str
    pain_point:  str
    outreach_angle: str

class OutreachCampaign(BaseModel):
    """Output of APEX (The Hunter) in full-scale mode"""
    icp_description:  str
    prospects:        List[ProspectProfile]
    email_template:   str
    follow_up_cadence: str

class FeedbackItem(BaseModel):
    source:  str  # "support_email" | "review" | "nps_survey"
    content: str
    sentiment: str  # "positive" | "negative" | "neutral"

class LoopFeedback(BaseModel):
    """Output of HAVEN (The Caretaker) — triggers the Loop"""
    feedback_items:    List[FeedbackItem]
    classification:    LoopClassification
    priority_request:  str
    route_description: str


# ── CEO Dashboard ──────────────────────────────────────────────

class CEODailyReport(BaseModel):
    date:             str
    burn_rate_usd:    float
    revenue_usd:      float
    active_projects:  List[str]
    action_items:     List[str]
    alerts:           List[str]
    chamber_statuses: dict
    summary:          str


# ── Event streaming (for frontend) ────────────────────────────

class AgentEvent(BaseModel):
    """Sent via SSE to the frontend dashboard"""
    event_type:  str   # "agent_start" | "agent_output" | "gate_decision" | "ceo_action" | "error"
    agent_name:  str
    chamber:     str
    status:      AgentStatus
    message:     str
    data:        Optional[dict] = None
    timestamp:   str = Field(default_factory=lambda: datetime.now().isoformat())
