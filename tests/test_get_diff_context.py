import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "get_diff_context.py"

spec = importlib.util.spec_from_file_location("get_diff_context", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DiffContextTests(unittest.TestCase):
    def test_parse_diff_filters_noise_but_keeps_source(self):
        raw = """diff --git a/src/app.py b/src/app.py
--- a/src/app.py
+++ b/src/app.py
@@ -1 +1 @@
-old()
+new()
diff --git a/package-lock.json b/package-lock.json
--- a/package-lock.json
+++ b/package-lock.json
@@ -1 +1 @@
-1
+2
"""
        files, skipped = module.parse_diff(raw)
        self.assertIn("src/app.py", files)
        self.assertNotIn("package-lock.json", files)
        self.assertIn("package-lock.json", skipped)

    def test_extract_modified_python_symbol_from_hunk_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "service.py").write_text(
                "def process_request(value):\n"
                "    return value.strip()\n"
                "\n"
                "def untouched():\n"
                "    return 1\n",
                encoding="utf-8",
            )
            diff = """diff --git a/service.py b/service.py
--- a/service.py
+++ b/service.py
@@ -1,2 +1,2 @@
 def process_request(value):
-    return value.strip()
+    return value.strip().lower()
"""
            symbols = module.extract_modified_symbols(tmp, "service.py", diff)
            self.assertIn("process_request", symbols)
            self.assertNotIn("untouched", symbols)

    def test_extract_modified_go_method_and_excludes_common_builtins(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "service.go").write_text(
                "func ProcessUser(id string) error {\n"
                "    return nil\n"
                "}\n",
                encoding="utf-8",
            )
            diff = """diff --git a/service.go b/service.go
--- a/service.go
+++ b/service.go
@@ -1,3 +1,3 @@
 func ProcessUser(id string) error {
-    return nil
+    log.Println(id)
 }
"""
            symbols = module.extract_modified_symbols(tmp, "service.go", diff)
            self.assertIn("ProcessUser", symbols)
            self.assertNotIn("log", symbols)

    def test_find_blast_radius_reports_external_usage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "service.py").write_text("def process_request(value):\n    return value\n", encoding="utf-8")
            diff = """diff --git a/service.py b/service.py
--- a/service.py
+++ b/service.py
@@ -1,2 +1,2 @@
 def process_request(value):
-    return value
+    return value.strip()
"""
            files = {"service.py": diff}

            class FakeResult:
                returncode = 0
                stdout = "caller.py:12: result = process_request('x')\n"
                stderr = ""

            with patch.object(module.subprocess, "run", return_value=FakeResult()):
                radius = module.find_blast_radius(tmp, files)

            self.assertIn("process_request", radius)
            self.assertEqual("caller.py", radius["process_request"]["samples"][0][0])

    def test_find_blast_radius_ignores_non_code_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "service.py").write_text("def run(value):\n    return value\n", encoding="utf-8")
            diff = """diff --git a/service.py b/service.py
--- a/service.py
+++ b/service.py
@@ -1,2 +1,2 @@
 def run(value):
-    return value
+    return value.strip()
"""
            files = {"service.py": diff}

            class FakeResult:
                returncode = 0
                stdout = "README.md:42: run `python app.py`\ncaller.py:10: run('x')\n"
                stderr = ""

            with patch.object(module.subprocess, "run", return_value=FakeResult()):
                radius = module.find_blast_radius(tmp, files)

            self.assertIn("run", radius)
            sample_files = [s[0] for s in radius["run"]["samples"]]
            self.assertNotIn("README.md", sample_files)
            self.assertIn("caller.py", sample_files)

    def test_untracked_files_are_synthesized_as_diff(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "new.py").write_text("def hello():\n    return 'hello'\n", encoding="utf-8")
            with patch.object(module, "run_command", return_value="?? new.py\n"):
                diffs, skipped = module.get_untracked_files_diff(tmp)
            self.assertEqual([], skipped)
            self.assertIn("new.py", diffs)
            self.assertIn("new file mode 100644", diffs["new.py"])
            self.assertIn("+def hello():", diffs["new.py"])

    def test_binary_untracked_file_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "image.dat").write_bytes(b"abc\x00def")
            with patch.object(module, "run_command", return_value="?? image.dat\n"):
                diffs, skipped = module.get_untracked_files_diff(tmp)
            self.assertNotIn("image.dat", diffs)
            self.assertIn("image.dat", skipped)

    def test_non_code_files_never_produce_blast_radius_symbols(self):
        diff = """diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1 +1 @@
-Call process_request()
+Call process_request()
"""
        self.assertEqual([], module.extract_modified_symbols("/tmp", "README.md", diff))

    def test_file_filter_is_considered_code_agnostic(self):
        self.assertTrue(module.is_code_file("src/main.java"))
        self.assertTrue(module.is_code_file("src/main.rs"))
        self.assertFalse(module.is_code_file("README.md"))
        self.assertFalse(module.is_code_file("config.yaml"))

    def test_count_code_files_safely_returns_none_outside_git(self):
        # count_code_files must degrade to None (not exit) when the dir is not
        # a git worktree — a non-code temp dir is the perfect non-git case.
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(module.count_code_files(tmp))

    def test_is_broadly_referenced_threshold(self):
        # Many distinct files -> broad (suppress per-file listing).
        many = [f"dir{i}/mod.py" for i in range(50)]
        self.assertTrue(module.is_broadly_referenced("String", many, total_code_files=120))
        # Small, meaningful call set -> keep detailed samples.
        few = [f"src/main/ipc/{i}.ts" for i in range(3)]
        self.assertFalse(module.is_broadly_referenced("runHooks", few, total_code_files=120))
        # Empty set never broad.
        self.assertFalse(module.is_broadly_referenced("x", [], total_code_files=120))
        # Unknown repo size (None) still applies the hard floor of 12 files.
        eleven = [f"f{i}.ts" for i in range(11)]
        twelve = [f"f{i}.ts" for i in range(12)]
        self.assertFalse(module.is_broadly_referenced("x", eleven, total_code_files=None))
        self.assertTrue(module.is_broadly_referenced("x", twelve, total_code_files=None))

    def test_blast_radius_flags_broad_symbol_but_drops_samples(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "service.py").write_text("def util():\n    return None\n", encoding="utf-8")
            diff = """diff --git a/service.py b/service.py
--- a/service.py
+++ b/service.py
@@ -1 +1 @@
-def util():
+def util():
"""
            files = {"service.py": diff}
            grab_all = "\n".join(f"c{i}.py:1: x.utils()\n" for i in range(60))
            class FakeResult:
                returncode = 0
                stdout = grab_all
                stderr = ""
            with patch.object(module.subprocess, "run", return_value=FakeResult()):
                radius = module.find_blast_radius(tmp, files)
            self.assertIn("util", radius)
            self.assertTrue(radius["util"]["broad"])
            self.assertNotIn("samples", radius["util"])

    def test_blast_radius_keeps_samples_for_local_symbol(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "service.py").write_text("def process():\n    return None\n", encoding="utf-8")
            diff = """diff --git a/service.py b/service.py
--- a/service.py
+++ b/service.py
@@ -1 +1 @@
-def process():
+def process():
"""
            files = {"service.py": diff}
            class FakeResult:
                returncode = 0
                stdout = "caller.py:12: process('x')\ncaller2.py:4: process(1)\n"
                stderr = ""
            with patch.object(module.subprocess, "run", return_value=FakeResult()):
                radius = module.find_blast_radius(tmp, files)
            self.assertIn("process", radius)
            self.assertFalse(radius["process"]["broad"])
            self.assertEqual(len(radius["process"]["samples"]), 2)


