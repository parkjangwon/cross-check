# Cross-Check Review Report Format

Review responses must be concise, evidence-based, and actionable. Do not manufacture certainty.

```markdown
# 🛡️ Cross-Check Security & Stability Review

- **Target Scope**: [Working Tree | Staged | Commit <hash> | Range <base>..<head>]
- **Audited Files**: N file(s)
- **Scoreboard**: 🚨 [X] Critical | ⚠️ [Y] Warning | 🧹 [Z] YAGNI | net: [-N lines possible]
- **Confidence**: HIGH [X] | MEDIUM [Y] | LOW [Z]
- **Verdict**: [ 🔴 BLOCKED | 🟡 CONDITIONAL PASS | 🟢 PASS ]

---

## ⚡ Quick Scan

> Format: `<file>:L<line>: <tag> [HIGH|MEDIUM|LOW] <what's wrong>. <immediate fix>.`

- `SecurityManager.java:L42-55: leak: [HIGH] InputStream escapes without deterministic close on error. Use try-with-resources.`
- `AuthService.java:L89: caller: [MEDIUM] timeout now returns null; caller L91 dereferences it. Guard or preserve the previous contract.`
- `RuleEngine.java:L12-70: yagni: [LOW] abstraction appears to have one consumer. Verify DI/test/plugin boundary before removing.`

If clean:
`None. All diff hunks pass safety standards.`

---

## 🚨 Critical Issues

(Only HIGH-confidence production-significant blockers belong here.)

### 1. [filepath:line] Concise Issue Title
- **Confidence**: HIGH
- **Cause & Blast Radius**: Concrete execution path and affected callers/users/resources.
- **Evidence**: Why the diff/context establishes the defect.
- **Vulnerable Code**:
```[language]
// Problematic code
```
- **Conservative Fix**:
```[language]
// Minimal safe fix
```

If none: `None detected.`

---

## ⚠️ Warning Issues

Include MEDIUM-confidence credible risks and HIGH-confidence issues that do not meet the blocking threshold. LOW-confidence concerns should be clearly labeled and should not block the verdict.

### 1. [filepath:line] Concise Issue Title
- **Confidence**: MEDIUM
- **Risk**: Concrete edge case or operational consequence.
- **Why not proven**: Missing runtime/framework/semantic evidence.
- **Recommendation**: Minimal validation or conservative fix.

---

## 🧹 Over-Engineering & YAGNI Findings

YAGNI is advisory unless it creates a concrete correctness/security/operational risk.

- `[filepath:line] yagni: [LOW] ...`
- `[filepath:line] stdlib: [MEDIUM] ...`

Do not recommend deleting abstractions solely because they currently have one implementation. Check DI, testing seams, framework contracts, plugin boundaries, and domain ownership.

---

## 🎯 Caller & Blast-Radius Notes

- **Changed contracts**: [None | concise list]
- **Caller evidence**: [direct callers inspected / textual candidates only / semantic tooling unavailable]
- **Sibling paths checked**: [Yes/No + reason]

---

## 💡 Net Impact & Verdict Summary

- **Net code change**: `-<N> lines` (only if a concrete simplification is recommended)
- **Bottom line**: [One clear sentence explaining why the verdict is PASS, CONDITIONAL PASS, or BLOCKED.]

### Verdict Rules
- 🔴 BLOCKED = HIGH-confidence production-significant security, crash, leak, race/deadlock, data-corruption, or caller-contract defect.
- 🟡 CONDITIONAL PASS = no HIGH blocker, but a credible MEDIUM-confidence safety/security/stability/contract risk remains.
- 🟢 PASS = no HIGH/MEDIUM safety or security findings; LOW and subjective style findings do not block.

If there are no issues: **Solid & Lean. Clean to ship.**
```
