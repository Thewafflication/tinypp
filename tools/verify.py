"""Run canonical local compiler-foundation checks with immutable run logs.

Build/test Debug and Release, inspect owned source documentation, and run the
WSP analyzer profile. Every command's original output survives a later rerun.
This dispatcher verifies the experimental foundation, not all C++98 or WSP.
"""

import datetime
import json
import subprocess
import sys
import uuid
from pathlib import Path

from evidence import source_snapshot


def verify():
    """Run every foundation gate, retaining failures and returning status."""
    root = Path(__file__).resolve().parents[1]
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-")
    output = root / "output/verification" / (stamp + uuid.uuid4().hex[:8])
    output.mkdir(parents=True)
    baseline = source_snapshot(root)
    records = []
    commands = [
        ("configure", ["cmake", "-S", ".", "-B", "output/build", "-G",
                       "Visual Studio 17 2022", "-A", "x64"]),
    ]
    for configuration in ("Debug", "Release"):
        commands += [
            (f"build-{configuration}", ["cmake", "--build", "output/build",
                                       "--config", configuration]),
            (f"test-{configuration}", ["ctest", "--test-dir", "output/build",
                                      "-C", configuration,
                                      "--output-on-failure"]),
        ]
    commands += [
        ("doxygen", ["doxygen", "Doxyfile"]),
        ("analysis", [sys.executable, "tools/analyze.py",
                      "--build", "output/build"]),
    ]
    for name, arguments in commands:
        record = {
            "gate": name, "argv": arguments,
            "started": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        try:
            result = subprocess.run(
                arguments, cwd=root, capture_output=True, text=True,
                timeout=300,
            )
            text = result.stdout + result.stderr
            record["exit_status"] = result.returncode
            record["status"] = "Pass" if result.returncode == 0 else "Fail"
        except (OSError, subprocess.TimeoutExpired) as error:
            text = str(error)
            record["status"] = "Blocked"
            record["reason"] = text
        record["finished"] = datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()
        (output / (name + ".txt")).write_text(text, encoding="utf-8")
        record["log"] = name + ".txt"
        records.append(record)
        (output / "results.json").write_text(json.dumps({
            "kind": "Experimental foundation gate run; no conformance claim",
            "results": records,
        }, indent=2) + "\n", encoding="utf-8")
        print(f"{record['status']}: {name}", flush=True)
        if record["status"] != "Pass":
            print(text, flush=True)
            # Never test stale binaries after a failed configure or build.
            if name == "configure" or name.startswith("build-"):
                break
    complete = len(records) == len(commands)
    after = source_snapshot(root)
    stable = baseline == after
    records.append({
        "gate": "input-stability", "status": "Pass" if stable else
        "Inconclusive", "reason": "Start/end controlled input comparison",
    })
    (output / "results.json").write_text(json.dumps({
        "kind": "Experimental foundation gate run; no conformance claim",
        "results": records,
    }, indent=2) + "\n", encoding="utf-8")
    (output / "source-sha256.json").write_text(json.dumps({
        "before": baseline, "after": after,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"Verification evidence: {output}", flush=True)
    return not complete or any(
        record["status"] != "Pass" for record in records
    )


if __name__ == "__main__":
    raise SystemExit(bool(verify()))
