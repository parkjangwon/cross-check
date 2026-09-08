import importlib.util
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "get_diff_context.py"

spec = importlib.util.spec_from_file_location("get_diff_context", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_parse_diff_filters_noise_but_keeps_source():
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

    assert "src/app.py" in files
    assert "package-lock.json" not in files
    assert "package-lock.json" in skipped


def test_extract_modified_python_symbol_from_hunk_context(tmp_path):
    source = tmp_path / "service.py"
    source.write_text(
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

    symbols = module.extract_modified_symbols(str(tmp_path), "service.py", diff)

    assert "process_request" in symbols
    assert "untouched" not in symbols


def test_extract_modified_go_method_and_excludes_common_builtins(tmp_path):
    source = tmp_path / "service.go"
    source.write_text(
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

    symbols = module.extract_modified_symbols(str(tmp_path), "service.go", diff)

    assert "ProcessUser" in symbols
    assert "log" not in symbols


def test_find_blast_radius_reports_external_usage(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "service.py").write_text(
        "def process_request(value):\n    return value\n",
        encoding="utf-8",
    )
    (tmp_path / "caller.py").write_text(
        "from service import process_request\n\nresult = process_request('x')\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-qm", "initial"],
        cwd=tmp_path,
        check=True,
    )
    (tmp_path / "service.py").write_text(
        "def process_request(value):\n    return value.strip()\n",
        encoding="utf-8",
    )
    diff = subprocess.run(
        ["git", "diff", "--no-color", "--unified=3", "HEAD"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    files, _ = module.parse_diff(diff)

    radius = module.find_blast_radius(str(tmp_path), files)

    assert "process_request" in radius
    assert any(sample[0] == "caller.py" for sample in radius["process_request"]["samples"])


def test_untracked_files_are_synthesized_as_diff(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    source = tmp_path / "new.py"
    source.write_text("def hello():\n    return 'hello'\n", encoding="utf-8")

    diffs, skipped = module.get_untracked_files_diff(str(tmp_path))

    assert skipped == []
    assert "new.py" in diffs
    assert "new file mode 100644" in diffs["new.py"]
    assert "+def hello():" in diffs["new.py"]


def test_binary_untracked_file_is_skipped(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    binary = tmp_path / "image.dat"
    binary.write_bytes(b"abc\x00def")

    diffs, skipped = module.get_untracked_files_diff(str(tmp_path))

    assert "image.dat" not in diffs
    assert "image.dat" in skipped


def test_non_code_files_never_produce_blast_radius_symbols(tmp_path):
    diff = """diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1 +1 @@
-Call process_request()
+Call process_request()
"""

    assert module.extract_modified_symbols(str(tmp_path), "README.md", diff) == []


def test_file_filter_is_considered_code_agnostic():
    assert module.is_code_file("src/main.java")
    assert module.is_code_file("src/main.rs")
    assert not module.is_code_file("README.md")
    assert not module.is_code_file("config.yaml")
