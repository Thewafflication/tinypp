"""Exercise the isolated DMC signature worker and a fail-closed consumer.

Native results check instrumentation transparency, not function-body handoff.
No DMC pointers or implementation structures cross the process boundary.
"""

import argparse
import datetime
import json
import os
import struct
import subprocess
import uuid
from pathlib import Path

from evidence import digest, source_snapshot
from semantic_signatures import read_signatures


def observe(name, records):
    """Check source-level facts independently of the serialized schema."""
    def named(identifier):
        """Find source identifiers without assuming an internal owner name."""
        encoded = identifier.encode("ascii").hex()
        return [row for row in records if row["path_hex"][-1] == encoded]

    answer = named("answer")
    assert len(answer) == 1 and answer[0]["linkage"] == "c"
    assert answer[0]["result"]["kind"] == "int"
    if name == "qualified-types":
        row = named("sum")[0]
        assert row["path_hex"][-2:] == ["N".encode().hex(), "73756d"]
        assert row["result"]["kind"] == "long"
        args = row["parameters"]
        assert [arg["kind"] for arg in args] == [
            "unsigned-int", "lvalue-reference", "pointer"]
        assert args[1]["to"]["kind"] == "int"
        assert args[2]["to"]["kind"] == "long" and args[2]["to"]["const"]
        assert named("truth")[0]["result"]["kind"] == "bool"
    elif name == "member-cv":
        rows = named("f")
        assert len(rows) == 2
        assert {row["const_member"] for row in rows} == {False, True}
        assert all(row["linkage"] == "c++" for row in rows)
    elif name == "record-value":
        row = named("echo")[0]
        assert row["result"] == row["parameters"][0]
        assert row["result"]["kind"] == "record"
        assert row["result"]["bytes"] == 8
        assert row["result"]["alignment"] == 4
    elif name == "constructor-destructor":
        categories = {row["function_kind"] for row in records}
        assert {"constructor", "destructor"}.issubset(categories)
        assert all(row["result"] is None for row in records
                   if row["function_kind"] != "function")
    elif name == "target-layout":
        row = named("echo_layout")[0]
        size, alignment = (16, 8) if row["target"] == "windows-x64" else (8, 4)
        assert row["result"] == row["parameters"][0]
        assert row["result"]["bytes"] == size
        assert row["result"]["alignment"] == alignment
    elif name == "language-linkage":
        assert named("cppf")[0]["linkage"] == "c++"
        assert named("cf")[0]["linkage"] == "c"