class ReviewProfileTests(unittest.TestCase):
    """Coverage for the LLM-audit profile helpers (review-profile extraction)."""

    SAMPLE = {
        "a/logic.ts": (
            "diff --git a/a/logic.ts b/a/logic.ts\n"
            "--- a/a/logic.ts\n+++ b/a/logic.ts\n"
            "@@ -1,2 +1,2 @@\n"
            " def f(x){\n-  return x+1\n+  return x+100\n}\n"
        ),
    }

    def test_compute_diff_stats_counts_add_del_lines(self):
        stats, ta, td, tl = module.compute_diff_stats(self.SAMPLE)
        path = "a/logic.ts"
        self.assertIn(path, stats)
        a, d, n = stats[path]
        self.assertEqual(a, 1)   # one + return
        self.assertEqual(d, 1)   # one - return
        self.assertEqual(n, 8)   # whole unified blob lines
        self.assertEqual(ta, 1)
        self.assertEqual(td, 1)
        self.assertEqual(tl, 8)

    def test_summarize_change_kind_logic_and_test_and_config(self):
        self.assertEqual(module.summarize_change_kind("src/a.test.ts", 5, 2), "test")
        self.assertEqual(module.summarize_change_kind("tests/test_x.py", 5, 2), "test")
        self.assertEqual(module.summarize_change_kind("cfg.yaml", 5, 2), "config/docs/data")
        self.assertEqual(module.summarize_change_kind("README.md", 5, 0), "config/docs/data")
        self.assertEqual(module.summarize_change_kind("src/app.ts", 5, 2), "logic")
        # meta-only when nothing added/deleted
        self.assertEqual(module.summarize_change_kind("x.ts", 0, 0), "meta-only")

    def _profile_of(self, files, audit, strict):
        s, ta, td, tl = module.compute_diff_stats(files)
        return module.build_commit_profile(
            files, s, ta, td, tl, {}, "TestTarget", audit, strict_cap=strict
        )

    def test_profile_audit_default_wording(self):
        p = self._profile_of(self.SAMPLE, audit=True, strict=False)
        self.assertIn("default to showing the", p)
        self.assertIn("Files", p)
        self.assertIn("Target", p)

    def test_profile_strict_wording(self):
        p = self._profile_of(self.SAMPLE, audit=True, strict=True)
        self.assertIn("--strict-cap is set", p)

    def test_profile_working_tree_wording(self):
        p = self._profile_of(self.SAMPLE, audit=False, strict=False)
        self.assertIn("working-tree", p)


