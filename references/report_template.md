# Cross-Check Review Report Format (The Golden Balance)

Goal: Emit a **dense, structured Markdown report** that a human reviewer can scan in **3 to 5 seconds** and an agent can parse and execute deterministically. No JSON clutter, no verbose essays.

---

## 🌐 Dynamic Localization Rules

- **Match User Language**: The report's human-facing prose, section headers, explanations, and next-action prompt must automatically match the **language of the user's prompt** (e.g., Korean if prompted in Korean, English if prompted in English, etc.).
- **Keep Technical Tokens Invariant**: Never translate machine tokens, code symbols, or file paths:
  - Verdicts: `BLOCKED`, `CONDITIONAL PASS`, `PASS`
  - Confidence: `[HIGH]`, `[MEDIUM]`, `[LOW]`
  - Tags: `leak:`, `race:`, `npe:`, `caller:`, `sec:`, `swallow:`, `yagni:`, `shrink:`, `stdlib:`
  - File paths, line numbers, function signatures, code snippets.

---

## 📋 Standard Output Shape

```markdown
# 🛡️ Cross-Check Review

- **Verdict**: [ 🔴 BLOCKED | 🟡 CONDITIONAL PASS | 🟢 PASS ]
- **Summary**: <1 sentence in user's language — the single most important takeaway>
- **Scope**: `<target desc>` (N file(s) audited)

---

### 🚨 Actionable Findings

1. **[HIGH] <tag>** (`<filepath>:<line>`)
   - **Issue**: <1 line — what is broken and the concrete failure path>
   - **Why**: <1 line — causal chain and proof why this causes a crash, leak, or vulnerability (required for MEDIUM+)>
   - **Fix**: <1 line — minimal, conservative, rock-solid fix>
   - **Trace**: `<optional pointer to caller site or probe that demonstrates it>`

2. **[MEDIUM] <tag>** (`<filepath>:<line>`)
   - **Issue**: <1 line — edge case, contract drift, or unhandled condition>
   - **Why**: <1 line — causal chain>
   - **Fix**: <1 line — conservative fix>

3. **[LOW] <tag>** (`<filepath>:<line>`)
   - **Issue**: <1 line — minor observation, YAGNI simplification, or style defect>
   - **Fix**: <1 line — simplified alternative>

---

👉 **Next Step**: <Natural prompt in user's language asking which finding to fix (e.g. "Tell me which numbers to fix like 'Fix #1', or say 'looks good, merge' if intended.")>
```

---

## 🟢 Clean / Zero-Findings Case

If verdict is **🟢 PASS** and there are **zero findings**, omit the Findings section entirely and output:

```markdown
# 🛡️ Cross-Check Review

- **Verdict**: 🟢 PASS
- **Scope**: `<target desc>` (N file(s) audited)

Solid & Lean. Clean to ship.

👉 **Next Step**: <Ready to merge. Say "proceed to merge" or let me know if you want to inspect specific files.>
```

---

## 🎯 Field Guidelines for Findings

1. **Confidence (`[HIGH]`, `[MEDIUM]`, `[LOW]`)**:
   - `[HIGH]`: Deterministic crash, leak, race, security flaw, or caller contract break on production path. (Always flips verdict to 🔴 BLOCKED).
   - `[MEDIUM]`: Strong evidence of an edge-case bug, concurrency risk, or unhandled contract drift. (Flips verdict to 🟡 CONDITIONAL PASS).
   - `[LOW]`: Plausible observation, YAGNI over-engineering, or simplification. Never blocks alone.
2. **Issue**: One crisp sentence naming the concrete defect and its direct impact.
3. **Why (Required for MEDIUM and HIGH)**: Explains the causal chain (e.g. "Caller `Foo.java:45` calls this without null check, expecting non-null return"). This ensures the agent fixes the issue with full comprehension rather than blind text replacement.
4. **Fix**: The most conservative, minimal, battle-tested fix.
5. **Trace**: Optional short pointer (caller file:line, symbol, or probe) to reproduce/verify.

---

## 🔍 On-Demand Deep Dive (Optional)

Do **NOT** dump full diffs, code blocks, or evidence essays by default.  
Only if the user explicitly asks for details (e.g., *"Show details for #1"*, *"Why does #2 fail?"*), expand finding N to show:
- Exact vulnerable code snippet
- Exact recommended replacement snippet
- Detailed caller blast-radius trace
