# Frontend Build — PIXEL

Frontend implementation for FlowLock v1. Mobile-first hidden sidebar interface for Reliability Ledger, with zero ambiguous states. Primary UI is a browser extension sidebar that shows execution history and rule status. No traditional pages—sidebar is the main interface. All interactions are sub-200ms with clear loading/error states.

## Files
- src/App.tsx
- src/components/Sidebar.tsx
- src/components/LedgerList.tsx
- src/components/LedgerEntry.tsx
- src/components/StatusIndicator.tsx
- src/components/Button.tsx
- src/hooks/useLedger.ts
- src/utils/api.ts
- src/styles/breakpoints.css

## Notes
1. Hidden sidebar activates via browser extension button—no standalone web app for v1. 2. Ledger entries show rule trigger, action taken, and reliability score with color-coded confidence. 3. Empty state shows 'No executions yet' with link to setup docs. 4. Errors show retry button with specific action ('Retry loading ledger'). 5. Mobile breakpoint at 320px, sidebar becomes full-screen modal. 6. API connections: GET /api/ledger polled every 30s, errors trigger exponential backoff. 7. Slash command setup handled entirely in Linear—no frontend UI for rule creation in v1.