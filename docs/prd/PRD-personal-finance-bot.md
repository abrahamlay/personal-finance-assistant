# PRD: Personal Finance Bot

**Version:** 1.0  
**Status:** Draft  
**Author:** Product Owner  
**Date:** 2026-06-21  
**Target Launch:** Mid-Year Review (Q2 2026)

---

## 1. Executive Summary

Personal Finance Bot is a conversational AI assistant that helps retail investors track, organize, and review their investment portfolio through natural language interaction. Users query their holdings, reorder portfolio sections, generate mid-year summaries, and receive actionable insights — all through a chat interface.

The bot targets users who find traditional portfolio dashboards overwhelming and prefer conversational, guided interactions for financial review and planning.

---

## 2. Problem Statement

### 2.1 Current Pain Points

| Pain Point | Impact |
|---|---|
| Portfolio dashboards are dense and information-heavy | Users miss key signals; review takes hours |
| Section ordering is rigid or unintuitive | Users can't prioritize what matters to their strategy |
| Mid-year review requires manual data aggregation | Time-consuming; prone to error; inconsistent |
| No conversational entry point for portfolio questions | Users resort to spreadsheets or multiple apps |
| No shared source of truth for portfolio state | Confusion between broker data, spreadsheet, and mental model |

### 2.2 Target Users

| Persona | Need |
|---|---|
| **Retail Investor (Primary)** | Quick answers: "How did my tech stocks do this quarter?" |
| **Self-Directed Trader** | Reorder sections by strategy (e.g., dividend-first, growth-first) |
| **Casual Reviewer** | Mid-year snapshot without logging into brokerage |
| **Financial Coach (Secondary)** | Guided review prompts for client portfolio walkthroughs |

---

## 3. Product Vision

> *"A conversational portfolio companion that makes mid-year review feel like a guided conversation, not a spreadsheet audit."*

**North Star Metric:** Time from question → actionable portfolio insight **under 30 seconds**.

---

## 4. Core Features (Phased)

### Phase 1 — Portfolio Foundation (MVP)
**Goal:** Answer basic portfolio questions via chat.

| ID | Feature | Description | Priority |
|---|---|---|---|
| F1.1 | Portfolio Import | Connect brokerage account or CSV upload to ingest holdings | P0 |
| F1.2 | Natural Language Query | "What's my top performer this year?" returns ranked list | P0 |
| F1.3 | Asset Categorization | Auto-tag holdings by sector, asset class, risk tier | P0 |
| F1.4 | Performance Summary | YTD, 1Y, and inception returns per holding | P0 |

### Phase 2 — Drawer & Section Ordering
**Goal:** Let users customize how portfolio data is presented.

| ID | Feature | Description | Priority |
|---|---|---|---|
| F2.1 | Portfolio Drawer | Expandable navigation drawer listing all sections | P1 |
| F2.2 | Section Reordering | Drag-and-drop or command-based section reordering | P1 |
| F2.3 | Preserve Order Invariant | Section order persists across sessions and devices | P1 |
| F2.4 | Default Templates | Pre-built orderings: "Dividend Focus," "Growth Focus," "Risk-First" | P2 |

### Phase 3 — Mid-Year Review
**Goal:** Guided mid-year portfolio review experience.

| ID | Feature | Description | Priority |
|---|---|---|---|
| F3.1 | Review Wizard | Step-by-step conversational review flow | P1 |
| F3.2 | Auto-Generated Summary | One-page H1 performance + allocation summary | P1 |
| F3.3 | Tax-Loss Harvesting Hints | Flag positions with unrealized losses for TLH consideration | P2 |
| F3.4 | Rebalancing Suggestions | Compare current vs. target allocation; suggest trades | P2 |
| F3.5 | Export Report | PDF/Markdown export of review summary | P2 |

### Phase 4 — Insights & Proactive
**Goal:** The bot surfaces insights before the user asks.

| ID | Feature | Description | Priority |
|---|---|---|---|
| F4.1 | Anomaly Detection | Alert on unusual price movements or volume spikes | P3 |
| F4.2 | Dividend Calendar | Upcoming dividend dates and estimated payouts | P3 |
| F4.3 | News Correlation | Link portfolio holdings to relevant news events | P3 |

---

## 5. User Stories (Key)

### Portfolio Drawer Section Ordering (Feature F2.1–F2.3)

```
As a self-directed investor
I want to reorder my portfolio drawer sections
So that my investment strategy (e.g., dividend-first) is reflected in how data is presented.

Acceptance Criteria:
- [ ] Drawer shows all portfolio sections (Holdings, Performance, Allocation, Dividends, News)
- [ ] User can reorder sections via drag-and-drop (desktop) or long-press (mobile)
- [ ] Section order persists after app restart and across logged-in devices
- [ ] Default order restorable with one action
- [ ] Order is invariant: the same user always sees the same order until they change it
```

### Mid-Year Review Wizard (Feature F3.1)

```
As a casual investor
I want a guided mid-year review conversation
So that I understand my portfolio health without analyzing spreadsheets.

Acceptance Criteria:
- [ ] Bot initiates review with a greeting and summary prompt
- [ ] Walks through: Performance → Allocation → Dividends → Tax Considerations
- [ ] Each step presents data + asks one follow-up question
- [ ] Generates a shareable summary at the end
- [ ] Review can be paused and resumed
```

### Natural Language Query (Feature F1.2)

```
As a retail investor
I want to ask natural language questions about my portfolio
So that I get answers without navigating complex dashboards.

Acceptance Criteria:
- [ ] Supports: "How did X perform?", "What's my biggest holding?", "Show me my dividend stocks"
- [ ] Response under 5 seconds for typical queries
- [ ] Handles ambiguous queries with clarifying follow-ups
- [ ] Supports date-range filters ("this quarter," "since January")
```

