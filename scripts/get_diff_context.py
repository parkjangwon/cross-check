#!/usr/bin/env python3
"""
get_diff_context.py
Enterprise-grade, token-efficient git diff extractor for code verification.

Supports:
- Uncommitted changes (both staged and unstaged) by default
- Staged-only changes (--staged / --cached)
- Specific commit (--commit <hash>)
- Commit/branch range (--range <base>..<head>)
- Specific file filtering (--file <path>)

Excludes lockfiles, minified bundles, build artifacts, and binary files.
"""

import argparse
import fnmatch
import os
import re
import subprocess
import sys

# Patterns to ignore to save tokens and focus on actual logic changes
IGNORED_PATTERNS = [
    # Lockfiles
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "Cargo.lock",
    "poetry.lock",
    "Gemfile.lock",
    "composer.lock",
    # Build & Distribution artifacts
    "dist/*",
    "build/*",
    "target/*",
    ".next/*",
    ".nuxt/*",
    "out/*",
    # Minified & Source maps
    "*.min.js",
    "*.min.css",
    "*.map",
    "*.bundle.js",
    # Generated / Meta & Config
    ".git/*",
    ".gitignore",
    ".gitattributes",
    ".editorconfig",
    # IDE & Editor files
    ".idea/*",
    ".vscode/*",
    ".settings/*",
    "*.iml",
    ".DS_Store",
    "Thumbs.db",
    # Logs & Temporary files
    "*.log",
    "*.tmp",
    "*.bak",
    "*.swp",
    "*.swo",
    "node_modules/*",
    "*.svg",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.ico",
    "*.woff",
    "*.woff2",
    "*.ttf",
    "*.eot",
]

def run_command(cmd, cwd=None):
    """Run a shell command and return stdout or raise error."""
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=cwd,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        sys.stderr.write(f"Error running {' '.join(cmd)}: {e.stderr.strip()}\n")
        sys.exit(1)
    except FileNotFoundError:
        sys.stderr.write(f"Command not found: {cmd[0]}\n")
        sys.exit(1)

def is_ignored(file_path):
    """Check if file matches any ignored pattern."""
    normalized = file_path.replace("\\", "/")
    for pattern in IGNORED_PATTERNS:
        if fnmatch.fnmatch(normalized, pattern) or fnmatch.fnmatch(os.path.basename(normalized), pattern):
            return True
    return False

def get_git_root():
    """Verify git repository and return root directory."""
    try:
        output = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        return output.stdout.strip()
    except subprocess.CalledProcessError:
        sys.stderr.write("Fatal: Not a git repository.\n")
        sys.exit(1)

