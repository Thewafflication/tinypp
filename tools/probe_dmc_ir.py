"""Run DMC semantic bodies through owned validation/lowering and TinyCC.

DMC objects are quarantined evidence, never target-link inputs. Unsupported
IR must fail before TinyCC runs. Templates and library implementation stay
outside this experimental scalar/object handoff.
"""

import argparse
import datetime
import json
import struct
import subprocess
import sys
import uuid
from pathlib import Path

from evidence import digest, source_snapshot
from semantic_ir import check_function_contract, compatible


def object_contracts(bodies):
    """Check explicit receiver binding in retained object streams."""
    calls = []
    pending = []
    for body in bodies:
        assert body["schema"] == "tinypp.function-ir.v2"
        function = body["function"]
        check_function_contract(function, "windows-x64")
        bindings = [item["type"] for item in body["variables"]
                    if item["storage"] == "parameter"]
        expected = ([function["receiver"]] if
                    function["receiver"] is not None else [])
        assert bindings == expected + function["parameters"]
        pending.extend(block["expression"] for block in body["blocks"])
    while pending:
        node = pending.pop()
        if node is None:
            continue
        if node["op"] == "call":
            function = node["function"]
            check_function_contract(function, "windows-x64")
            assert len(node["args"]) == len(function["parameters"])
            assert all(compatible(arg["type"], parameter) for arg, parameter
                       in zip(node["args"], function["parameters"]))
            assert (node["receiver"] is None) == \
                (function["receiver"] is None)
            if node["receiver"] is not None:
                assert compatible(node["receiver"]["type"],
                                  function["receiver"])
                pending.append(node["receiver"])
            assert compatible(node["type"], function["lowered_result"])
            calls.append(function)
        pending.extend(node.get("args", []))
    assert any(call["function_kind"] == "constructor" for call in calls)


