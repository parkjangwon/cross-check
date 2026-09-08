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


if __name__ == "__main__":
    unittest.main()
