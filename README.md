<p align="center">
  <img src="assets/banner.jpg" alt="cross-check banner" width="100%">
</p>

# 🛡️ cross-check

> **Laser-focused, diff-scoped gatekeeper for enterprise stability, security, and YAGNI.**  
> Built for Claude Code, Codex, Antigravity, and any Agent Skills-compatible AI assistant.

---

## ⚡ Why Cross-Check?

In enterprise software deployed on-premise, defects cannot be silently hot-reloaded. A single memory leak, unhandled panic, or authorization bypass triggers emergency on-site engineering missions and compliance audit escalations.

AI vibe-coding produces plausible code, but routinely introduces:
- **Silent Resource Leaks**: Unclosed file descriptors, sockets, database connections, and background coroutines/listeners.
- **Concurrency Hazards**: Data races on shared mutable state and lock-order deadlocks.
- **Swallowed Errors**: Empty catch/error blocks and lost transaction rollbacks.
- **Over-Engineering Bloat**: AI-generated design patterns, single-implementation interfaces, and unneeded dependencies for trivial tasks.

**`cross-check` is not a full-scan SAST.** It performs a fast, conservative audit strictly on your **`git diff`** and its external caller sites against **7 Universal Enterprise Invariants**.

---

## 📦 Quick Install

### Via `skills.sh` (Recommended)
```bash
npx skills add parkjangwon/cross-check -g
```

### Manual Symlink
```bash
# Claude Code (Global)
mkdir -p ~/.claude/skills
ln -s /path/to/cross-check ~/.claude/skills/cross-check

# Antigravity (AGY)
mkdir -p ~/.gemini/antigravity/skills
ln -s /path/to/cross-check ~/.gemini/antigravity/skills/cross-check
```

---

## 🧭 The 7 Universal Invariants

| Tag | Category | What We Catch |
| :--- | :--- | :--- |
| `leak:` | **Resource Lifecycle** | FD, socket, DB connection, thread/goroutine, or listener leaks on any exit path. |
| `race:` | **Concurrency** | Unprotected shared state, non-atomic updates, lock contention during I/O. |
| `npe:` / `crash:` | **Memory & Pointer** | Null/nil dereferences, array out-of-bounds, unsafe unboxing, raw casts. |
| `caller:` | **Blast Radius** | Caller contract drift, unhandled null returns or uncaught errors at call sites. |
| `swallow:` | **Error Integrity** | Silently ignored exceptions, lost root-cause traces, missing transaction rollbacks. |
| `sec:` | **Trust Boundary** | SQL/command injection, path traversal, hardcoded secrets, plain PII in logs. |
| `yagni:` | **Over-Engineering** | Single-impl interfaces, premature design patterns, unnecessary dependencies. |

---

## 📊 Sample Output

Review reports are dense, tagged, and actionable:

```markdown
# 🛡️ Cross-Check Security & Stability Review

- **Target Scope**: Working Tree (staged + unstaged)
- **Audited Files**: 2 files
- **Scoreboard**: 🚨 1 Critical | ⚠️ 1 Warning | 🧹 1 YAGNI | net: -45 lines possible
- **Verdict**: 🔴 BLOCKED

---

## ⚡ Quick Scan (One-Line Tagged Findings)
- `session_manager.go:L42: race: concurrent write to activeSessions map. Protect with sync.RWMutex.`
- `SecurityService.java:L80: swallow: catch(Exception e) ignores error. Re-throw or ensure rollback.`
- `AuthRuleEngine.ts:L12-70: yagni: AbstractRuleEngine with 1 impl. Inline directly, delete 40 lines.`

---

## 🚨 Critical Issues
### 1. [session_manager.go:L42] Concurrent Map Write Panic
- **Blast Radius**: High concurrent traffic triggers Go runtime panic (`fatal error: concurrent map writes`), crashing the on-premise daemon.
- **Conservative Fix**:
```go
m.mu.Lock()
m.activeSessions[id] = session
m.mu.Unlock()
```
```

---

## 💬 Usage

Ask your agent naturally in English or Korean:

- *"Cross-check my uncommitted code for crash risks, leaks, and over-engineering."*
- *"Audit staged changes against enterprise invariants."*
- *"Cross-check commit `a1b2c3d` before merging."*
- *(한국어: "방금 수정한 코드 장애 유발 요인이랑 오버엔지니어링 크로스체크해줘.")*

---

## 🛠️ Standalone CLI (`get_diff_context.py`)

Extract token-efficient, noise-free diffs directly in your terminal:

```bash
# Working tree changes (auto-detects untracked files, excludes lockfiles & binaries)
python3 scripts/get_diff_context.py

# Staged only
python3 scripts/get_diff_context.py --staged

# Specific commit or range
python3 scripts/get_diff_context.py --commit <HASH>
python3 scripts/get_diff_context.py --range main..HEAD
```

---

## 📜 License
MIT
