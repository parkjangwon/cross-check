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
        cmd.extend(["--", rel_to_root])
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
    "hashCode", "constructor", "run", "test", "get", "set", "true", "false", "null",
    "return", "this", "super", "export", "default", "class", "interface", "struct",
    "enum", "type", "void", "string", "int", "boolean", "new", "lambda", "render",
    "not", "and", "or", "is", "in", "raise", "try", "except", "finally", "assert",
    "with", "yield", "pass", "break", "continue", "import", "from", "as", "global", "nonlocal",
    # Framework lifecycle
    "created", "mounted", "updated", "destroyed", "beforeCreate", "beforeMount",
    "onMounted", "onUnmounted", "computed", "watch", "setup", "data", "props",
    # Language builtins & universal utilities
    "range", "len", "open", "print", "close", "read", "write", "send", "recv",
    "map", "filter", "reduce", "list", "dict", "str", "float", "tuple", "any", "all",
    "log", "info", "warn", "error", "debug", "trace", "parse", "format", "build",
    "push", "pop", "shift", "unshift", "slice", "splice", "join", "split", "find",
    "includes", "indexOf", "lastIndexOf", "forEach", "some", "every", "sort"
}

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
    symbol_to_source = {}
    for file_path, diff_content in filtered_files.items():
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
            for l in lines:
                parts = l.split(":", 2)
                if len(parts) >= 3:
                    caller_file, line_no, content = parts[0], parts[1], parts[2].strip()
                    # Skip the definition file itself
                    if caller_file == source_file:
                        continue
                    if is_ignored(caller_file):
                        continue
                    callers.append((caller_file, line_no, content))

            if callers:
                blast_radius[sym] = {
                    "source_file": source_file,
                    "total_callers": len(callers),
                    "samples": callers[:max_callers_per_sym]
                }
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
            diff_lines.append(f"+{l.rstrip('\r\n')}")

        untracked_diffs[rel_path] = "\n".join(diff_lines)

    return untracked_diffs, skipped_untracked

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

    # When inspecting working tree (uncommitted), include untracked code files
    if not (args.commit or args.range or args.staged):
        untracked_files, skipped_untracked = get_untracked_files_diff(git_root)
        if args.file:
            untracked_files = {p: c for p, c in untracked_files.items() if p == args.file or p.startswith(args.file)}
        filtered_files.update(untracked_files)
        skipped_files.extend(skipped_untracked)

    if not filtered_files and not skipped_files:
        print(f"## [cross-check] No changes found for: {target_desc}")
        sys.exit(0)

    # Output structured summary
    print(f"# Cross-Check Diff Context")
    print(f"- **Target**: {target_desc}")
    print(f"- **Modified Files Target**: {len(filtered_files)} file(s)")
    if skipped_files:
        print(f"- **Excluded Noise Files**: {len(skipped_files)} file(s) (lockfiles, bundles, binaries)")
    print()

    print("## Target Files Summary")
    for file_path in sorted(filtered_files.keys()):
        content = filtered_files[file_path]
        additions = sum(1 for l in content.splitlines() if l.startswith("+") and not l.startswith("+++"))
        deletions = sum(1 for l in content.splitlines() if l.startswith("-") and not l.startswith("---"))
        print(f"- `{file_path}` (+{additions}, -{deletions})")
    print()

    # Discover blast radius / caller impact
    if not getattr(args, "skip_callers", False):
        blast_radius = find_blast_radius(git_root, filtered_files)
        if blast_radius:
            print("## 🎯 Blast Radius & Caller Impact Candidates")
            print("> The following modified methods were found to have external callers across the codebase.")
            print("> Audit these call sites for return contract drift, unhandled nulls, or broken assumptions:\n")
            for sym, data in blast_radius.items():
                print(f"### Method `{sym}()` (defined in `{data['source_file']}`)")
                print(f"- Found {data['total_callers']} external call site(s) across repository:")
                for caller_file, line_no, snippet in data["samples"]:
                    print(f"  - `{caller_file}:L{line_no}`: `{snippet}`")
                if data["total_callers"] > len(data["samples"]):
                    remaining = data["total_callers"] - len(data["samples"])
                    print(f"  - *... and {remaining} more caller(s). (Use `git grep -w \"{sym}\"` for all)*")
                print()

    print("## Diff Details")
    total_emitted_lines = 0
    budget_exhausted = False

    for file_path in sorted(filtered_files.keys()):
        content = filtered_files[file_path]
        lines = content.splitlines()
        total_lines = len(lines)

        print(f"### File: `{file_path}`")

        if not args.no_truncate and budget_exhausted:
            print(f"> *[Diff truncated: Total token budget ({args.max_total_lines} lines) reached. Use `--file {file_path}` to inspect this file directly.]*\n")
            continue

        if not args.no_truncate and total_lines > args.max_file_lines:
            truncated_lines = lines[:args.max_file_lines]
            print("```diff")
            print("\n".join(truncated_lines))
            print(f"\n# ... [Diff truncated: showing first {args.max_file_lines} of {total_lines} lines. Run with --no-truncate for full diff.] ...")
            print("```\n")
            total_emitted_lines += args.max_file_lines
        else:
            print("```diff")
            print(content)
            print("```\n")
            total_emitted_lines += total_lines

        if not args.no_truncate and total_emitted_lines >= args.max_total_lines:
            budget_exhausted = True

if __name__ == "__main__":
    main()
