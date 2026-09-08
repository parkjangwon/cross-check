# Cross-Check Review Report Format (minimal, JSON-core)

Goal: emit a **short, parseable, decision-ready** report. Every review ends with
an explicit next-action gate so the human only answers one short prompt instead
of reading a wall of prose. Effort goes into the *findings*, not the prose.

## Localization Rules

- Human-facing prose is in the user's language; keep code/paths/identifiers and
  machine tokens (`BLOCKED`/`CONDITIONAL PASS`/`PASS`, `HIGH`/`MEDIUM`/`LOW`,
  tags like `leak:` `sec:` `caller:`) as-is. No translation subsystem.
- Localization never changes findings, verdict, or confidence.

## Output shape (STOP after these three blocks; no filler)

```markdown
## 💬 Verdict
**Verdict**: 🔴 BLOCKED | 🟡 CONDITIONAL PASS | 🟢 PASS
**Summary (1 sentence, human language)**: <what's the one thing they must know>

## 🔍 Findings (machine-readable — the agent consumes this verbatim)
```json
{
  "verdict": "BLOCKED",
  "scope": "<target desc>",
  "files_audited": <n>,
  "confidence": { "HIGH": <n>, "MEDIUM": <n>, "LOW": <n> },
  "findings": [
    {
      "tag": "sec:auth-bypass",
      "confidence": "HIGH",
      "location": "AuthService.java:89",
      "issue": "<1 line — what's wrong, concrete path to impact>",
      "fix": "<1 line — minimal conservative fix>",
      "blocks": true
    }
  ],
  "changed_contracts": ["method(): now returns null on timeout" ]
}
```

## ✅ Next action (ask, then stop — do not auto-act)
```
조치를 선택하세요:
 [1] 수정 진행 — 위 findings 중 잡을 것 (사람/에이전트 지정)
 [2] 그대로 두고 여기서 마무리
 [3] 상세 열람 — 특정 finding의 근거/코드 전문
```
- If verdict is **BLOCKED**/**CONDITIONAL PASS**, the gate is mandatory.
- If verdict is **PASS** and there are **zero findings**, skip Findings JSON and
  just output: `Solid & Lean. Clean to ship.` then the gate ([2] default).
- The gate belongs to **every** report — a bare cross-check should always hand
  the decision back, never end silently.

## When to expand beyond the JSON

Only when asked (by the human or a [3] drill-down). Then per-finding expand to:
evidence path, vulnerable code, conservative fix code, and sibling callers. The
**default report is the three blocks above.** Do not reproduce the whole diff or
repeat a finding's rationale in both the JSON and prose.
```

## Guiding rules

- Every finding must carry `tag`, `confidence`, `location`, 1-line `issue`, 1-line
  `fix`, and `blocks` (whether it alone would flip to BLOCKED).
- Verdict rule recap:
  - 🔴 BLOCKED — at least one HIGH-confidence production-significant security /
    crash / leak / race / data-corruption / caller-contract defect.
  - 🟡 CONDITIONAL PASS — no HIGH blocker but a credible MEDIUM risk remains.
  - 🟢 PASS — no HIGH/MEDIUM safety/security findings.
    LOW-confidence and taste-level (YAGNI/style) findings never block.
- `changed_contracts` is optional but include any nullability / error / behavior
  drift that callers must honor; leave empty if none.
- Do **not** invent defects from mere unusual patterns; the JSON issue line must
  name the concrete path from changed code to impact.
- Keep JSON valid — no markdown fences inside string values, escape quotes.
