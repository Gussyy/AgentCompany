# Outreach Campaign

## ICP
Security Engineer or Security Lead at a mid-market SaaS company (100-1000 employees, $10M-$100M revenue) with 10+ SaaS integrations. They manage identity and access management but lack visibility into third-party API permissions and non-human identities. They've experienced or fear shadow IT integrations, have compliance requirements (SOC2, ISO27001), and spend hours manually auditing vendor permissions. They value automation over manual processes and need to demonstrate security posture to leadership.

## Prospects
### Alex Rivera — Security Engineer @ DataFlow Analytics
- Pain: Manual audit of 30+ SaaS integrations for SOC2 compliance took 3 weeks last quarter
- Angle: Reference their SOC2 audit timeline mentioned in their company blog post about security improvements
### Maya Patel — Head of Security @ CloudSync Inc
- Pain: Recent security incident involving a compromised service account from a marketing automation tool
- Angle: Reference their LinkedIn post about implementing stricter access controls after the incident
### James Kim — Security Operations Lead @ RevTrack SaaS
- Pain: Difficulty tracking which departments are connecting which tools via OAuth without oversight
- Angle: Reference their comment on a Reddit thread about shadow IT challenges in scaling SaaS companies
### Sophia Williams — Security Engineer @ AppLaunch Platform
- Pain: Time-consuming manual review of GitHub app permissions across engineering teams
- Angle: Reference their GitHub repository where they built a basic script to audit OAuth apps
### David Chen — CISO @ CustomerIQ
- Pain: Board asking for visibility into third-party risk from SaaS integrations
- Angle: Reference their interview on a security podcast where they discussed third-party risk management challenges

## Email Template
```
Subject: Reducing third-party permission risk at {{company}}

Hi {{first_name}},

I noticed {{specific_fact}} and thought about how Identity Lens could help.

For security teams at SaaS companies like yours, Identity Lens automatically discovers and visualizes the risk of non-human identities and API permissions across all your SaaS-to-SaaS integrations.

Instead of manually auditing each vendor's admin console, you get a complete permissions graph showing:
- Which third-party integrations have excessive API permissions
- Non-human service accounts that could be compromised
- Risk visualization without logs or user behavior analysis

Would 15 minutes on Thursday make sense to show how this works with your current stack?

Best,
APEX
Head of Growth & Acquisition
AgentCompany
```

## Follow-up Cadence
Day 3: Share a relevant case study of a similar company reducing audit time by 80%. Day 7: Send a visualization example of what their permissions graph might look like. Day 14: Offer a limited-time pilot to test with one SaaS connector (GitHub or Slack).