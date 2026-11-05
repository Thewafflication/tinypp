"""Run bounded Win32 probes using a recorded source-built DMC compiler.

This optional feasibility tool uses the distribution driver only to link
objects. It does not replace Tiny++ or verify the complete C++98 language.
"""

import argparse
import datetime
import json
import struct
import subprocess
import uuid
from pathlib import Path

from evidence import digest, source_snapshot


def probe(options):
    """Compile, link and execute independent semantic partitions."""
    root = Path(__file__).resolve().parents[1]
    baseline = source_snapshot(root)
    compiler = options.compiler.resolve()
    record = options.build_record.resolve()
    build = json.loads(record.read_text(encoding="utf-8"))
    if (build.get("status") != "Pass" or
            build.get("output_sha256") != digest(compiler)):
        raise ValueError("Compiler does not match successful build record")
    binaries = (compiler, record, root / "dmc/bin/dmc.exe",
                root / "dmc/bin/link.exe", root / "dmc/bin/optlink.exe")
    binary_baseline = {str(path): digest(path) for path in binaries}
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-")
    output = root / "output/dmc-native" / (stamp + uuid.uuid4().hex[:8])
    output.mkdir(parents=True)
    fixtures = {
        "scalar": "int main(){return 42;}",
        "using-namespace": "namespace N{int f(){return 42;}}"
        "namespace M{using namespace N;int g(){return f();}}"
        "int main(){return M::g();}",
        "virtual-dispatch": "struct B{virtual int f(){return 3;}};"
        "struct D:B{int f(){return 42;}};"
        "int main(){D d;B* p=&d;return p->f();}",
        "normal-cleanup": "struct G{int* p;G(int& n):p(&n){++*p;}"
        "~G(){++*p;}};int main(){int n=0;{G g(n);}return n==2?42:1;}",
        "exception-handler": "int main(){try{throw 42;}"
        "catch(int n){return n;}}",
        "exceptional-cleanup": "struct G{int* p;G(int& n):p(&n){++*p;}"
        "~G(){++*p;}};void f(int& n){G g(n);throw 7;}"
        "int main(){int n=0;try{f(n);}catch(int){return n==2?42:1;}}",
        "temporary-reference-lifetime": "struct G{int* p;G(int& n):p(&n){}"
        "~G(){++*p;}};int main(){int n=0;"
        "{const G& g=G(n);if(n)return 1;}return n==1?42:2;}",
        "argument-dependent-lookup": "namespace N{struct A{};"
        "int f(A){return 42;}}int main(){N::A a;return f(a);}",
    }
    results = []
    for name, text in fixtures.items():
        directory = output / name
        directory.mkdir()
        source = directory / "probe.cpp"
        source.write_text(text + "\n", encoding="ascii")
        current = {"name": name, "status": "Not run", "commands": [],
                   "source_sha256": digest(source)}
        commands = [
            ([str(compiler), "-A", "-Ae", "-Ar", "-mn", "-c",
              f"-I{root / 'dmc/include'}", "probe.cpp"], 0),
            ([str(root / "dmc/bin/dmc.exe"), "-mn", "probe.obj"], 0),
            ([str(directory / "probe.exe")], 42),
        ]
        try:
            for arguments, expected in commands:
                began = datetime.datetime.now(datetime.timezone.utc)
                child = subprocess.run(
                    arguments, cwd=directory, capture_output=True, timeout=15,
                )
                current["commands"].append({
                    "argv": arguments, "started": began.isoformat(),
                    "finished": datetime.datetime.now(
                        datetime.timezone.utc
                    ).isoformat(),
                    "exit_status": child.returncode,
                    "expected_exit_status": expected,
                    "stdout": child.stdout.decode(errors="replace"),
                    "stderr": child.stderr.decode(errors="replace"),
                })
                if child.returncode != expected:
                    raise AssertionError("Unexpected process exit status")
            current["status"] = "Pass"
            data = (directory / "probe.exe").read_bytes()
            pe = struct.unpack_from("<I", data, 60)[0]
            if (data[:2] != b"MZ" or data[pe:pe + 4] != b"PE\0\0" or
                    struct.unpack_from("<H", data, pe + 4)[0] != 0x14C):
                raise AssertionError("Expected native PE x86 executable")
        except subprocess.TimeoutExpired as error:
            current["commands"].append({
                "argv": arguments, "started": began.isoformat(),
                "timeout_seconds": 15, "exit_status": None,
                "stdout": (error.stdout or b"").decode(errors="replace"),
                "stderr": (error.stderr or b"").decode(errors="replace"),
            })
            current["status"] = "Fail"
            current["reason"] = "Child process timed out"
        except (OSError, AssertionError,
                struct.error) as error:
            current["status"] = "Fail"
            current["reason"] = str(error)
        for suffix in ("obj", "exe"):
            path = directory / ("probe." + suffix)
            if path.exists():
                current[suffix + "_sha256"] = digest(path)
        results.append(current)
        print(f"{current['status']}: source-built Win32 {name}", flush=True)
    stable = baseline == source_snapshot(root) and binary_baseline == {
        str(path): digest(path) for path in binaries
    }
    (output / "results.json").write_text(json.dumps({
        "kind": "Source-built DMC Win32 native feasibility; partial evidence",
        "results": results, "baseline_stable": stable,
        "input_sha256": baseline, "compiler_sha256": digest(compiler),
        "binary_input_sha256": binary_baseline,
        "link_driver_sha256": digest(root / "dmc/bin/dmc.exe"),
        "build_record": str(record), "build_record_sha256": digest(record),
        "compiler_d_assertions_enabled": build.get("d_assertions_enabled"),
        "source_copy_adaptations": build["source_copy_adaptations"],
        "limits": ["Win32 only; no Tiny++ x64 integration or ABI proof",
                   "No full capability TC or C++98 conformance closure"],
    }, indent=2) + "\n", encoding="utf-8")
    print(f"Evidence: {output}")
    return not stable or any(row["status"] != "Pass" for row in results)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, required=True)
    parser.add_argument("--build-record", type=Path, required=True)
    raise SystemExit(bool(probe(parser.parse_args())))