---

## 6. Non-Functional Requirements

| Category | Requirement | Target |
|---|---|---|
| **Performance** | Query response time | <5s p95 for NL queries |
| **Performance** | Portfolio data refresh | ≤15min staleness for live-connected accounts |
| **Reliability** | Uptime | 99.5% (non-market-hours tolerated) |
| **Security** | Data at rest | AES-256 encryption |
| **Security** | Data in transit | TLS 1.3 |
| **Security** | Credential storage | Never store brokerage passwords; OAuth-only |
| **Accessibility** | Chat interface | WCAG 2.1 AA compliant |
| **Data Integrity** | Section order persistence | Order invariant guaranteed across sessions |
| **Scalability** | Concurrent users | Support 10,000 concurrent chat sessions |
| **Test Coverage** | Code coverage floor | ≥80% (per SDD TDD requirements) |

---

## 7. Success Metrics

| Metric | Baseline | Target (6 months) |
|---|---|---|
| Monthly Active Users (MAU) | 0 | 5,000 |
| Query-to-Insight Time | N/A | <30 seconds |
| Mid-Year Review Completion Rate | N/A | >70% |
| Section Order Customization Rate | N/A | >40% of users customize at least once |
| User Satisfaction (CSAT) | N/A | ≥4.2 / 5 |
| Data Freshness Complaints | N/A | <2% of support tickets |
| Token Cost per Session | N/A | ≤$0.15 average (Caveman-optimized) |

---

## 8. Out of Scope (v1)

| Item | Reason | When |
|---|---|---|
| Trade execution | Brokerage integration complexity; regulatory risk | v2+ |
| Multi-currency support | Scope; target USD-only initially | v2 |
| Social/sharing features | Not core to review workflow | v3 |
| Robo-advisor recommendations | Requires fiduciary compliance | v3+ |
| Real-time streaming prices | Cost; 15min delay acceptable for review use case | v2 |
| Tax filing integration | Export-only at first | v2 |

---

## 9. Architecture Principles (from SDD)

These principles are codified in the SDD and constrain all implementation:

1. **Spec-First Development:** Every feature starts as an OpenSpec proposal before code is written.
2. **Traceable Design:** Each task plan traces back to one spec requirement (this PRD).
3. **Atomic Execution:** Each task = one git commit with passing tests.
4. **Living Specs:** Archive is current; no specs linger in PROPOSAL state.
5. **Zero Drift:** Code always matches latest spec; specs never surprise QA.
6. **Graph-First Navigation:** Knowledge graphs (CRG + graphify) are the primary codebase exploration tool, not grep.
7. **Token Efficiency:** Caveman skill on all execution agents; target 65-75% output token reduction.

---

## 10. Development Phases (Aligned with SDD)

| Dev Phase | Contents | Duration |
|---|---|---|
| **Setup** | OpenSpec + Superpowers + GSD + Knowledge Graphs stack | ~5 hours |
| **MVP (Phase 1)** | Portfolio Import + NL Query + Categorization + Performance | 2 weeks |
| **UX (Phase 2)** | Drawer + Section Ordering + Templates | 2 weeks |
| **Review (Phase 3)** | Mid-Year Wizard + Summary + Export | 2 weeks |
| **Insights (Phase 4)** | Anomalies + Dividends + News | 3 weeks |

### Current Milestone: SDD Stack Setup (In Progress)
- [x] PRD drafted (this document)
- [ ] Phase 1: Environment & Prerequisites
- [ ] Phase 2: OpenSpec Setup
- [ ] Phase 3: Superpowers Setup
- [ ] Phase 4: GSD + Caveman + Knowledge Graphs
- [ ] Phase 5: Workflow Integration Tests
- [ ] Phase 6: Verification Checklist Complete

---

## 11. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Brokerage API rate limits / changes | Medium | High | Cache aggressively; support CSV fallback |
| AI hallucination on financial data | Medium | Critical | Source-of-truth anchoring; never generate numbers |
| Section order data corruption | Low | High | Order invariant tests; CRC checks on persistence |
| OAuth token expiry mid-review | Medium | Medium | Proactive refresh; graceful session recovery |
| Knowledge graph rebuild storms | Low | Medium | Resource guards in post-commit hooks (per SDD §7.6) |

---

## 12. Glossary

| Term | Definition |
|---|---|
| **Drawer** | Expandable side navigation listing portfolio sections |
| **Section Order Invariant** | Guarantee that a user's section order is preserved exactly across all sessions |
| **NL Query** | Natural Language Query — user asks in plain English |
| **SDD** | Spec-Driven Development — the workflow documented in `SDD-personal-finance-bot.md` |
| **GSD** | Get Shit Done — wave-based task execution framework |
| **CRG** | Code-Review-Graph — AST knowledge graph for codebase navigation |
| **Caveman** | Token optimization skill that reduces verbose output while preserving code accuracy |

---

## 13. References

- **SDD Stack Implementation Plan:** `SDD-personal-finance-bot.md` (project root)
- **OpenSpec Workflow:** `.openspec/config.yaml` (post-setup)
- **Superpowers Conventions:** `.superpowers.yaml` (post-setup)
- **GSD Configuration:** `.gsd/config.json` (post-setup)
- **Knowledge Graph Setup:** Dev.to article linked in SDD §4.5

---

*This PRD is the authoritative source of product requirements. All OpenSpec proposals, Superpowers task plans, and GSD execution waves must trace back to feature IDs defined in Section 4. Any deviation requires a PRD amendment before implementation.*
