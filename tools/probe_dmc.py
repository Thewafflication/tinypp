"""Record optional compile-only DMC comparison probes from the pinned tree.

DMC is corroboration, not a normative oracle or an x64 backend. These probes
never link DMC objects into Tiny++ output and never count as native x64 runs.
All inputs, objects, output and binary identity stay in a fresh output folder.
"""

import datetime
import hashlib
import json
import subprocess
import uuid
from pathlib import Path


def probe():
    """Run isolated known-positive and diagnosable-negative comparison cases."""
    root = Path(__file__).resolve().parents[1]
    compiler = root / "dmc/bin/dmc.exe"
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-")
    output = root / "output/dmc-comparison" / (stamp + uuid.uuid4().hex[:8])
    output.mkdir(parents=True)
    banner = subprocess.run(
        [str(compiler)], capture_output=True, timeout=15,
    )
    inputs = [
        ("scalar", "int f(int x){return x+1;} int main(){return f(41);}", True),
        ("bool-overload", "int f(int x){return 11;}"
         "int f(bool x){return 22;} int main(){return f(true);}", True),
        ("recursion", "int f(int n){return n<2 ? 1 : n*f(n-1);}"
         "int main(){return f(5);}", True),
        ("scope-loop", "int main(){int n=0;while(n<5){n=n+1;}return n;}",
         True),
        ("undeclared", "int main(){return missing;}", False),
        ("ambiguous", "int f(int,bool);int f(bool,int);"
         "int main(){return f(true,true);}", False),
        ("void-expression-return", "void g(){}void f(){return g();}", True),
        ("namespace-alias", "namespace N{int f(){return 42;}}"
         "namespace A=N;namespace A=A;int main(){return A::f();}", True),
        ("void-object", "void n;", False),
        ("namespace-alias-retarget", "namespace N{}namespace M{}"
         "namespace A=N;namespace A=M;", False),
    ]
    records = []
    for name, text, accepted in inputs:
        directory = output / name
        directory.mkdir()
        source = directory / "probe.cpp"
        source.write_text(text + "\n", encoding="ascii")
        arguments = [str(compiler), "-A", "-mn", "-c", "probe.cpp"]
        began = datetime.datetime.now(datetime.timezone.utc).isoformat()
        child = subprocess.run(
            arguments, cwd=directory, capture_output=True, timeout=15,
        )
        obj = directory / "probe.obj"
        matched = child.returncode == 0 and obj.is_file() if accepted else (
            child.returncode == 1 and bool(child.stdout or child.stderr)
            and not obj.exists()
        )
        records.append({
            "name": name, "argv": arguments, "started": began,
            "finished": datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat(),
            "input_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "expected_acceptance": accepted, "exit_status": child.returncode,
            "stdout": child.stdout.decode(errors="replace"),
            "stderr": child.stderr.decode(errors="replace"),
            "object_sha256": hashlib.sha256(obj.read_bytes()).hexdigest()
            if obj.exists() else None,
            "status": "Pass" if matched else "Fail",
        })
        print(f"{records[-1]['status']}: DMC {name}")
    (output / "results.json").write_text(json.dumps({
        "kind": "Optional DMC comparison; compile-only Windows x86 (-mn)",
        "compiler_sha256": hashlib.sha256(compiler.read_bytes()).hexdigest(),
        "banner": (banner.stdout + banner.stderr).decode(errors="replace"),
        "results": records,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"DMC comparison evidence: {output}")
    return any(record["status"] != "Pass" for record in records)


if __name__ == "__main__":
    raise SystemExit(bool(probe()))
