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
    # Generated / Meta
    ".git/*",
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

def build_diff_command(args):
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
        cmd.extend(["--", args.file])
        target_desc += f" (filter: {args.file})"

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

    args = parser.parse_args()

    git_root = get_git_root()
    diff_cmd, target_desc = build_diff_command(args)

    raw_diff = run_command(diff_cmd, cwd=git_root)

    if not raw_diff.strip():
        # If HEAD diff was empty, check unstaged-only (in case initial commit or no HEAD)
        if not (args.commit or args.range or args.staged):
            fallback_cmd = ["git", "diff", "--no-color", "--unified=3"]
            if args.file:
                fallback_cmd.extend(["--", args.file])
            raw_diff = run_command(fallback_cmd, cwd=git_root)
            target_desc = "Working tree (unstaged)"

    filtered_files, skipped_files = parse_diff(raw_diff)

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

    print("## Diff Details")
    for file_path, content in filtered_files.items():
        print(f"### File: `{file_path}`")
        print("```diff")
        print(content)
        print("```\n")

if __name__ == "__main__":
    main()