def probe(options):
    """Retain end-to-end worker/IR/C/object/native evidence and controls."""
    root = Path(__file__).resolve().parents[1]
    baseline = source_snapshot(root)
    compiler = options.compiler.resolve()
    record = options.build_record.resolve()
    backend = options.backend.resolve()
    runtime = options.runtime.resolve()
    build = json.loads(record.read_text(encoding="utf-8"))
    if (build.get("status") != "Pass" or
            build["output_sha256"] != digest(compiler) or not any(
                "typed body stream" in patch["change"] for patch in
                build["source_copy_adaptations"])):
        raise ValueError("Compiler lacks a matching body-worker build")
    tools = [compiler, record, backend, backend.parent / "tinypp_tcc.dll"]
    tools += [path for path in runtime.rglob("*") if path.is_file()]
    binaries = {str(path): digest(path) for path in tools}
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-")
    output = root / "output/dmc-ir" / (stamp + uuid.uuid4().hex[:8])
    output.mkdir(parents=True)
    fixtures = {
        "scalar": ['extern "C" int answer(){return 42;}'],
        "standard-main": ['int helper(){return 42;}'
                          'int main(){return helper();}'],
        "implicit-main": ['int main(){}'],
        "header-path-spaces": ['#include "helper.h"\n'
                               'int main(){return helper();}'],
        "locals": ['extern "C" int answer(){int a=10;int b=4;'
                   'a+=b;return a*3;}'],
        "branch": ['int f(bool b){if(b)return 40;return 2;}'
                   'extern "C" int answer(){return f(true)+f(false);}'],
        "loop": ['extern "C" int answer(){int s=0;'
                 'for(int i=0;i<7;++i)s+=i;return s*2;}'],
        "recursion": ['int sum(int n){return n?n+sum(n-1):0;}'
                      'extern "C" int answer(){return sum(6)*2;}'],
        "overloads": ['int f(bool b){return b?40:1;}int f(int n){return n+2;}'
                      'extern "C" int answer(){return f(true)+f(0);}'],
        "namespaces": ['namespace N{int f(){return 40;}}'
                       'namespace M{using namespace N;int g(){return f()+2;}}'
                       'extern "C" int answer(){return M::g();}'],
        "static-member": ['struct G{static int f(int n){return n+2;}};'
                          'int main(){return G::f(40);}'],
        "argument-order": ['int f(int a,int b,int c){return a*100+b*10+c;}'
                           'extern "C" int answer(){return f(0,4,2);}'],
        "eight-arguments": ['int f(int a,int b,int c,int d,int e,int f,'
                            'int g,int h){return a+2*b+3*c+4*d+5*e+'
                            '6*f+7*g+8*h;}extern "C" int answer()'
                            '{return f(1,2,3,4,5,6,7,8)-162;}'],
        "comma-update": ['extern "C" int answer(){int a=20;'
                         'int b=(a++,a);return a+b;}'],
        "unsigned": ['unsigned f(unsigned n){return (n>>1)&255U;}'
                     'extern "C" int answer(){return (int)f(84U);}'],
        "reference-void-call": ['void add(int& n){n+=2;}'
                                'extern "C" int answer(){int n=40;'
                                'add(n);return n;}'],
        "reference-result": ['int& alias(int& n){return n;}'
                             'extern "C" int answer(){int n=40;'
                             'alias(n)+=2;return n;}'],
        "cross-unit": ['int helper(int);extern "C" int answer()'
                       '{return helper(20)+2;}',
                       'int helper(int n){return n*2;}'],
        "internal-collision": ['static int helper(){return 40;}int other();'
            'extern "C" int answer(){return helper()+other();}',
            'static int helper(){return 2;}int other(){return helper();}'],
        "unsupported-record": ['struct P{int a;};P echo(P p){return p;}'
                               'extern "C" int answer(){P p={42};'
                               'return echo(p).a;}'],
        "normal-lifetime": ['struct G{int* p;G(int& n):p(&n){++*p;}'
                                 '~G(){++*p;}};int main(){int n=0;'
                                 '{G g(n);}return n==2?42:1;}'],
        "qualified-member": ['struct G{int a,b;'
            'G(int x,int y):a(x),b(y){}int read()const volatile{return a+b;}'
            'static int f(int x){return x+2;}};'
            'int main(){G g(30,10);return g.read()+G::f(0);}'],
        "cross-unit-class": ['struct G{int* p;int v;G(int&,int);~G();'
            'int read()const;};int main(){int n=0;int v=0;'
            '{G g(n,40);v=g.read();}return n==2?v+2:1;}',
            'struct G{int* p;int v;G(int&,int);~G();int read()const;};'
            'G::G(int& n,int x):p(&n),v(x){++*p;}'
            'G::~G(){++*p;}int G::read()const{return v;}'],
        "early-return-cleanup": ['struct G{int* p;int id;'
            'G(int& n,int i):p(&n),id(i){*p=*p*10+id;}'
            '~G(){*p=*p*10+id+2;}};'
            'int f(int& n){G a(n,1);{G b(n,2);return 7;}}'
            'int main(){int n=0;int r=f(n);return n==1243&&r==7?42:1;}'],
        "member-cv-overloads": ['struct G{int v;G(int n):v(n){}'
            'int read(){return v+2;}int read()const{return v;}};'
            'int c(const G& g){return g.read();}'
            'int main(){G g(20);return g.read()+c(g);}'],
        "member-argument-order": ['struct G{int v;'
            'G(int a,int b):v(a*10+b){}int f(int a,int b){return v+a*10+b;}};'
            'int main(){G g(4,0);return g.f(0,2);}'],
        "unsupported-mutable": ['struct G{mutable int v;G():v(0){}'
            'int read()const{return ++v;}};'
            'int main(){G g;return g.read();}'],
        "unsupported-exception": ['int main(){try{throw 42;}'
                                  'catch(int n){return n;}}'],
        "unsupported-switch": ['int f(int n){switch(n){case 1:return 42;'
                               'default:return 1;}}extern "C" int answer()'
                               '{return f(1);}'],
        "unresolved-external": ['int missing();extern "C" int answer()'
                                '{return missing();}'],
    }
    controls = {
        "unsupported-record": "Unsupported IR record value result",
        "unsupported-mutable": "Invalid typed IR indirection",
        "unsupported-exception": "Compiler command failed",
        "unsupported-switch": "Invalid IR block exit or successor",
        "unresolved-external": "Unresolved IR function body",
    }
    selected = set(options.case or fixtures)
    if selected - set(fixtures):
        raise ValueError("Unknown IR probe case")
    results = []
    for name, sources in fixtures.items():
        if name not in selected:
            continue
        directory = output / (name + " with spaces" if name ==
                              "header-path-spaces" else name)
        directory.mkdir()
        current = {"name": name, "status": "Fail", "commands": [],
                   "tinycc_started": False, "native_executed": False}
        paths = []
        for index, text in enumerate(sources):
            source = directory / (f"source {index}.cpp" if name ==
                "header-path-spaces" else f"source{index}.cpp")
            source.write_text(text + "\n", encoding="ascii")
            paths.append(source)
        source_hashes = {str(path): digest(path) for path in paths}
        if name == "header-path-spaces":
            header = directory / "helper.h"
            header.write_text("inline int helper(){return 42;}\n",
                              encoding="ascii")
            source_hashes[str(header)] = digest(header)
        exe = directory / ("from ir.exe" if name == "header-path-spaces"
                           else "from-ir.exe")
        arguments = [sys.executable, str(root / "tools/compile_worker.py"),
            "--worker", str(compiler), "--build-record", str(record),
            "--backend", str(backend), "--runtime", str(runtime),
            "-o", str(exe)] + [str(path) for path in paths]
        try:
            child = subprocess.run(arguments, cwd=directory,
                capture_output=True, timeout=120)
            current["commands"].append({
                "argv": arguments, "exit_status": child.returncode,
                "stdout": child.stdout.decode(errors="replace"),
                "stderr": child.stderr.decode(errors="replace"),
            })
            summary = json.loads(child.stdout)
            report_path = Path(summary["evidence"])
            report = json.loads(report_path.read_text(encoding="utf-8"))
            current["compilation_evidence"] = str(report_path)
            current["tinycc_started"] = report["tinycc_started"]
            if name in ("normal-lifetime",
                        "qualified-member"):
                stream = report_path.parent / "body0.jsonl"
                bodies = [json.loads(line) for line in
                          stream.read_text(encoding="utf-8").splitlines()]
                object_contracts(bodies)
                identities = {(tuple(body["function"]["path_hex"]),
                               body["function"]["function_kind"])
                              for body in bodies}
                expected = {
                    (("6d61696e",), "function"),
                    (("47", "3f30"), "constructor"),
                }
                if name == "normal-lifetime":
                    expected.add((("47", "3f31"), "destructor"))
                    current["destructor_body_discovered"] = True
                else:
                    expected.update({(("47", "72656164"), "function"),
                                     (("47", "66"), "function")})
                    member = next(body["function"] for body in bodies if
                        body["function"]["path_hex"] == ["47", "72656164"])
                    assert member["const_member"]
                    assert member["volatile_member"]
                assert identities == expected
                current["object_contract_stream"] = str(stream)
                current["object_contract_sha256"] = digest(stream)
                current["explicit_receiver_contract"] = True
            if name in controls:
                assert child.returncode == 1 and report["status"] == "Fail"
                assert controls[name] in report["reason"]
                assert not report["tinycc_started"] and not exe.exists()
                current["control"] = report["reason"]
                if name == "unsupported-exception":
                    command = report["commands"][0]
                    assert command["exit_status"] == 1
                    assert "Compile all files with -Ae" in \
                        command["stdout"] + command["stderr"]
            else:
                assert child.returncode == 0 and report["status"] == "Pass"
                assert report["baseline_stable"]
                objects = report["target_link_inputs"]
                assert objects and all(Path(path).suffix == ".o" and
                    Path(path).parent == report_path.parent for path in objects)
                current["target_link_inputs"] = objects
                data = exe.read_bytes()
                pe = struct.unpack_from("<I", data, 60)[0]
                assert data[:2] == b"MZ" and data[pe:pe + 4] == b"PE\0\0"
                assert struct.unpack_from("<H", data, pe + 4)[0] == 0x8664
                native = subprocess.run([str(exe)], capture_output=True,
                                        timeout=15)
                expected = 0 if name == "implicit-main" else 42
                assert native.returncode == expected
                current["expected_native_exit_status"] = expected
                current["native_executed"] = True
                if name == "scalar":
                    before = digest(exe)
                    repeated = subprocess.run(arguments, cwd=directory,
                        capture_output=True, timeout=120)
                    rejected = json.loads(repeated.stdout)
                    assert repeated.returncode == 1
                    assert "Output already exists" in rejected["reason"]
                    assert digest(exe) == before
                    current["existing_output_preserved"] = True
                    current["preservation_evidence"] = rejected["evidence"]
            assert source_hashes == {path: digest(Path(path))
                                     for path in source_hashes}
            current["consumed_source_sha256"] = source_hashes
            current["status"] = "Pass"
        except subprocess.TimeoutExpired as error:
            current["reason"] = "Compiler or native execution timed out"
            current["timeout_stdout"] = (error.stdout or b"").decode(
                errors="replace")
            current["timeout_stderr"] = (error.stderr or b"").decode(
                errors="replace")
        except (OSError, ValueError, AssertionError, KeyError,
                struct.error) as error:
            current["reason"] = str(error)
        current["artifact_sha256"] = {
            path.name: digest(path) for path in directory.iterdir()
            if path.is_file()
        }
        results.append(current)
        print(f"{current['status']}: DMC/owned IR/TinyCC {name}", flush=True)
    stable = baseline == source_snapshot(root) and binaries == {
        str(path): digest(path) for path in tools
    }
    (output / "results.json").write_text(json.dumps({
        "kind": "DMC typed CFG to owned lowering to TinyCC native feasibility",
        "parent_requirements_verified": False,
        "requirement_ids": ["REQ-0010", "REQ-0013", "REQ-0015", "REQ-0016",
                            "REQ-0044"],
        "test_ids": ["TC-0010", "TC-0013", "TC-0015", "TC-0016", "TC-0044"],
        "target": "windows-x64", "results": results,
        "baseline_stable": stable, "input_sha256": baseline,
        "binary_input_sha256": binaries,
        "limits": ["Experimental scalar/object profile, not full C++98",
                   "No EH/RTTI, general class value ABI or external runtime",
                   "No production driver replacement or ARM64 qualification"],
    }, indent=2) + "\n", encoding="utf-8")
    print(f"Evidence: {output}")
    return not stable or any(row["status"] != "Pass" for row in results)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, required=True)
    parser.add_argument("--build-record", type=Path, required=True)
    parser.add_argument("--backend", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--case", action="append")
    raise SystemExit(bool(probe(parser.parse_args())))
