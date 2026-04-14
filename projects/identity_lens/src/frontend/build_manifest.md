# Frontend Build — PIXEL

Mobile-first React/TypeScript frontend for Identity Lens v1. Zero ambiguous states: skeleton loaders, inline error recovery, empty state CTAs. State managed via React Query for server state + Zustand for UI state. D3 force-directed graph with mobile-optimized touch interactions. All API calls wrapped in custom hooks with automatic retry/error handling.

## Files
- src/App.tsx
- src/pages/Dashboard.tsx
- src/components/Button.tsx
- src/pages/Connections.tsx
- src/pages/Visualization.tsx
- src/pages/NonHumanIdentities.tsx
- src/pages/Reports.tsx
- src/components/ConnectionCard.tsx
- src/components/GraphVisualization.tsx
- src/components/EmptyState.tsx
- src/components/ErrorBoundary.tsx
- src/hooks/useConnections.ts
- src/hooks/useGraphData.ts
- src/hooks/useNonHumanIdentities.ts
- src/hooks/useReports.ts
- src/lib/api.ts
- src/store/uiStore.ts

## Notes
Mobile breakpoints: <640px (mobile), 640-1024px (tablet), >1024px (desktop). All primary actions have visual feedback within 200ms. PDF generation shows progress bar with ETA. Graph visualization has mobile tap-to-expand nodes. Every error state has 'Try again' or 'Contact support' CTA. OAuth flow opens in popup with heartbeat polling to detect completion.