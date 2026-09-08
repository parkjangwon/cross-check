# Cross-Check Review Report Format

Review responses must avoid generic filler prose and follow this standardized, high-density reporting template.

---

```markdown
# 🛡️ Cross-Check Security & Stability Review

- **Target Scope**: [Working Tree | Staged | Commit <hash> | Range <base>..<head>]
- **Audited Files**: N file(s)
- **Scoreboard**: 🚨 [X] Critical | ⚠️ [Y] Warning | 🧹 [Z] YAGNI | net: [-N lines possible]
- **Verdict**: [ 🔴 BLOCKED | 🟡 CONDITIONAL PASS | 🟢 PASS (Solid & Lean. Clean to ship.) ]

---

## ⚡ Quick Scan (One-Line Tagged Findings)
> Format: `<file>:L<line>: <tag> <what's wrong>. <immediate fix>.`

- `SecurityManager.java:L42-55: leak: InputStream not closed on IOException. try-with-resources, 1 line.`
- `auth_service.go:L78: race: concurrent write to session map without mutex. sync.RWMutex or sync.Map.`
- `AuthFilter.java:L89: caller: calls validateToken() which now returns null on timeout. NPE at caller L91.`
- `UserDataHandler.ts:L110: npe: blind unboxing without null check. Guard before property access.`
- `ConfigLoader.py:L35: swallow: except Exception ignores error. Log cause and propagate or rollback.`
- `RuleEngine.java:L12-70: yagni: AbstractRuleEngine with 1 impl. Inline directly, delete 40 lines.`

---

## 🚨 Critical Issues (Must Fix before Merge/Release)
(If none detected: "None detected. No crash or leak risks found.")

### 1. [filepath:line] Concise Issue Title
- **Cause & Blast Radius**: Detailed scenario explaining why this causes crashes, leaks, or exploits in production.
- **Vulnerable Code**:
```[language]
// Problematic original code snippet
```
- **Conservative Fix**:
```[language]
// Rock-solid, minimal, conservative fix
```

---

## ⚠️ Warning Issues (High Risk / Edge Cases)
(Edge conditions, potential NPE/nil dereferences, incomplete error handling, subtle concurrency risks)

---

## 🧹 Over-Engineering & YAGNI Findings
(Unnecessary wrappers, single-impl interfaces, redundant abstractions, code to be deleted or simplified)

---

## 💡 Net Impact & Verdict Summary
- **Net code change**: `-<N> lines` (if simplifications are applied)
- **Bottom line**: [Final verdict in 1 clear sentence]
```
