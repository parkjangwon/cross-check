# 🛡️ cross-check: Enterprise Security & Stability Gatekeeper

> **Language-Agnostic, Diff-Scoped Enterprise Code Verification Skill**  
> Complies with the universal Agent Skills standard (`SKILL.md`) for Claude Code, Codex, Antigravity, and other leading AI coding agents.

---

## 🎯 Why Cross-Check?

- **Guard against Vibe-Coding Hazards**: AI coding tools generate plausible code that frequently conceals **resource leaks (FD, socket, DB connections), concurrency race conditions, null/nil panics, swallowed errors, and authorization bypasses**.
- **Zero On-Premise Regressions**: In enterprise software deployed on-premise, defects cannot be silently hot-reloaded. Crashes and security flaws result in emergency customer on-site engineering and compliance audit escalations.
- **Diff-Scoped (Not Full-Scan SAST)**: Targets strictly `git diff` modifications and direct callers/callees. Saves 80-90% of LLM tokens while delivering rapid, high-signal reviews.
- **Ruthless YAGNI / Anti-Over-Engineering**: Flags unnecessary abstractions, single-implementation interfaces, premature design patterns, and unneeded dependencies.
- **Language-Agnostic**: Operates across any language ecosystem (Java, Go, C/C++, Rust, Python, TypeScript, etc.) based on Universal Enterprise Invariants.

---

## 📂 Project Structure

```
cross-check/
├── SKILL.md                 # Universal Agent Skill specification and gatekeeper persona
├── scripts/
│   └── get_diff_context.py  # Python 3 stdlib git diff extractor (auto-filters lockfiles & binaries)
├── references/
│   ├── enterprise_checklist.md  # 6 Universal Enterprise Invariants & checklist
│   └── report_template.md       # High-density reporting format with tagged findings & scoreboard
└── README.md                # Installation and usage instructions
```

---

## 🚀 Installation

### 1. Claude Code
Install as a global skill or local project skill:

```bash
# Global installation (available across all repositories)
mkdir -p ~/.claude/skills
ln -s /Users/pjw/dev/project/cross-check ~/.claude/skills/cross-check

# Or project-local installation
mkdir -p .claude/skills
ln -s /Users/pjw/dev/project/cross-check .claude/skills/cross-check
```

### 2. Antigravity (AGY)
Link to your Antigravity skills directory:

```bash
mkdir -p ~/.gemini/antigravity/skills
ln -s /Users/pjw/dev/project/cross-check ~/.gemini/antigravity/skills/cross-check
```

### 3. Codex / Cursor / Other Agents
Place inside `.skills/cross-check` in your project root or symlink to your agent's configured skills path.

---

## 💬 Usage Examples (Prompts)

The skill automatically triggers on natural language prompts in both English and Korean:

1. **Audit uncommitted working tree changes**:
   > *"Run a cross-check on my uncommitted code for crash risks, leaks, and over-engineering."*  
   > *(또는 "방금 수정한 코드 버그나 리소스 누수 없는지 크로스체크해줘.")*
2. **Audit staged changes before commit**:
   > *"Cross-check staged changes against enterprise safety invariants."*
3. **Audit a specific commit**:
   > *"Cross-check commit `a1b2c3d` for regressions, security flaws, and YAGNI violations."*
4. **Audit PR diff against main branch**:
   > *"Run cross-check on `main..HEAD` and generate the review scoreboard."*

---

## 🛠️ Standalone CLI Usage (`get_diff_context.py`)

Extract clean, token-efficient diff context directly in your terminal:

```bash
# Working tree changes (staged + unstaged)
python3 scripts/get_diff_context.py

# Staged changes only
python3 scripts/get_diff_context.py --staged

# Specific commit
python3 scripts/get_diff_context.py --commit <COMMIT_HASH>

# Commit or branch range
python3 scripts/get_diff_context.py --range main..HEAD

# Single file inspection
python3 scripts/get_diff_context.py --file path/to/file.go
```
*Note: Lockfiles (`package-lock.json`, `Cargo.lock`), bundles, and binaries are automatically excluded.*
