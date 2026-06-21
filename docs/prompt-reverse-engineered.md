# Reverse-Engineered Prompt to Generate SDD Implementation Plan

> Paste this prompt into your AI coding assistant (Claude Code, OpenCode, Cursor, etc.) to regenerate a document like `SDD-personal-finance-bot.md`.

---

## System-Level Instructions

You are a senior DevOps/platform engineer and AI tooling architect. You write clear, executable implementation plans with zero fluff. Every step must include exact bash commands, file contents, configuration snippets, checkpoints, and expected outputs. Assume the reader is a senior engineer comfortable with CLI tools but unfamiliar with this specific stack.

**Constraints:**
- All commands must be copy-paste ready (use `cat > file <<'EOF'...EOF` for file creation)
- Every section ends with a **Checkpoint** line stating what verifies success
- Use absolute paths where applicable, `~` for home, `/path/to/project` as placeholder
- Timeline estimates per phase must be stated
- Include a rollback plan
- Include edge cases and troubleshooting for common failure modes
- Include a time budget summary table
- Include success criteria checklist
- Include a phased adoption recommendation (week 1, week 2, week 3+)

---

## Prompt

Write a comprehensive **SDD (Spec-Driven Development) Stack Implementation Plan** for my project `personal-finance-bot`. The stack integrates these tools into a single end-to-end workflow:

1. **OpenCode** (AI coding CLI, v0.4.0+) — the host agent environment
2. **OMO Slim** (`oh-my-opencode-slim`) — multi-agent configuration and skill management for OpenCode
3. **OpenSpec** (+ `opencode-plugin-openspec`) — spec-as-code proposal → design → apply → archive lifecycle
4. **Superpowers** — skill collection (`brainstorming`, `writing-plans`, `executing-plans`, `requesting-code-review`) that bridges OpenSpec proposals to executable task plans
5. **GSD** (`get-shit-done-cc`) — wave-based parallel task execution with atomic commits
6. **Caveman** (`caveman-skill`) — output token reduction (60-75%) for cost optimization during multi-wave execution
7. **Knowledge Graphs** — `code-review-graph` (CRG, SQLite AST + embeddings, MCP tools) + `graphify` (JSON AST + community detection, CLI) for ~100-token symbol lookup instead of grep+Read
8. **Smart-Grep Hook** — intercepts grep/rg/find, routes through graph first, prevents 1300-2500 token waste

**Target outcome:** Every feature starts as an OpenSpec proposal, gets decomposed into a task plan by Superpowers/Oracle, executes via GSD waves with atomic commits, archives via OpenSpec, and all agents query knowledge graphs instead of reading files.

**The plan must have these phases:**

### Phase 1: Environment & Prerequisites (~30 min)
- Verify OpenCode version (0.4.0+)
- Verify/install OMO Slim globally (`bunx oh-my-opencode-slim@latest install`)
- Backup current OpenCode config (`~/.config/opencode/opencode.json`)
- Validate JSON

### Phase 2: OpenSpec Setup (~45 min)
- Install `openspec` CLI globally via npm/bun
- Install `opencode-plugin-openspec` plugin (Option A: global config plugins array; Option B: project-scoped `.opencode/opencode.json`)
- Initialize OpenSpec in project root (`openspec init`)
- Show resulting `.openspec/config.yaml` with project name, profile, workflows (propose, explore, apply, sync, archive), schemas, tools list, vcs, syncStrategy
- Create initial spec template (`.openspec/feature-name.md`) with phases: PROPOSAL, requirements, design, tasks, status
- Verification: `openspec validate`

### Phase 3: Superpowers Setup (~45 min)
- Verify Superpowers skills exist in OMO Slim (`opencode --list-skills | grep -i superpowers`)
- Full OMO Slim `mixed_up` preset config for `~/.config/opencode/opencode.json`:
  - **orchestrator**: model `opencode-go/deepseek-v4-pro`, skills `["*"]`, mcps `["*", "!context7"]`
  - **oracle**: model `9router/claude-sonnet-combo`, skills: brainstorming, context-engineering, receiving-code-review, requesting-code-review, simplify, systematic-debugging, writing-plans; mcps: code-review-graph, context-mode, gradle-mcp, paper-search-mcp, security-mcp
  - **specsmith** (new agent): model `9router/claude-sonnet-combo`, skills: brainstorming, writing-plans, requesting-code-review, clean-code-principles; mcps: figma, atlassian, context7, websearch
  - **fixer**: model `openai/gpt-5.5`, skills: clean-code-principles, simplify, systematic-debugging, task-decomposition, test-driven-development, verification-before-completion; mcps: adb-mcp, chrome-devtools, code-review-graph, gradle-mcp, security-mcp
- Create `.superpowers.yaml` defining workflow conventions:
  - brainstorming → Product Owner + Architect + QA roles → output to design/
  - writing-plans → Tech Lead + Implementation Lead → phased checklist with file paths
  - executing-plans → Developer + QA → atomic git commits with TDD verification
  - code-review severity levels, blocking rules (CRITICAL, HIGH), red-green-refactor, 80% coverage floor

