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


if __name__ == "__main__":
    unittest.main()