class SubmoduleGitlinkTests(unittest.TestCase):
    def test_is_gitlink_and_extract_subproject_commits(self):
        content = (
            "diff --git a/arch-web b/arch-web\n"
            "index b3c3826..3c182b5 160000\n"
            "--- a/arch-web\n"
            "+++ b/arch-web\n"
            "@@ -1 +1 @@\n"
            "-Subproject commit b3c38269dbbcbc609c0554ab70fed7d1e7208873\n"
            "+Subproject commit 3c182b54c09b6a5f05924c673faf52bf18ad8eb8\n"
        )
        self.assertTrue(module.is_gitlink(content))
        old_sha, new_sha = module.extract_subproject_commits(content)
        self.assertEqual(old_sha, "b3c38269dbbcbc609c0554ab70fed7d1e7208873")
        self.assertEqual(new_sha, "3c182b54c09b6a5f05924c673faf52bf18ad8eb8")

    def test_find_submodule_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            gitmodules = Path(tmp) / ".gitmodules"
            gitmodules.write_text(
                '[submodule "arch-web"]\n\tpath = arch-web\n\turl = ...\n',
                encoding="utf-8"
            )
            prefix = module.find_submodule_prefix(tmp, "arch-web/src/components/Header.tsx")
            self.assertEqual(prefix, "arch-web")
            # Path not in submodule
            self.assertIsNone(module.find_submodule_prefix(tmp, "root-file.ts"))

    def test_expand_submodule_diff_uninitialized_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Submodule dir does not exist locally
            expanded, skipped, err = module.expand_submodule_diff(
                tmp, "nonexistent-sub", "b3c3826", "3c182b5"
            )
            self.assertIsNone(expanded)
            self.assertIn("not found or not initialized", err)

    def test_expand_submodule_diff_mocked_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            sub_dir = Path(tmp) / "sub"
            sub_dir.mkdir()
            (sub_dir / ".git").mkdir()

            mock_inner_diff = (
                "diff --git a/src/app.ts b/src/app.ts\n"
                "--- a/src/app.ts\n"
                "+++ b/src/app.ts\n"
                "@@ -1,2 +1,2 @@\n"
                "-old()\n"
                "+new()\n"
                "diff --git a/package-lock.json b/package-lock.json\n"
                "--- a/package-lock.json\n"
                "+++ b/package-lock.json\n"
                "@@ -1 +1 @@\n"
                "-1\n"
                "+2\n"
            )

            class FakeProc:
                returncode = 0
                stdout = mock_inner_diff
                stderr = ""

            with patch.object(module.subprocess, "run", return_value=FakeProc()):
                expanded, skipped, err = module.expand_submodule_diff(
                    tmp, "sub", "sha1", "sha2"
                )
                self.assertIsNone(err)
                self.assertIn("sub/src/app.ts", expanded)
                self.assertIn("diff --git a/sub/src/app.ts b/sub/src/app.ts", expanded["sub/src/app.ts"])
                self.assertIn("--- a/sub/src/app.ts", expanded["sub/src/app.ts"])
                self.assertIn("+++ b/sub/src/app.ts", expanded["sub/src/app.ts"])
                # package-lock.json was recognized as noise and skipped
                self.assertNotIn("sub/package-lock.json", expanded)
                self.assertIn("sub/package-lock.json", skipped)

    def test_real_submodule_bump_integration(self):
        import subprocess, sys
        with tempfile.TemporaryDirectory() as tmpdir:
            sub_repo = Path(tmpdir) / "sub"
            sub_repo.mkdir()
            subprocess.run(["git", "init"], cwd=sub_repo, check=True, stdout=subprocess.DEVNULL)
            subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=sub_repo, check=True)
            subprocess.run(["git", "config", "user.name", "test"], cwd=sub_repo, check=True)
            (sub_repo / "service.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=sub_repo, check=True)
            subprocess.run(["git", "commit", "-m", "sub v1"], cwd=sub_repo, check=True, stdout=subprocess.DEVNULL)
            c1 = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=sub_repo, text=True).strip()

            (sub_repo / "service.py").write_text("def helper():\n    return 2\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=sub_repo, check=True)
            subprocess.run(["git", "commit", "-m", "sub v2"], cwd=sub_repo, check=True, stdout=subprocess.DEVNULL)
            c2 = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=sub_repo, text=True).strip()

            main_repo = Path(tmpdir) / "main"
            main_repo.mkdir()
            subprocess.run(["git", "init"], cwd=main_repo, check=True, stdout=subprocess.DEVNULL)
            subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=main_repo, check=True)
            subprocess.run(["git", "config", "user.name", "test"], cwd=main_repo, check=True)
            (main_repo / "main.py").write_text("# root\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=main_repo, check=True)
            subprocess.run(["git", "commit", "-m", "root init"], cwd=main_repo, check=True, stdout=subprocess.DEVNULL)

            subprocess.run(["git", "-c", "protocol.file.allow=always", "submodule", "add", str(sub_repo), "arch-web"], cwd=main_repo, check=True, stdout=subprocess.DEVNULL)
            subprocess.run(["git", "checkout", c1], cwd=main_repo / "arch-web", check=True, stderr=subprocess.DEVNULL)
            subprocess.run(["git", "add", "arch-web"], cwd=main_repo, check=True)
            subprocess.run(["git", "commit", "-m", "add sub at v1"], cwd=main_repo, check=True, stdout=subprocess.DEVNULL)

            subprocess.run(["git", "checkout", c2], cwd=main_repo / "arch-web", check=True, stderr=subprocess.DEVNULL)
            subprocess.run(["git", "add", "arch-web"], cwd=main_repo, check=True)
            subprocess.run(["git", "commit", "-m", "bump arch-web to v2"], cwd=main_repo, check=True, stdout=subprocess.DEVNULL)
            bump_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=main_repo, text=True).strip()

            res = subprocess.run([sys.executable, str(SCRIPT), "--commit", bump_sha], cwd=main_repo, capture_output=True, text=True)
            self.assertEqual(res.returncode, 0)
            self.assertIn("arch-web/service.py", res.stdout)
            self.assertIn("return 2", res.stdout)


if __name__ == "__main__":
    unittest.main()
