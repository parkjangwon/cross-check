<p align="center">
  <img src="assets/banner.jpg" alt="cross-check banner" width="100%">
</p>

# 🛡️ cross-check

> **Fast, conservative diff gatekeeper for AI coding agents.**  
> Catches leaks, crashes, deadlocks, caller blast radius, and AI over-engineering before you merge.

Compatible with **Claude Code**, **Codex**, **Antigravity**, and any Agent Skills-enabled tool.

---

## 💡 When to Use

Coding agents write code fast, but in enterprise/on-premise environments, subtle bugs cause critical incidents. Use `cross-check` right after an agent finishes coding, before your own review or merge:

- **Pre-Merge / Pre-Commit Check**: Catch latent bugs humans easily miss in secondary reviews.
- **Resource Leak & Crash Defense**: Detect unclosed connections/FDs, goroutine/thread leaks, NPEs, and panic paths.
- **Concurrency Hazards**: Identify data races, non-atomic mutations, and lock deadlocks.
- **Blast Radius Check**: Verify existing callers aren't broken by changed return types or nullability contracts.
- **AI Sanity Check (YAGNI)**: Strip away speculative abstractions, bloated dependencies, and over-engineered boilerplate.

---

## 📦 Quick Install

### Via `skills.sh` (Recommended)
```bash
npx skills add parkjangwon/cross-check -g
```

### Manual Symlink
```bash
# Claude Code
ln -s /path/to/cross-check ~/.claude/skills/cross-check

# Antigravity (AGY)
ln -s /path/to/cross-check ~/.gemini/antigravity/skills/cross-check
```

---

## 💬 How to Use

Just ask your AI agent naturally in **English**, **Korean**, or your preferred language:

```text
"Cross-check my changes before I merge."
"방금 작업한 거 머지하기 전에 장애 유발 요소나 오버엔지니어링 크로스체크해줘."
"Audit staged changes against enterprise safety invariants."
```

The agent automatically extracts diffs, analyzes caller blast radius, and produces a **Golden Balance** report — scannable in 3 seconds by you, immediately actionable by the agent.

---

## 📊 Sample Report

```markdown
# 🛡️ Cross-Check Review

- **Verdict**: 🔴 BLOCKED
- **Summary**: Session map concurrent write causes daemon panic; token timeout returns null causing caller NPE.
- **Scope**: Working Tree (2 files audited)

---

### 🚨 Actionable Findings

1. **[HIGH] race:concurrent-map-write** (`session_manager.go:42`)
   - **Issue**: Concurrent write to activeSessions map triggers Go runtime fatal panic.
   - **Why**: Mutated across HTTP goroutines without synchronization; crashes under load.
   - **Fix**: Wrap map accesses with `sync.RWMutex`.

2. **[MEDIUM] caller:nullable-drift** (`AuthService.java:89`)
   - **Issue**: Token validation now returns null on timeout.
   - **Why**: Caller `SecurityFilter.java:45` calls `token.isValid()` without null check.
   - **Fix**: Return `false` instead of `null` on timeout.

3. **[LOW] yagni:single-impl-wrapper** (`RuleEngine.ts:12`)
   - **Issue**: AbstractRuleEngine has only one implementation.
   - **Fix**: Inline the class unless plugin extension is imminent.

---

👉 **Next Step**: Tell me which finding(s) to fix (e.g. "Fix #1 and #2"), or say "proceed to merge" if intended.
```

> 🌐 **Dynamic Localization**: Technical verdicts (`BLOCKED`, `PASS`) and tags (`race:`, `leak:`) remain uniform, while explanations and next steps match your conversational language.

---

## 🧭 What It Audits (7 Invariants)

| Tag | Category | What It Guards Against |
| :--- | :--- | :--- |
| `leak:` | **Resource Lifecycle** | FD, socket, DB connection, thread/goroutine, context leaks |
| `race:` | **Concurrency** | Shared mutable state, race conditions, TOCTOU, deadlocks |
| `npe:` / `crash:` | **Boundary Safety** | Null/nil dereference, bounds error, unsafe cast, panic paths |
| `caller:` | **Blast Radius** | Return type, nullability, or error contract drift at call sites |
| `swallow:` | **Error Integrity** | Ignored errors, silent drops, broken rollback/cleanup paths |
| `sec:` | **Trust Boundary** | Injection, path traversal, auth/authz bypass, secret exposure |
| `yagni:` | **Minimalism** | AI-generated speculative boilerplate, unnecessary layers |

- **🔴 BLOCKED**: High-confidence crash, leak, race, security, or caller-breaking bug.
- **🟡 CONDITIONAL PASS**: Credible medium-risk defect.
- **🟢 PASS**: Safe to proceed. (Low & YAGNI items never block alone).

---

## 📜 License
MIT