### Phase 4: GSD + Caveman Setup (~45 min)
- Install GSD (`get-shit-done-cc`) and Caveman globally
- Explain why Caveman: 60-75% token reduction, ~$7,665/year savings on 10,000 API calls/day
- Create `.gsdignore` protecting `.openspec/**`, spec files, `.gsd-context/`, `.gsd-waves/`, `.gsd-commits/`
- Create `.gsd/config.json` with:
  - orchestrator: model `claude-sonnet-4-6`, contextStrategy `minimal-fresh`
  - waves: maxParallel 2, taskTimeout 1800, retryOnFailure true, maxRetries 2
  - context: clearBetweenWaves true, include `.openspec/**` `.codex/**` `ARCHITECTURE.md`
  - commits: atomic true, format `[gsd-wave-{waveId}] {taskName}`, verifyBeforePush true
  - recovery: autoDetectStuckLoops true, stuckLoopTimeout 300, rollbackOnFailure false
- Create `.gsd/agents.json` mapping 5 agent roles (researcher, planner, executor, verifier, debugger) with models, skills, and Caveman settings:
  - executor: Caveman mode `ultra`, 70% reduction
  - verifier: Caveman mode `lite`, 40% reduction

### Phase 4.5: Knowledge Graphs (~45 min)
- Install both tools via `uv tool install graphifyy` and `uv tool install code-review-graph`
- Create `.graphifyignore` and `.code-review-graphignore` (node_modules, dist, build, coverage, logs, env, lock files, etc.)
- First build: `code-review-graph build` and `graphify update .`
- Register with OpenCode: `code-review-graph install` and `graphify claude install`
- Wire auto-update hooks (post-commit, post-checkout) with `_resources_ok()` guard to prevent CPU saturation
- Setup smart-grep hook (PreToolUse intercept for grep/rg/find → graph-first)
- Setup SessionStart cheatsheet hook showing graph query commands and tool names
- Configure CRG_TOOLS env to strip unused tools (8 instead of 25) — saves ~4,200 tokens/session
- Setup Stop hook for CRG incremental update (once per turn, not per file edit)
- Verification: `code-review-graph status`, `graphify query "term"`, test git hook firing
- Include a query patterns reference table: "Where is X defined?" → semantic_search_nodes_tool (~115 tok), "Who calls X?" → query_graph_tool (~80 tok), "What breaks if I change X?" → get_impact_radius_tool (~70 tok), etc.

### Phase 5: Workflow Integration Testing (~45 min)
- Test OpenSpec standalone: `@specsmith propose` creates spec in `.openspec/`
- Test OpenSpec → Superpowers handoff: `@oracle writing-plans` generates task plan with file paths
- Test GSD wave execution: `gsd execute tasks/plan.md` creates 2+ waves, atomic commits with `[gsd-wave-X]` prefix, all tests pass
- Test OpenSpec archive: `openspec apply` then `openspec archive` moves to `.openspec/archive/`
- Test Caveman output: verify code blocks preserved but prose cut 65-75%

### Phase 6: Verification Checklist
- Structured checkbox lists for: OpenSpec layer (4 items), Superpowers layer (3 items), GSD layer (5 items), OMO Slim integration (4 items), End-to-end workflow (5 items), Knowledge Graphs (8 items)

### Phase 7: Edge Cases & Troubleshooting
Cover these specific scenarios with symptom, root cause, and fix:
- GSD detects stuck loop (300s timeout)
- OpenSpec proposal mutated by GSD (missing .gsdignore entry)
- Superpowers plan too coarse-grained (15 parallel tasks → OOM)
- OMO Slim skill collision (duplicate skill across agents)
- Caveman output too sparse for debugging (mode toggle: ultra/lite/off)
- Knowledge Graph edge cases:
  - CRG incremental update lag after large refactor (>150 files)
  - graphify update timeout (>300s on large monorepo)
  - Smart-grep hook not firing (permission or config issue)
  - CRG embeddings not updating (Stop hook runs update without embed)
  - graphify BFS timeout (>10s, memory limit)
  - CRG database corruption after crash (WAL file out of sync)

### Phase 8: Day-1 Workflow
- Full end-to-end feature workflow in ~7 steps: community exploration → propose → plan → pre-execution graph analysis → execute → code review with graph context → archive
- Graph query commands for daily use (7 common patterns)
- Include a Rollback Plan: `git reset --soft HEAD~10`, remove `.gsd` `.openspec` `.superpowers.yaml`, restore config backup

**Additional sections required:**
- **Time Budget Recap** table (8 rows, phase name + duration + status)
- **Phased Adoption Recommendation** (Week 1: phases 1-2; Week 2: phases 3-4; Week 3+: full workflow)
- **Success Criteria** (5 items: spec-first mindset, traceable design, atomic execution, living specs, zero drift)
- **Context Notes** specific to the project (e.g., Portfolio feature as ideal SDD test case, Android builds with gradle-mcp, mid-year review deadline, Caveman cost justification, knowledge graph token savings math)
- **System-Level Risk** section: concurrent background processes from post-commit + post-checkout hooks causing CPU saturation (load average 12+), with mitigation (resource guards, pgrep, timeout, nohup) and residual gap (killing processes on low-resource machines)

**Formatting rules:**
- Use `## Phase X:` for phase headers
- Use `### X.Y` for subsections
- **Bold** checkpoint indicators
- Inline code for commands, file paths, config keys
- Fenced code blocks with language tags for bash, json, yaml, markdown
- Horizontal rules (`---`) between major sections
- Reference URLs where appropriate (e.g., Dev.to article for full hook scripts)
- Practical, not theoretical — every command should work as written

**Tone:** Direct, instructional, no flattery, no "great question." Assume the reader is a busy senior engineer who wants the fast path to production.
