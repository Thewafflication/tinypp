"""Measure configured DMC semantic import graphs with the recorded D compiler.

This is a semantic-import inventory, not a linker or extraction closure.
It reads a successful isolated build and never changes the dependency tree.
"""

import argparse
import datetime
import json
import re
import subprocess
import uuid
from pathlib import Path

from evidence import digest, source_snapshot


def parse_dependencies(text, source):
    """Parse DMD 2.092 dependency edges, rejecting unrecognized records."""
    pattern = re.compile(
        r"^(\S+) \((.*?)\) : (public|private|protected|package) : "
        r"(\S+) \((.*?)\)(?::(.*))?$"
    )
    edges = []
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        match = pattern.fullmatch(line)
        if not match:
            raise ValueError(f"Unrecognized dependency record at {number}")
        parent, first, visibility, child, second, symbols = match.groups()
        paths = []
        for value in (first, second):
            path = (source / value.replace("\\\\", "\\")).resolve()
            if not path.is_file():
                raise ValueError(f"Dependency source missing: {path}")
            paths.append(str(path))
        edges.append({
            "from_module": parent, "from_path": paths[0],
            "visibility": visibility, "to_module": child,
            "to_path": paths[1], "symbols": symbols or "",
        })
    if not edges:
        raise ValueError("Empty dependency graph")
    return edges


def reachable_paths(seed, edges):
    """Traverse physical paths so import aliases do not split one module."""
    graph = {}
    for edge in edges:
        graph.setdefault(edge["from_path"], set()).add(edge["to_path"])
    visited, pending = set(), [str(seed)]
    while pending:
        current = pending.pop()
        if current not in visited:
            visited.add(current)
            pending.extend(graph.get(current, ()))
    return visited


def trace(options):
    """Retain raw imports, commands, hashes and per-seed reachability."""
    root = Path(__file__).resolve().parents[1]
    baseline = source_snapshot(root)
    record = options.build_record.resolve()
    source = record.parent / "source"
    dmd = options.dmd.resolve()
    build = json.loads(record.read_text(encoding="utf-8"))
    if (build.get("status") != "Pass" or
            build["tools_sha256"].get(str(dmd)) != digest(dmd)):
        raise ValueError("DMD does not match a successful source build")
    expected = dict(build["copied_input_sha256"])
    expected.update(build["generated_source_sha256"])
    if any(digest(source / name) != value
           for name, value in expected.items()):
        raise ValueError("Isolated build inputs changed since source build")
    binaries = {str(path): digest(path) for path in (dmd, record)}
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-")
    output = root / "output/dmc-dependencies" / (stamp + uuid.uuid4().hex[:8])
    output.mkdir(parents=True)
    results, imported = [], {}
    for name in ("dscope.d", "dtype.d", "nspace.d", "exp.d", "eh.d", "rtti.d"):
        raw = output / (name + ".deps")
        arguments = [str(dmd), "-o-", "-c", "-betterC", "-noboundscheck",
                     "-mv=dmd.backend=.", "-mv=tk=tk", "-version=SCPP",
                     "-deps=" + str(raw), name]
        current = {
            "seed": name, "argv": arguments, "status": "Fail",
            "started": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        try:
            child = subprocess.run(arguments, cwd=source, capture_output=True,
                                   timeout=30)
            current.update({
                "exit_status": child.returncode,
                "stdout": child.stdout.decode(errors="replace"),
                "stderr": child.stderr.decode(errors="replace"),
            })
            if child.returncode:
                raise ValueError("DMD semantic analysis failed")
            edges = parse_dependencies(raw.read_text(encoding="utf-8"), source)
            paths = reachable_paths(source / name, edges)
            local = sorted(path for path in paths
                           if Path(path).is_relative_to(source))
            current.update({
                "status": "Pass", "edges": edges,
                "raw_sha256": digest(raw), "reachable_paths": sorted(paths),
                "local_paths": local,
                "direct_local_paths": sorted({edge["to_path"] for edge in
                    edges if edge["from_path"] == str(source / name) and
                    Path(edge["to_path"]).is_relative_to(source)}),
            })
            for edge in edges:
                for field in ("from_path", "to_path"):
                    path = edge[field]
                    actual = digest(Path(path))
                    if path in imported and imported[path] != actual:
                        raise ValueError("Import changed between seed runs")
                    imported[path] = actual
        except subprocess.TimeoutExpired as error:
            current.update({
                "error": "DMD analysis timed out",
                "stdout": (error.stdout or b"").decode(errors="replace"),
                "stderr": (error.stderr or b"").decode(errors="replace"),
            })
        except (OSError, ValueError) as error:
            current["status"] = "Fail"
            current["error"] = str(error)
        current["finished"] = datetime.datetime.now(
            datetime.timezone.utc).isoformat()
        results.append(current)
        print(f"{current['status']}: configured imports for {name}", flush=True)
    stable = (baseline == source_snapshot(root) and binaries == {
        str(path): digest(path) for path in (dmd, record)
    } and all(digest(source / name) == value
              for name, value in expected.items()) and all(
        Path(path).is_file() and digest(Path(path)) == value
        for path, value in imported.items()))
    (output / "results.json").write_text(json.dumps({
        "kind": "Configured SCPP semantic imports; not extraction closure",
        "parent_requirements_verified": False,
        "requirement_ids": ["REQ-0035", "REQ-0044"],
        "results": results, "baseline_stable": stable,
        "input_sha256": baseline, "binary_input_sha256": binaries,
        "import_sha256": imported,
        "limits": ["No symbol-level use or link dependency analysis",
                   "No allocation, global-state or thread-safety proof",
                   "One SCPP configuration; imports may include unused code"],
    }, indent=2) + "\n", encoding="utf-8")
    print(f"Evidence: {output}")
    return not stable or any(row["status"] != "Pass" for row in results)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dmd", type=Path, required=True)
    parser.add_argument("--build-record", type=Path, required=True)
    raise SystemExit(bool(trace(parser.parse_args())))