def has_commit(ref="HEAD"):
    """Check if a commit reference exists."""
    res = subprocess.run(
        ["git", "rev-parse", "--verify", ref],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    return res.returncode == 0


# If a modified symbol's textual matches span more than this fraction of the
# repository's code files (or exceed this hard ceiling of distinct files), it
# is almost certainly a language builtin, a shared util, or a framework/common
# name — listing its callers would flood the report with noise and burn the
# very tokens this tool exists to save. In that case we downgrade the symbol to
# a concise "broadly referenced name" note instead of sampling dozens of files.
BROAD_SYMBOL_FILE_RATIO = 0.30          # >=30% of code files reference it
BROAD_SYMBOL_MIN_FILES = 12             # ...and at least 12 distinct files
BROAD_SYMBOL_HARD_CAP = 40              # never list per-file callers beyond 40


def count_code_files(git_root):
    """Count source files in the repo (post ignore/code filtering). Cheap via git ls-files."""
    # Use subprocess directly (not run_command) so a non-git dir degrades to None
    # instead of exiting the whole tool.
    try:
        res = subprocess.run(
            ["git", "ls-files"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=git_root,
        )
    except Exception:
        return None
    if res.returncode != 0:
        return None
    n = 0
    for f in res.stdout.splitlines():
        if not is_ignored(f) and is_code_file(f):
            n += 1
    return n or None


def is_broadly_referenced(sym, caller_files, total_code_files):
    """
    Decide whether a symbol is too widely referenced to be a useful blast-radius
    target. `caller_files` is the list of distinct files holding textual matches.
    """
    if not caller_files:
        return False
    distinct = len(set(caller_files))
    if distinct >= BROAD_SYMBOL_HARD_CAP:
        return True
    if total_code_files:
        return distinct >= max(BROAD_SYMBOL_MIN_FILES, round(total_code_files * BROAD_SYMBOL_FILE_RATIO))
    return distinct >= BROAD_SYMBOL_MIN_FILES

# --- Gitlink / Submodule Helpers ---------------------------------------------

def is_gitlink(content):
    """Check if diff content represents a submodule gitlink (mode 160000 / Subproject commit)."""
    if not content:
        return False
    has_mode = bool(re.search(r"^(?:index [0-9a-fA-F]+\.\.[0-9a-fA-F]+ 160000|(?:new|deleted) file mode 160000)", content, re.MULTILINE))
    has_subproject = bool(re.search(r"^[-+]Subproject commit [0-9a-fA-F]{7,40}$", content, re.MULTILINE))
    return has_mode or has_subproject

def extract_subproject_commits(content):
    """
    Extract (old_sha, new_sha) from a gitlink diff.
    Returns (old_sha, new_sha), either of which may be None.
    """
    old_m = re.search(r"^-Subproject commit ([0-9a-fA-F]{7,40})$", content, re.MULTILINE)
    new_m = re.search(r"^\+Subproject commit ([0-9a-fA-F]{7,40})$", content, re.MULTILINE)
    old_sha = old_m.group(1) if old_m else None
    new_sha = new_m.group(1) if new_m else None
    return old_sha, new_sha

def get_submodule_paths(git_root):
    """Return set of relative submodule paths declared in .gitmodules."""
    paths = set()
    gitmodules = os.path.join(git_root, ".gitmodules")
    if os.path.isfile(gitmodules):
        try:
            with open(gitmodules, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("path =") or line.startswith("path="):
                        p = line.split("=", 1)[1].strip()
                        paths.add(p.replace("\\", "/"))
        except Exception:
            pass
    return paths

def find_submodule_prefix(git_root, rel_path, declared_paths=None):
    """
    If rel_path is inside a git submodule, return the submodule's relative path from git_root.
    Otherwise return None.
    """
    if not rel_path:
        return None
    normalized = rel_path.replace("\\", "/")
    if declared_paths is None:
        declared_paths = get_submodule_paths(git_root)

    parts = normalized.split("/")
    for i in range(1, len(parts)):
        prefix = "/".join(parts[:i])
        if prefix in declared_paths:
            return prefix
        sub_dir = os.path.join(git_root, prefix)
        if os.path.exists(os.path.join(sub_dir, ".git")):
            return prefix
    return None

def expand_submodule_diff(git_root, sub_path, old_sha, new_sha):
    """
    Expand a submodule gitlink into inner file diffs if the submodule
    repository is cloned and initialized locally.
    Returns: (expanded_files_dict, skipped_list, error_or_notice_string)
    """
    full_sub_path = os.path.join(git_root, sub_path)
    if not os.path.isdir(full_sub_path):
        return None, [], f"Submodule directory '{sub_path}' not found or not initialized locally"

    # Verify it is a valid git repository
    try:
        chk = subprocess.run(
            ["git", "-C", full_sub_path, "rev-parse", "--git-dir"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if chk.returncode != 0:
            return None, [], f"Submodule '{sub_path}' is not an initialized git repo"
    except Exception as e:
        return None, [], f"Cannot inspect submodule '{sub_path}': {e}"

    # Build diff command for submodule
    if old_sha and new_sha:
        cmd = ["git", "-C", full_sub_path, "diff", "--no-color", "--unified=3", f"{old_sha}..{new_sha}"]
    elif new_sha:
        # Added submodule: diff against empty tree SHA
        cmd = ["git", "-C", full_sub_path, "diff", "--no-color", "--unified=3", "4b825dc642cb6eb9a060e54bf8d69288fbee4904", new_sha]
    elif old_sha:
        # Removed submodule: diff against empty tree SHA
        cmd = ["git", "-C", full_sub_path, "diff", "--no-color", "--unified=3", old_sha, "4b825dc642cb6eb9a060e54bf8d69288fbee4904"]
    else:
        return None, [], f"No commit hashes found in gitlink for '{sub_path}'"

    try:
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        if res.returncode != 0:
            err = res.stderr.strip().splitlines()
            first_err = err[0] if err else "git diff failed in submodule"
            return None, [], f"Submodule '{sub_path}' diff error: {first_err}"

        inner_diff = res.stdout
        if not inner_diff.strip():
            return {}, [], None

        raw_inner_files, raw_skipped = parse_diff(inner_diff)
        expanded_files = {}
        skipped = []

        for inner_file, inner_content in raw_inner_files.items():
            prefixed = f"{sub_path}/{inner_file}"
            if is_ignored(prefixed):
                skipped.append(prefixed)
                continue

            lines = inner_content.splitlines()
            adjusted = []
            for line in lines:
                if line.startswith("diff --git "):
                    adjusted.append(f"diff --git a/{prefixed} b/{prefixed}")
                elif line.startswith("--- a/"):
                    adjusted.append(f"--- a/{prefixed}")
                elif line.startswith("+++ b/"):
                    adjusted.append(f"+++ b/{prefixed}")
                else:
                    adjusted.append(line)
            expanded_files[prefixed] = "\n".join(adjusted)

        for sk in raw_skipped:
            skipped.append(f"{sub_path}/{sk}")

        return expanded_files, skipped, None
    except Exception as e:
        return None, [], f"Error executing git in submodule '{sub_path}': {e}"

def build_diff_command(args, git_root):
    """Build git diff command based on user options."""
    cmd = ["git", "diff", "--no-color", "--unified=3"]
    target_desc = ""

    if args.commit:
        commit = args.commit
        cmd = ["git", "show", "--no-color", "--unified=3", commit]
        target_desc = f"Commit {commit}"
    elif args.range:
        cmd.extend([args.range])
        target_desc = f"Range {args.range}"
    elif args.staged:
        if has_commit("HEAD"):
            cmd.extend(["--cached"])
        else:
            # Empty tree SHA-1 for initial commit without HEAD
            cmd.extend(["--cached", "4b825dc642cb6eb9a060e54bf8d69288fbee4904"])
        target_desc = "Staged changes (--cached)"
    else:
        if has_commit("HEAD"):
            cmd.extend(["HEAD"])
            target_desc = "Working tree (staged + unstaged vs HEAD)"
        else:
            # Fresh repo with no commits yet
            target_desc = "Working tree (unstaged changes, no HEAD commit yet)"

    if args.file:
        raw_file = args.file
        abs_target = os.path.abspath(raw_file)
        if abs_target.startswith(git_root):
            rel_to_root = os.path.relpath(abs_target, git_root).replace("\\", "/")
        else:
            rel_to_root = raw_file.replace("\\", "/")
        sub_prefix = find_submodule_prefix(git_root, rel_to_root)
        target_path_for_diff = sub_prefix if sub_prefix else rel_to_root
        cmd.extend(["--", target_path_for_diff])
        target_desc += f" (filter: {rel_to_root})"

    return cmd, target_desc

def parse_diff(raw_diff):
    """Parse raw git diff output and split by file, filtering ignored paths."""
    files = {}
    current_file = None
    current_lines = []

    for line in raw_diff.splitlines():
        if line.startswith("diff --git "):
            if current_file and current_lines:
                files[current_file] = "\n".join(current_lines)
            
            # Extract file path: diff --git a/path/to/file b/path/to/file
            parts = line.split(" ")
            if len(parts) >= 4:
                b_path = parts[3]
                if b_path.startswith("b/"):
                    current_file = b_path[2:]
                else:
                    current_file = b_path
            else:
                current_file = "unknown"
            current_lines = [line]
        else:
            if current_file:
                current_lines.append(line)

    if current_file and current_lines:
        files[current_file] = "\n".join(current_lines)

    # Filter out ignored files
    filtered_files = {}
    skipped_files = []
    for path, content in files.items():
        if is_ignored(path):
            skipped_files.append(path)
        else:
            filtered_files[path] = content

    return filtered_files, skipped_files

def is_binary_file(filepath):
    """Check if file appears to be binary by checking for null bytes in initial chunk."""
    try:
        with open(filepath, "rb") as f:
            chunk = f.read(1024)
            return b"\x00" in chunk
    except Exception:
        return True

COMMON_EXCLUDED_METHOD_NAMES = {
    # Control flow & keywords
    "if", "for", "while", "switch", "catch", "init", "main", "toString", "equals",
    "hashCode", "constructor", "true", "false", "null",
    "return", "this", "super", "export", "default", "class", "interface", "struct",
    "enum", "type", "void", "string", "int", "boolean", "new", "lambda", "render",
    "not", "and", "or", "is", "in", "raise", "try", "except", "finally", "assert",
    "with", "yield", "pass", "break", "continue", "import", "from", "as", "global", "nonlocal",
    # Framework lifecycle
    "created", "mounted", "updated", "destroyed", "beforeCreate", "beforeMount",
    "onMounted", "onUnmounted", "computed", "watch", "setup", "data", "props",
    # Language builtins & universal utilities (common verbs like get/set/run/test
    # are deliberately NOT excluded: they are frequent real method names)
    "range", "len", "open", "print", "close", "read", "write", "send", "recv",
    "list", "dict", "str", "float", "tuple", "any", "all",
    "log", "info", "warn", "error", "debug", "trace", "parse", "format", "build",
    "push", "pop", "shift", "unshift", "slice", "splice", "join", "split",
    "includes", "indexOf", "lastIndexOf", "forEach", "some", "every", "sort"
}

# File extensions that are not source code: keep them visible in the diff,
# but never extract "modified methods" from them for blast-radius analysis.
NON_CODE_EXTENSIONS = {
    ".md", ".markdown", ".rst", ".txt", ".adoc",
    ".json", ".jsonc", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".csv", ".tsv", ".html", ".htm", ".xml", ".svg",
    ".lock", ".log", ".env", ".editorconfig", ".gitignore", ".gitattributes",
    ".sql", ".graphql", ".prisma", ".dockerfile", ".http", ".rest",
}

def is_code_file(file_path):
    """True only for files whose extension suggests runnable source code."""
    ext = os.path.splitext(file_path)[1].lower()
    return ext not in NON_CODE_EXTENSIONS

def extract_enclosing_function_from_file(file_path, line_number, func_patterns):
    """Scan upward from line_number in source file to find enclosing function definition."""
    if not os.path.isfile(file_path):
        return None
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        # Scan upward up to 50 lines
        start = max(0, line_number - 1)
        for idx in range(start, max(-1, start - 50), -1):
            if idx < len(lines):
                line = lines[idx]
                for pat in func_patterns:
                    m = pat.search(line)
                    if m:
                        for g in m.groups():
                            if g and g not in COMMON_EXCLUDED_METHOD_NAMES and len(g) > 2:
                                return g
    except Exception:
        pass
    return None

def extract_modified_symbols(git_root, file_path, diff_content):
    """Extract candidate function/method names modified in diff."""
    if is_gitlink(diff_content) or not is_code_file(file_path):
        return []  # docs/config/data/gitlinks never define methods to trace
    candidates = set()

    hunk_header_re = re.compile(r"^@@\s+-([0-9]+)(?:,[0-9]+)?\s+\+([0-9]+)(?:,[0-9]+)?\s+@@\s*(.*)$")
    func_patterns = [
        re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z0-9_]{3,})\s*\("),                       # Python
        re.compile(r"^func\s+(?:\([^)]+\)\s+)?([A-Za-z0-9_]{3,})\s*\("),                     # Go
        re.compile(r"^\s*(?:pub(?:\([^)]+\))?\s+)?(?:async\s+)?fn\s+([A-Za-z0-9_]{3,})"),   # Rust
        re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z0-9_]{3,})\s*\("),    # JS/TS func
        re.compile(r"^\s*(?:const|let|var)\s+([A-Za-z0-9_]{3,})\s*=\s*(?:async\s*)?\("),      # JS/TS arrow
        re.compile(r"^\s*(?:[A-Za-z0-9_<>\[\],?]+\s+)+([A-Za-z0-9_]{3,})\s*\([^;]*$"),      # Java/C/C++
    ]

    full_path = os.path.join(git_root, file_path)

    for line in diff_content.splitlines():
        # Check hunk header
        m_hunk = hunk_header_re.match(line)
        if m_hunk:
            header_tail = m_hunk.group(3).strip()
            # 1. Look for function name directly in git header
            words = re.findall(r"([A-Za-z0-9_]{3,})\s*\(", header_tail)
            for w in words:
                if w not in COMMON_EXCLUDED_METHOD_NAMES and len(w) > 2:
                    candidates.add(w)

            # 2. Scan upward in source file from hunk start line
            hunk_start_line = int(m_hunk.group(2))
            enclosing = extract_enclosing_function_from_file(full_path, hunk_start_line, func_patterns)
            if enclosing:
                candidates.add(enclosing)

        # Check all lines in diff (both modified and immediate context)
        if not line.startswith(("+++", "---")):
            code_line = line[1:] if line.startswith(("+", "-", " ")) else line
            for pat in func_patterns:
                m = pat.search(code_line)
                if m:
                    for g in m.groups():
                        if g and g not in COMMON_EXCLUDED_METHOD_NAMES and len(g) > 2:
                            candidates.add(g)

    return sorted(candidates)

def find_blast_radius(git_root, filtered_files, max_symbols=5, max_callers_per_sym=8):
    """Find external caller sites in the repository for modified methods."""
    total_code_files = count_code_files(git_root)

    symbol_to_source = {}
    for file_path, diff_content in filtered_files.items():
        if not is_code_file(file_path):
            continue  # docs/config/data files never define methods to trace
        symbols = extract_modified_symbols(git_root, file_path, diff_content)
        for sym in symbols:
            if sym not in symbol_to_source:
                symbol_to_source[sym] = file_path

    if not symbol_to_source:
        return {}

    blast_radius = {}
    tested_count = 0

    for sym, source_file in symbol_to_source.items():
        if tested_count >= max_symbols:
            break

        # Run git grep to find usages across repo
        try:
            grep_cmd = ["git", "grep", "--recurse-submodules", "--no-color", "-n", "-w", sym]
            grep_res = subprocess.run(
                grep_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=git_root
            )
            if grep_res.returncode != 0 and grep_res.stderr:
                # Fallback to standard git grep without --recurse-submodules if not supported
                grep_res = subprocess.run(
                    ["git", "grep", "--no-color", "-n", "-w", sym],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    cwd=git_root
                )
            if grep_res.returncode != 0 or not grep_res.stdout.strip():
                continue

            lines = grep_res.stdout.splitlines()
            callers = []
            caller_files = []
            for l in lines:
                parts = l.split(":", 2)
                if len(parts) >= 3:
                    caller_file, line_no, content = parts[0], parts[1], parts[2].strip()
                    # Skip the definition file itself
                    if caller_file == source_file:
                        continue
                    if is_ignored(caller_file) or not is_code_file(caller_file):
                        continue
                    callers.append((caller_file, line_no, content))
                    caller_files.append(caller_file)

            if not callers:
                continue

            # A symbol matched across most of the codebase is almost certainly a
            # language builtin or an overbroad shared name (e.g. `String`) — not
            # a change whose callers we can meaningfully audit. Downgrade it to a
            # one-line note instead of flooding the report with dozens of samples,
            # which would consume exactly the tokens this tool exists to save.
            broad = is_broadly_referenced(sym, caller_files, total_code_files)
            entry = {
                "source_file": source_file,
                "total_callers": len(callers),
                "distinct_files": len(set(caller_files)),
                "broad": broad,
            }
            if not broad:
                entry["samples"] = callers[:max_callers_per_sym]
            blast_radius[sym] = entry
            tested_count += 1
        except Exception:
            continue

    return blast_radius

def get_untracked_files_diff(git_root):
    """Detect untracked files and synthesize unified diffs for new text files."""
    try:
        status_output = run_command(["git", "status", "--porcelain", "-uall"], cwd=git_root)
    except Exception:
        return {}, []

    untracked_diffs = {}
    skipped_untracked = []

    for line in status_output.splitlines():
        if not line.startswith("?? "):
            continue
        rel_path = line[3:].strip()
        # Handle quotes if filename has spaces
        if rel_path.startswith('"') and rel_path.endswith('"'):
            rel_path = rel_path[1:-1]

        if is_ignored(rel_path):
            skipped_untracked.append(rel_path)
            continue

        full_path = os.path.join(git_root, rel_path)
        if not os.path.isfile(full_path) or is_binary_file(full_path):
            skipped_untracked.append(rel_path)
            continue

        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception:
            skipped_untracked.append(rel_path)
            continue

        num_lines = len(lines)
        diff_lines = [
            f"diff --git a/{rel_path} b/{rel_path}",
            "new file mode 100644",
            "--- /dev/null",
            f"+++ b/{rel_path}",
            f"@@ -0,0 +1,{num_lines} @@"
        ]
        for l in lines:
            # strip newline from right for clean output
            # NOTE: avoid backslash inside f-string expression for Python < 3.12
            stripped = l.rstrip("\r\n")
            diff_lines.append(f"+{stripped}")

        untracked_diffs[rel_path] = "\n".join(diff_lines)

    return untracked_diffs, skipped_untracked


# --- Review-profile helpers (LLM-audit oriented) -----------------------------
#
# cross-check does NOT ask the runtime model whether a change is "abnormal" —
# that decision belongs to the reviewing agent, which already has the full PR /
# conversation context. Instead the extractor produces a concise *change
# profile* at the top of the report. The reviewing agent uses it to answer
# "is this an out-of-band commit worth reading in full?" before details stream.
# A commit audit defaults to showing everything; the numeric line caps only
# bite when --strict-cap is passed (or for iterative working-tree edits).

def _ext_of(path):
    _, ext = os.path.splitext(path)
    return ext.lower()

def summarize_change_kind(file_path, n_add, n_del, is_submodule=False):
    """
    Coarse, extension-based classification of what a changed file *mostly is*,
    for the review profile. Not a substitute for reading it — only a signal the
    reviewing agent can use to triage breadth (e.g. "mostly lockfiles/tests").
    """
    if is_submodule:
        return "submodule"
    ext = _ext_of(file_path)
    base = os.path.basename(file_path).lower()

    if ext in {".test.ts", ".test.tsx", ".test.js", ".spec.ts", ".spec.tsx",
               ".t.ts"} or ".test." in base or ".spec." in base or base.startswith("test_"):
        return "test"
    if ext in {".css", ".scss", ".less", ".html"} or ext in {".htm", ".css"}:
        return "style"
    if ext in NON_CODE_EXTENSIONS:
        return "config/docs/data"
    if ext in {".json", ".jsonc", ".yaml", ".yml", ".toml", ".ini", ".cfg",
               ".conf", ".env", ".sql", ".graphql", ".prisma", ".lock"}:
        return "config/docs/data"
    if n_del > 3 * n_add and n_del > 20:   # heavily deletion-heavy
        return "refactor/del"
    if n_add == 0 and n_del == 0:
        return "meta-only"
    return "logic"

def compute_diff_stats(filtered_files):
    """
    Return {path: (add, del, total_lines)} plus aggregate totals so main() can
    decide upfront whether this change exceeds review caps.
    """
    stats = {}
    total_add = total_del = total_lines = 0
    for path, content in filtered_files.items():
        lines = content.splitlines()
        adds = sum(1 for l in lines if l.startswith("+") and not l.startswith("+++"))
        dels = sum(1 for l in lines if l.startswith("-") and not l.startswith("---"))
        stats[path] = (adds, dels, len(lines))
        total_add += adds
        total_del += dels
        total_lines += len(lines)
    return stats, total_add, total_del, total_lines

def build_commit_profile(filtered_files, stats, total_add, total_del, total_lines,
                         blast_radius, target_desc, audit_mode, strict_cap=False):
    """
    One concise, mostly-machine-readable header block a reviewing agent can
    triage immediately. Highlights breadth/danger signals without dumping diffs.
    """
    n_files = len(filtered_files)
    kinds = {}
    for path, (adds, dels, _tl) in stats.items():
        is_sub = is_gitlink(filtered_files.get(path, ""))
        k = summarize_change_kind(path, adds, dels, is_submodule=is_sub)
        kinds[k] = kinds.get(k, 0) + 1
    kind_summary = ", ".join(f"{v} {k.replace('config/docs/data', 'config')}"
                             for k, v in sorted(kinds.items(), key=lambda kv: -kv[1]))

    # Distinct caller files across all blast-radius entries (danger signal).
    broad_syms = 0
    caller_files_est = 0
    if blast_radius:
        broad_syms = sum(1 for d in blast_radius.values() if d.get("broad"))
        caller_files_est = sum(d.get("distinct_files", 0) for d in blast_radius.values())

    if audit_mode and total_lines:
        if strict_cap:
            note = (f"\n- **Audit policy**: whole change is {total_lines} diff lines / "
                    f"{n_files} file(s); --strict-cap is set, so output is capped. "
                    f"If you judge this change 'abnormal' and want to review it in "
                    f"full, re-run with --no-truncate or isolate files with --file.")
        else:
            note = (f"\n- **Audit policy**: commit/range audits default to showing the "
                    f"full change. This one is {total_lines} diff lines across "
                    f"{n_files} file(s). Triage breadth from this profile; if you judge "
                    f"it clearly out-of-band (e.g. pure restructure/config churn) you "
                    f"may narrow to key files with --file instead of reading every line.")
    else:
        note = ("\n- **Audit policy**: working-tree view; line caps are applied to "
                "keep the loop cheap. Re-run with --no-truncate for the entire change.")

    return (
        f"# Cross-Check Change Profile\n"
        f"- **Target**: {target_desc}\n"
        f"- **Files**: {n_files} ({total_add}+/ {total_del}-, ~{total_lines} diff lines)\n"
        f"- **Shape**: {kind_summary or 'unknown'}"
        + (f"\n- **Blast hints**: {len(blast_radius) if blast_radius else 0} candidate symbol(s), "
           f"{broad_syms} broadly-referenced, ~{caller_files_est} caller-file mention(s) (bounded to this repository)" if blast_radius else "")
        + note
        + f"\n"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Extract token-efficient git diff context for conservative enterprise code verification."
    )
    parser.add_argument(
        "--staged", "--cached", action="store_true",
        help="Inspect staged changes only (git diff --cached)"
    )
    parser.add_argument(
        "--commit", "-c", type=str,
        help="Inspect a specific commit (e.g. abc1234)"
    )
    parser.add_argument(
        "--range", "-r", type=str,
        help="Inspect a commit or branch range (e.g. main..HEAD or v1.0..v1.1)"
    )
    parser.add_argument(
        "--file", "-f", type=str,
        help="Limit diff inspection to a specific file or path"
    )
    parser.add_argument(
        "--max-file-lines", type=int, default=400,
        help="Maximum diff lines per file before truncation (default: 400)"
    )
    parser.add_argument(
        "--max-total-lines", type=int, default=1200,
        help="Maximum total diff lines across all files (default: 1200)"
    )
    parser.add_argument(
        "--no-truncate", "--all", action="store_true",
        help="Disable diff truncation limits"
    )
    parser.add_argument(
        "--strict-cap", action="store_true",
        help="Keep exact numeric truncation (per-file 400 / total 1200 lines by "
             "default) even for --commit/--range audits. Without this, an audit "
             "that exceeds the caps is shown in full by default so a reviewing "
             "agent can triage the whole change."
    )
    parser.add_argument(
        "--skip-callers", action="store_true",
        help="Skip searching repository for external callers of modified methods"
    )

    args = parser.parse_args()

    git_root = get_git_root()
    diff_cmd, target_desc = build_diff_command(args, git_root)

    raw_diff = run_command(diff_cmd, cwd=git_root)

    if not raw_diff.strip():
        if not (args.commit or args.range or args.staged):
            fallback_cmd = ["git", "diff", "--no-color", "--unified=3"]
            if args.file:
                abs_f = os.path.abspath(args.file)
                rel_f = os.path.relpath(abs_f, git_root).replace("\\", "/") if abs_f.startswith(git_root) else args.file
                fallback_cmd.extend(["--", rel_f])
            raw_diff = run_command(fallback_cmd, cwd=git_root)
            target_desc = "Working tree (unstaged)"

    filtered_files, skipped_files = parse_diff(raw_diff)

    # Expand submodule gitlinks (mode 160000 / Subproject commit)
    expanded_files = {}
    for path, content in filtered_files.items():
        if is_gitlink(content):
            old_sha, new_sha = extract_subproject_commits(content)
            inner_files, inner_skipped, err_msg = expand_submodule_diff(git_root, path, old_sha, new_sha)
            if inner_files is not None:
                if inner_files:
                    expanded_files.update(inner_files)
                else:
                    sha_info = f"{old_sha[:8]}..{new_sha[:8]}" if old_sha and new_sha else (new_sha[:8] if new_sha else (old_sha[:8] if old_sha else ""))
                    notice = f"# [cross-check: Submodule '{path}' ({sha_info}) contains no internal file changes]"
                    expanded_files[path] = content + "\n" + notice
                skipped_files.extend(inner_skipped)
            else:
                notice = f"# [cross-check note: {err_msg}]"
                expanded_files[path] = content + "\n" + notice
        else:
            expanded_files[path] = content
    filtered_files = expanded_files

    # When inspecting working tree (uncommitted), include untracked code files
    if not (args.commit or args.range or args.staged):
        untracked_files, skipped_untracked = get_untracked_files_diff(git_root)
        if args.file:
            untracked_files = {p: c for p, c in untracked_files.items() if p == args.file or p.startswith(args.file)}
        filtered_files.update(untracked_files)
        skipped_files.extend(skipped_untracked)

    if args.file:
        abs_target = os.path.abspath(args.file)
        rel_target = os.path.relpath(abs_target, git_root).replace("\\", "/") if abs_target.startswith(git_root) else args.file.replace("\\", "/")
        filtered_files = {p: c for p, c in filtered_files.items() if p == rel_target or p.startswith(rel_target + "/")}

    if not filtered_files and not skipped_files:
        print(f"## [cross-check] No changes found for: {target_desc}")
        sys.exit(0)

    # --- Gather stats + blast once, then print a triage-first report --------
    stats, total_add, total_del, total_lines = compute_diff_stats(filtered_files)
    audit_mode = bool(args.commit or args.range)

    # Discover blast radius / caller impact
    blast_radius = {}
    if not getattr(args, "skip_callers", False):
        blast_radius = find_blast_radius(git_root, filtered_files)

    # Triage-first: the review profile lands at the very top so the reviewing
    # agent (LLM) can judge "worth a full read?" before any diff detail streams.
    print(build_commit_profile(
        filtered_files, stats, total_add, total_del, total_lines,
        blast_radius, target_desc, audit_mode, strict_cap=bool(args.strict_cap)
    ))
    if skipped_files:
        print(f"- **Excluded Noise Files**: {len(skipped_files)} file(s) (lockfiles, bundles, binaries)")
    print(f"\n## Target Files Summary")
    for file_path in sorted(filtered_files.keys()):
        adds, dels, _tl = stats[file_path]
        print(f"- `{file_path}` (+{adds}, -{dels})")
    print()

    if blast_radius:
        print("## 🎯 Blast Radius & Caller Impact Candidates")
        print("> The following modified methods were found to have external callers across the codebase.")
        print("> Audit these call sites for return contract drift, unhandled nulls, or broken assumptions:\n")
        for sym, data in blast_radius.items():
            print(f"### Method `{sym}()` (defined in `{data['source_file']}`)")
            if data.get("broad"):
                # Overbroad name: skip per-file samples, they'd drown the report.
                print(f"- Broadly referenced across the codebase "
                      f"({data['distinct_files']} file(s) / {data['total_callers']} mention(s)); "
                      f"likely a common/shared name. Not listing individual callers — "
                      f"this name is too generic to trace a contract drift to a single caller.")
                print()
                continue
            print(f"- Found {data['total_callers']} external call site(s) across {data['distinct_files']} file(s):")
            for caller_file, line_no, snippet in data["samples"]:
                print(f"  - `{caller_file}:L{line_no}`: `{snippet}`")
            if data["total_callers"] > len(data["samples"]):
                remaining = data["total_callers"] - len(data["samples"])
                print(f"  - *... and {remaining} more caller(s). (Use `git grep -w \"{sym}\"` for all)*")
            print()

    print("## Diff Details")

    # --- Truncation policy ----------------------------------------------------
    # Commit/range audits default to showing the *full* diff so a reviewing agent
    # can triage the whole change (out-of-band size alone is not "abnormal" — the
    # LLM decides that from the profile above). Numeric caps only bite when the
    # user opts into them (--strict-cap) or for iterative working-tree runs.
    truncate = (args.no_truncate is False) and (args.strict_cap or not audit_mode)
    total_emitted_lines = 0
    budget_exhausted = False

    for file_path in sorted(filtered_files.keys()):
        content = filtered_files[file_path]
        lines = content.splitlines()
        file_total = len(lines)

        print(f"### File: `{file_path}`")

        if truncate and budget_exhausted:
            print(f"> *[Diff truncated: Total token budget ({args.max_total_lines} lines) reached. Use `--file {file_path}` to inspect this file directly.]*\n")
            continue

        if truncate and file_total > args.max_file_lines:
            truncated_lines = lines[:args.max_file_lines]
            print("```diff")
            print("\n".join(truncated_lines))
            print(f"\n# ... [Diff truncated: showing first {args.max_file_lines} of {file_total} lines. Pass --strict-cap or --no-truncate explicit; or --file for this file.] ...")
            print("```\n")
            total_emitted_lines += args.max_file_lines
        else:
            print("```diff")
            print(content)
            print("```\n")
            total_emitted_lines += file_total

        if truncate and total_emitted_lines >= args.max_total_lines:
            budget_exhausted = True

    # If an audit exceeded caps but we still showed it in full, say so clearly —
    # the reviewer should know it was a forced full read for a large change.
    if audit_mode and not truncate and total_lines > args.max_total_lines and not args.no_truncate:
        print(f"> *[Note: this commit/range diff ({total_lines} lines) exceeded the "
              f"{args.max_total_lines}-line audit cap but was shown in full (default "
              f"for audits). Re-run with --strict-cap to cap, or pass "
              f"`--file <path>` to isolate a file.]*")

if __name__ == "__main__":
    main()
