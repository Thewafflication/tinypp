"""Hash controlled project inputs and dependency identities for local runs.

Snapshots identify exact bytes without recording their contents. Comparing
start/end snapshots detects a changed baseline; it is not a filesystem lock.
Generated output and Python caches are excluded from the controlled inputs.
"""

import hashlib
import subprocess
from pathlib import Path


def digest(path):
    """Return the SHA-256 hex digest of a readable local file's exact bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_snapshot(root):
    """Return controlled relative input names mapped to content identities."""
    root = Path(root)
    paths = [root / name for name in (
        "README.md", "CMakeLists.txt", "Doxyfile", ".gitmodules",
    )]
    extensions = {".cpp", ".hpp", ".c", ".h", ".py", ".md", ".tex",
                  ".csv", ".json", ".yml", ".yaml", ".ps1", ".cmake"}
    for directory in ("src", "tools", "tests", "docs", ".github"):
        paths.extend(
            path for path in (root / directory).rglob("*")
            if path.is_file() and path.suffix in extensions
        )
    result = {
        path.relative_to(root).as_posix(): digest(path)
        for path in sorted(paths) if path.is_file()
    }
    # Upstream quoted includes can prefer ignored in-source generated headers.
    for relative in ("tinycc/config.h", "tinycc/tccdefs_.h"):
        path = root / relative
        if path.is_file():
            result[relative] = digest(path)
    for name in ("tinycc", "dmc", "wsp"):
        arguments = ["git", "-C", str(root / name)]
        revision = subprocess.check_output(arguments + ["rev-parse", "HEAD"])
        diff = subprocess.check_output(arguments + ["diff", "--binary", "HEAD"])
        result[f"dependency:{name}:revision"] = revision.decode().strip()
        result[f"dependency:{name}:diff"] = hashlib.sha256(diff).hexdigest()
        untracked = subprocess.check_output(arguments + [
            "ls-files", "--others", "--exclude-standard", "-z",
        ])
        for relative in untracked.decode("utf-8").split("\0"):
            if relative:
                result[f"dependency:{name}:{relative}"] = digest(
                    root / name / relative
                )
    return result
