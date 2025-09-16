#!/usr/bin/env python3
"""
pattern_check.py
Scans changed .py and .ipynb files for risky patterns and exits 1 if any found.
"""

import sys
import re
import json
from pathlib import Path

# ---------------- CONFIG ----------------
PATTERNS = {
    "mnt_path": re.compile(r'["\']\/mnt\/[^"\']*["\']', re.IGNORECASE),
    "deltatable_forpath": re.compile(r'DeltaTable\s*\.forPath\s*\(', re.IGNORECASE),
    "option_path": re.compile(r'\.option\s*\(\s*["\']path["\']', re.IGNORECASE),
    "input_file_name": re.compile(r'\binput_file_name\s*\(', re.IGNORECASE)  # NEW
}

IGNORE_PATHS = []
EXTENSIONS = {".py", ".ipynb"}


# ---------------- HELPERS ----------------
def path_ignored(path_str):
    for ig in IGNORE_PATHS:
        if Path(path_str).match(ig):
            return True
    return False


def load_changed_files(file_path):
    if not file_path or not Path(file_path).exists():
        return []
    txt = Path(file_path).read_text().splitlines()
    return [line.strip() for line in txt if line.strip()]


def extract_code_from_ipynb(path: Path):
    try:
        nb = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    code_cells = []
    for i, cell in enumerate(nb.get("cells", []) or []):
        if cell.get("cell_type") == "code":
            src = cell.get("source", "")
            if isinstance(src, list):
                src = "".join(src)
            code_cells.append({"cell_index": i+1, "source": src})
    return code_cells


def scan_code_text(code_text, filename):
    findings = []
    for lineno, line in enumerate(code_text.splitlines(), start=1):
        stripped = line.strip()

        # Skip empty lines
        if not stripped:
            continue

        # Remove inline comments (everything after #)
        code_only = line.split("#", 1)[0].strip()
        if not code_only:  # line is comment-only
            continue

        # Scan only real code (without comments)
        for pname, patt in PATTERNS.items():
            if patt.search(code_only):
                findings.append({
                    "file": filename,
                    "line": lineno,
                    "pattern": pname,
                    "snippet": stripped
                })
    return findings


def main():
    changed_file_list_path = sys.argv[1] if len(sys.argv) > 1 else None
    changed_files = load_changed_files(changed_file_list_path)

    if not changed_files:
        print("No changed_files.txt or file is empty — scanning repo for .py/.ipynb")
        changed_files = [str(p.relative_to(Path.cwd())) for p in Path(".").rglob("*") if p.suffix in EXTENSIONS]

    results = []

    for f in changed_files:
        if not f or path_ignored(f):
            continue
        p = Path(f)
        if not p.exists():
            p = Path.cwd() / f
            if not p.exists():
                continue

        if p.suffix == ".py":
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            results.extend(scan_code_text(text, str(p)))

        elif p.suffix == ".ipynb":
            cells = extract_code_from_ipynb(p)
            for cell in cells:
                results.extend(scan_code_text(cell["source"], f"{p} (cell {cell['cell_index']})"))

    if not results:
        print("✅ No risky patterns found in changed files.")
        sys.exit(0)

    print("❌ Risky patterns detected:")
    for r in results:
        msg = f"Pattern '{r['pattern']}' found — {r['snippet']}"
        safe_msg = msg.replace("\n", " ").replace("\r", " ")
        print(f"::error file={r['file']},line={r['line']}::{safe_msg}")

    # Human-readable summary
    print("\nDetailed findings:")
    for r in results:
        print(f"- {r['file']}:{r['line']}  [{r['pattern']}] {r['snippet']}")

    sys.exit(1)


if __name__ == "__main__":
    main()