def probe(options):
    """Compile real inputs, validate copied metadata and execute positives."""
    root = Path(__file__).resolve().parents[1]
    baseline = source_snapshot(root)
    compiler = options.compiler.resolve()
    record = options.build_record.resolve()
    linker = options.linker.resolve()
    cc = linker.parent / "cl.exe"
    driver = root / "dmc/bin/dmc.exe"
    build = json.loads(record.read_text(encoding="utf-8"))
    if (build.get("status") != "Pass" or
            build["output_sha256"] != digest(compiler) or not any(
                "signature stream" in patch["change"]
                for patch in build["source_copy_adaptations"])):
        raise ValueError("Compiler lacks a matching signature-worker build")
    tools = [compiler, record, linker, cc] if options.target == "windows-x64" \
        else [compiler, record, driver, root / "dmc/bin/optlink.exe"]
    binaries = {str(path): digest(path) for path in tools}
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-")
    output = root / "output/dmc-semantics" / (stamp + uuid.uuid4().hex[:8])
    output.mkdir(parents=True)
    fixtures = {
        "qualified-types": "namespace N{bool truth(bool n){return n;}"
        "long sum(unsigned n,int& r,const long* p){r+=n;return r+*p;}}"
        'extern "C" int answer(){int n=1;long k=40;return N::sum(1,n,&k);}',
        "member-cv": "struct C{int f()const;int f();};"
        "int C::f()const{return 1;}int C::f(){return 2;}"
        'extern "C" int answer(){C c;const C& r=c;return c.f()+r.f()+39;}',
        "record-value": "struct P{int x;long y;};P echo(P p){return p;}"
        'extern "C" int answer(){P p={12,30};P q=echo(p);return q.x+q.y;}',
        "target-layout": "struct Layout{void* p;int n;};"
        "Layout echo_layout(Layout v){return v;}"
        'extern "C" int answer(){int n=42;Layout v={&n,0};'
        "Layout w=echo_layout(v);return *(int*)w.p;}",
        "constructor-destructor": "struct G{int* p;G(int&);~G();};"
        "G::G(int& n):p(&n){++*p;}G::~G(){++*p;}"
        'extern "C" int answer(){int n=0;{G g(n);}return n==2?42:1;}',
        "language-linkage": 'int cppf(){return 40;}extern "C" int cf()'
        '{return 2;}extern "C" int answer(){return cppf()+cf();}',
        "unsupported-function-pointer": "int f(){return 42;}"
        'int(*factory())(){return &f;}extern "C" int answer()'
        "{return factory()();}",
        "export-disabled": 'extern "C" int answer(){return 42;}',
        "export-io-failure": 'extern "C" int answer(){return 42;}',
    }
    results = []
    for name, text in fixtures.items():
        directory = output / name
        directory.mkdir()
        stream = directory / "signatures.jsonl"
        if options.target == "windows-x86":
            text += "int main(){return answer();}"
        (directory / "probe.cpp").write_text(text + "\n", encoding="ascii")
        (directory / "caller.c").write_text(
            "extern int answer(void);int entry(void){return answer();}\n",
            encoding="ascii")
        environment = os.environ.copy()
        environment.pop("TINYPP_SEMANTIC_EXPORT", None)
        if name != "export-disabled":
            environment["TINYPP_SEMANTIC_EXPORT"] = str(
                directory if name == "export-io-failure" else stream)
        current = {"name": name, "status": "Fail", "commands": [],
                   "native_executed": False}
        arguments = [str(compiler), "-c", "-m64" if options.target ==
                     "windows-x64" else "-mn", "probe.cpp"]
        expected = 1 if name == "export-io-failure" else 0
        try:
            def run(command, code):
                """Retain timing and diagnostics for every process outcome."""
                began = datetime.datetime.now(datetime.timezone.utc)
                try:
                    child = subprocess.run(command, cwd=directory,
                        env=environment, capture_output=True, timeout=15)
                except subprocess.TimeoutExpired as error:
                    current["commands"].append({
                        "argv": command, "started": began.isoformat(),
                        "timeout_seconds": 15,
                        "stdout": (error.stdout or b"").decode(
                            errors="replace"),
                        "stderr": (error.stderr or b"").decode(
                            errors="replace"),
                    })
                    raise ValueError("Worker command timed out") from error
                current["commands"].append({
                    "argv": command, "expected_exit_status": code,
                    "exit_status": child.returncode,
                    "started": began.isoformat(),
                    "finished": datetime.datetime.now(
                        datetime.timezone.utc).isoformat(),
                    "stdout": child.stdout.decode(errors="replace"),
                    "stderr": child.stderr.decode(errors="replace"),
                })
                if child.returncode != code:
                    raise ValueError("Unexpected worker command status")
                return child

            child = run(arguments, expected)
            if name == "export-io-failure":
                assert b"semantic signature export failed" in child.stderr
                current["control"] = "Producer output failure rejected"
            else:
                if name == "export-disabled":
                    assert not stream.exists()
                elif name == "unsupported-function-pointer":
                    try:
                        read_signatures(stream, options.target)
                    except ValueError as error:
                        assert str(error) == "Unsupported signature type"
                        current["control"] = str(error)
                    else:
                        raise AssertionError("Unsupported handoff accepted")
                else:
                    signatures = read_signatures(stream, options.target)
                    observe(name, signatures)
                    current["signatures"] = signatures
                if options.target == "windows-x64":
                    run([str(cc), "/nologo", "/GS-", "/Zl", "/TC", "/c",
                         "/Focaller.obj", "caller.c"], 0)
                    run([str(linker), "/nologo", "/entry:entry",
                         "/subsystem:console", "/nodefaultlib",
                         "/out:probe.exe", "probe.obj", "caller.obj"], 0)
                else:
                    run([str(driver), "-mn", "probe.obj"], 0)
                image = (directory / "probe.exe").read_bytes()
                pe = struct.unpack_from("<I", image, 60)[0]
                machine = 0x8664 if options.target == "windows-x64" else 0x14c
                assert image[:2] == b"MZ" and image[pe:pe + 4] == b"PE\0\0"
                assert struct.unpack_from("<H", image, pe + 4)[0] == machine
                run([str(directory / "probe.exe")], 42)
                current["native_executed"] = True
            current["status"] = "Pass"
        except (OSError, ValueError, AssertionError, struct.error) as error:
            current["reason"] = str(error)
        current["artifact_sha256"] = {
            path.name: digest(path) for path in directory.iterdir()
            if path.is_file()
        }
        results.append(current)
        print(f"{current['status']}: semantic handoff {name}", flush=True)
    stable = baseline == source_snapshot(root) and binaries == {
        str(path): digest(path) for path in tools
    }
    (output / "results.json").write_text(json.dumps({
        "kind": "Experimental copied-signature process handoff",
        "parent_requirements_verified": False,
        "requirement_ids": ["REQ-0026", "REQ-0027", "REQ-0044"],
        "test_ids": ["TC-0026", "TC-0027", "TC-0044"],
        "target": options.target, "results": results,
        "baseline_stable": stable, "input_sha256": baseline,
        "binary_input_sha256": binaries,
        "source_copy_adaptations": build["source_copy_adaptations"],
        "limits": ["No function-body, lifetime or EH IR handoff",
                   "No production frontend replacement or conformance claim",
                   "Legacy native emission checks instrumentation only"],
    }, indent=2) + "\n", encoding="utf-8")
    print(f"Evidence: {output}")
    return not stable or any(row["status"] != "Pass" for row in results)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, required=True)
    parser.add_argument("--build-record", type=Path, required=True)
    parser.add_argument("--linker", type=Path, required=True)
    parser.add_argument("--target", choices=("windows-x86", "windows-x64"),
                        default="windows-x64")
    raise SystemExit(bool(probe(parser.parse_args())))
