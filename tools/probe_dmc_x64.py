"""Exercise adapted DMC x64 COFF emission with an independent MSVC caller.

Default probes avoid CRT, EH and RTTI dependencies and do not enable strict
mode. Optional runtime probes retain failures until a real runtime is linked.
Results establish only the observed ABI and object-model partitions.
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
    """Emit target objects, link through MSVC and execute bounded probes."""
    root = Path(__file__).resolve().parents[1]
    baseline = source_snapshot(root)
    compiler = options.compiler.resolve()
    record = options.build_record.resolve()
    linker = options.linker.resolve()
    cc = linker.parent / "cl.exe"
    build = json.loads(record.read_text(encoding="utf-8"))
    if (build.get("status") != "Pass" or
            build.get("output_sha256") != digest(compiler)):
        raise ValueError("Compiler does not match successful build record")
    binaries = (compiler, record, linker, cc)
    binary_baseline = {str(path): digest(path) for path in binaries}
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-")
    output = root / "output/dmc-x64" / (stamp + uuid.uuid4().hex[:8])
    output.mkdir(parents=True)
    fixtures = {
        "pointer-width": (
            'extern "C" int answer(){return sizeof(void*)==8?42:1;}',
            "extern int answer(void);int entry(void){return answer();}"),
        "register-stack-arguments": (
            'extern "C" int answer(int a,int b,int c,int d,int e,int f,'
            "int g,int h){return a+b+c+d+e+f+g+h;}",
            "extern int answer(int,int,int,int,int,int,int,int);"
            "int entry(void){return answer(1,2,3,4,5,6,7,14);}"),
        "reference-mutation": (
            'extern "C" int answer(int& n){n=41;return 1;}',
            "extern int answer(int*);"
            "int entry(void){int n=0;int r=answer(&n);return r+n;}"),
        "pointer-return": (
            'extern "C" int* answer(int* p){return p;}',
            "extern int* answer(int*);"
            "int entry(void){int n=0;return answer(&n)==&n?42:1;}"),
        "reverse-callback": (
            'extern "C" int callback(int,int,int,int,int,int,int,int);'
            'extern "C" int answer(){return callback(1,2,3,4,5,6,7,14);}',
            "int callback(int a,int b,int c,int d,int e,int f,int g,int h)"
            "{return a+b+c+d+e+f+g+h;}extern int answer(void);"
            "int entry(void){return answer();}"),
        "virtual-dispatch": (
            "struct B{virtual int f(){return 3;}};"
            "struct D:B{int f(){return 42;}};"
            'extern "C" int answer(){D d;B* p=&d;return p->f();}',
            "extern int answer(void);int entry(void){return answer();}"),
        "normal-cleanup": (
            "struct G{int* p;G(int& n):p(&n){++*p;}~G(){++*p;}};"
            'extern "C" int answer(){int n=0;{G g(n);}return n==2?42:1;}',
            "extern int answer(void);int entry(void){return answer();}"),
        "mixed-floating-arguments": (
            'extern "C" double answer(int a,double b,int c,double d,'
            "int e,double f,int g,double h){return a+b+c+d+e+f+g+h;}",
            "int _fltused;extern double answer(int,double,int,double,"
            "int,double,int,double);"
            "int entry(void){return answer(1,2,3,4,5,6,7,14)==42?42:1;}"),
        "small-aggregate-argument": (
            'struct P{int a,b;};extern "C" int answer(P p)'
            "{return p.a+p.b;}",
            "struct P{int a,b;};extern int answer(struct P);"
            "int entry(void){struct P p={12,30};return answer(p);}"),
        "large-aggregate-argument": (
            'struct P{int a,b,c;};extern "C" int answer(P p)'
            "{return p.a+p.b+p.c;}",
            "struct P{int a,b,c;};extern int answer(struct P);"
            "int entry(void){struct P p={11,12,19};return answer(p);}"),
        "large-aggregate-copy-mutation": (
            'struct P{int a,b,c;};extern "C" int answer(P p)'
            "{p.a=20;return sizeof(p)==12?p.a+p.b+p.c:1;}",
            "struct P{int a,b,c;};extern int answer(struct P);"
            "int entry(void){struct P p={11,12,19};int r=answer(p);"
            "return r==51 && p.a==11?42:1;}"),
        "large-aggregate-stack-position": (
            'struct P{int a,b,c;};extern "C" int answer('
            "int a,int b,int c,int d,int e,P p)"
            "{return a+b+c+d+e+p.a+p.b+p.c;}",
            "struct P{int a,b,c;};"
            "extern int answer(int,int,int,int,int,struct P);"
            "int entry(void){struct P p={6,7,14};"
            "return answer(1,2,3,4,5,p);}"),
        "odd-aggregate-argument": (
            'struct P{char a,b,c;};extern "C" int answer(P p)'
            "{return p.a+p.b+p.c;}",
            "struct P{char a,b,c;};extern int answer(struct P);"
            "int entry(void){struct P p={12,13,17};return answer(p);}"),
        "large-aggregate-source-call": (
            "struct P{int a,b,c;};int f(P p)"
            "{p.a=20;return p.a+p.b+p.c;}"
            'extern "C" int answer(){P p={11,12,19};int r=f(p);'
            "return r==51 && p.a==11?42:1;}",
            "extern int answer(void);int entry(void){return answer();}"),
        "large-aggregate-inline-call": (
            "struct P{int a,b,c;};inline int f(P p)"
            "{p.a=20;return p.a+p.b+p.c;}"
            'extern "C" int answer(){P p={11,12,19};int r=f(p);'
            "return r==51 && p.a==11?42:1;}",
            "extern int answer(void);int entry(void){return answer();}"),
        "large-aggregate-reverse-callback": (
            'struct P{int a,b,c;};extern "C" int callback(P);'
            'extern "C" int answer(){P p={11,12,19};int r=callback(p);'
            "return r==51 && p.a==11?42:1;}",
            "struct P{int a,b,c;};int callback(struct P p){"
            "if((unsigned __int64)&p & 15)return 1;"
            "p.a=20;return p.a+p.b+p.c;}extern int answer(void);"
            "int entry(void){return answer();}"),
        "large-aggregate-distinct-copies": (
            'struct P{int a,b,c;};extern "C" int answer(P p,P q)'
            "{p.a=20;return &p!=&q && q.a==11?42:1;}",
            "struct P{int a,b,c;};extern int answer(struct P,struct P);"
            "int entry(void){struct P p={11,12,19};return answer(p,p);}"),
        "small-aggregate-return": (
            'struct P{int a,b;};extern "C" P answer(){P p={12,30};return p;}',
            "struct P{int a,b;};extern struct P answer(void);"
            "int entry(void){struct P p=answer();return p.a+p.b;}"),
        "large-aggregate-return": (
            'struct P{int a,b,c;};extern "C" P answer(int n)'
            "{P p={11,n,19};return p;}",
            "struct P{int a,b,c;};extern struct P answer(int);"
            "int entry(void){struct P p=answer(12);return p.a+p.b+p.c;}"),
        "large-aggregate-return-callback": (
            'struct P{int a,b,c;};extern "C" P callback(int);'
            'extern "C" int answer(){P p=callback(12);'
            "return p.a+p.b+p.c;}",
            "struct P{int a,b,c;};struct P callback(int n)"
            "{struct P p={11,n,19};return p;}extern int answer(void);"
            "int entry(void){return answer();}"),
    }
    support_sources = {
        "cross-unit-lifetime": {
            "model.h": "struct G{int* p;G(int&);~G();};",
            "worker.cpp": '#include "model.h"\n'
            "G::G(int& n):p(&n){*p=*p*10+1;}G::~G(){*p=*p*10+2;}",
        },
        "cross-unit-nontrivial-value": {
            "model.h": "extern int copies,dtors;"
            "struct P{int value;P(int);P(const P&);~P();};int consume(P);",
            "worker.cpp": '#include "model.h"\nint copies=0,dtors=0;'
            "P::P(int n):value(n){}P::P(const P& p):value(p.value){++copies;}"
            "P::~P(){++dtors;}int consume(P p){p.value+=2;return p.value;}",
        },
        "cross-unit-adjusted-virtual": {
            "model.h": "struct B{virtual int f();};"
            "struct C{virtual int f();};struct D:B,C{int f();};int invoke(C*);",
            "worker.cpp": '#include "model.h"\n'
            "int B::f(){return 1;}int C::f(){return 2;}"
            "int D::f(){return 42;}int invoke(C* p){return p->f();}",
        },
    }
    object_probes = {
        "cross-unit-lifetime": 'extern "C" int answer(){int n=0;'
        "{G g(n);if(n!=1)return 1;}return n==12?42:2;}",
        "cross-unit-nontrivial-value": 'extern "C" int answer(){'
        "copies=dtors=0;int r;{P p(40);r=consume(p);if(p.value!=40)return 1;}"
        "return r==42 && copies==1 && dtors==2?42:2;}",
        "cross-unit-adjusted-virtual": 'extern "C" int answer(){D d;C* p=&d;'
        "return invoke(p)==42 && (char*)p!=(char*)&d?42:1;}",
    }
    for name, text in object_probes.items():
        fixtures[name] = ('#include "model.h"\n' + text,
                          "extern int answer(void);"
                          "int entry(void){return answer();}")
    for size in (8, 12, 24):
        name = f"cross-unit-nontrivial-size-{size}"
        count = size - 4
        support_sources[name] = {
            "model.h": "extern int copies,dtors,badalign;"
            f"struct P{{int value;unsigned char bytes[{count}];"
            "P(int);P(const P&);~P();};int consume(P);",
            "worker.cpp": '#include "model.h"\n'
            "int copies=0,dtors=0,badalign=0;"
            "P::P(int n):value(n){"
            f"for(int i=0;i<{count};++i)bytes[i]=i+1;}}"
            "P::P(const P& p):value(p.value){++copies;"
            "if((unsigned long long)this & 15)++badalign;"
            f"for(int i=0;i<{count};++i)bytes[i]=p.bytes[i];}}"
            "P::~P(){++dtors;}int consume(P p){"
            f"for(int i=0;i<{count};++i)if(p.bytes[i]!=i+1)return 1;"
            "p.value+=2;p.bytes[0]=99;return p.value;}",
        }
        fixtures[name] = (
            '#include "model.h"\nextern "C" int answer(){'
            "copies=dtors=badalign=0;int r;{P p(40);r=consume(p);"
            "if(p.value!=40 || p.bytes[0]!=1)return 1;}"
            f"if(sizeof(P)!={size})return 3;if(r!=42)return 4;"
            "if(copies!=1)return 5;if(dtors!=2)return 6;"
            "return badalign?7:42;}",
            "extern int answer(void);int entry(void){return answer();}",
        )
    runtime_names = set()
    if options.runtime_probes:
        runtime = {
            "exception-handler": 'extern "C" int answer(){try{throw 42;}'
            'catch(int n){return n;}return 1;}',
            "exceptional-cleanup": "struct G{int* p;G(int& n):p(&n){++*p;}"
            "~G(){++*p;}};void f(int& n){G g(n);throw 7;}"
            'extern "C" int answer(){int n=0;try{f(n);}'
            "catch(int){return n==2?42:1;}return 2;}",
            "rtti-cast": "#include <typeinfo.h>\n"
            "struct B{virtual int f(){return 1;}};"
            "struct D:B{int f(){return 42;}};"
            'extern "C" int answer(){D d;B* p=&d;'
            "D* q=dynamic_cast<D*>(p);return q?q->f():1;}",
            "rtti-typeid": "#include <typeinfo.h>\n"
            "struct B{virtual int f(){return 1;}};struct D:B{};"
            'extern "C" int answer(){D d;B* p=&d;'
            "return typeid(*p)==typeid(D)?42:1;}",
        }
        runtime_names = set(runtime)
        for name, text in runtime.items():
            fixtures[name] = (text, "extern int answer(void);"
                              "int entry(void){return answer();}")
    for size in (1, 2, 3, 4, 5, 6, 7, 8, 9, 12, 16, 24):
        declaration = f"struct P{{unsigned char b[{size}];}};"
        total = size * (size + 1) // 2
        fixtures[f"pod-return-size-{size}"] = (
            declaration + 'extern "C" P answer(){P p={{0}};'
            f"for(int i=0;i<{size};++i)p.b[i]=i+1;return p;}}",
            declaration + "extern struct P answer(void);"
            "int entry(void){struct P p=answer();int i,s=0;"
            f"for(i=0;i<{size};++i)s+=p.b[i];return s=={total}?42:1;}}",
        )
        fixtures[f"pod-argument-size-{size}"] = (
            declaration + 'extern "C" int answer(P p){int s=0;'
            f"for(int i=0;i<{size};++i)s+=p.b[i];p.b[0]=99;"
            f"return sizeof(p)=={size} && s=={total}?42:1;}}",
            declaration + "extern int answer(struct P);"
            "int entry(void){struct P p={{0}};int i,r;"
            f"for(i=0;i<{size};++i)p.b[i]=i+1;r=answer(p);"
            "return r==42 && p.b[0]==1?42:1;}",
        )
    selected = set(options.case or fixtures)
    if selected - set(fixtures):
        raise ValueError("Unknown x64 probe case")
    fixtures = {name: value for name, value in fixtures.items()
                if name in selected}
    results = []
    for name, (text, harness) in fixtures.items():
        directory = output / name
        directory.mkdir()
        (directory / "probe.cpp").write_text(text + "\n", encoding="ascii")
        (directory / "caller.c").write_text(harness + "\n", encoding="ascii")
        extra = support_sources.get(name, {})
        for filename, contents in extra.items():
            (directory / filename).write_text(contents + "\n", encoding="ascii")
        units = ["probe.cpp"] + sorted(filename for filename in extra
                                       if filename.endswith(".cpp"))
        objects = [str(Path(unit).with_suffix(".obj")) for unit in units]
        current = {"name": name, "status": "Not run", "commands": []}
        compile_arguments = [str(compiler), "-m64", "-c"]
        if not options.no_nc:
            compile_arguments.append("-Nc")
        if options.optimize:
            compile_arguments.append("-o")
        if options.debug_info:
            compile_arguments.append("-g")
        if name in runtime_names:
            compile_arguments += ["-Ae", "-Ar", f"-I{root / 'dmc/include'}"]
        link_arguments = [str(linker), "/nologo", "/entry:entry",
                          "/subsystem:console", "/nodefaultlib",
                          "/out:probe.exe"] + objects + ["caller.obj"]
        if options.debug_info:
            link_arguments += ["/debug", "/pdb:probe.pdb"]
        commands = [(compile_arguments + [unit], 0) for unit in units] + [
            ([str(cc), "/nologo", "/GS-", "/Zl", "/TC", "/c",
              "/Focaller.obj", "caller.c"], 0),
            (link_arguments, 0),
            ([str(directory / "probe.exe")], 42),
        ]
        try:
            for arguments, expected in commands:
                began = datetime.datetime.now(datetime.timezone.utc)
                child = subprocess.run(
                    arguments, cwd=directory, capture_output=True, timeout=15,
                )
                current["commands"].append({
                    "argv": arguments, "exit_status": child.returncode,
                    "started": began.isoformat(),
                    "finished": datetime.datetime.now(
                        datetime.timezone.utc
                    ).isoformat(),
                    "expected_exit_status": expected,
                    "stdout": child.stdout.decode(errors="replace"),
                    "stderr": child.stderr.decode(errors="replace"),
                })
                if child.returncode != expected:
                    raise AssertionError("Unexpected process exit status")
            for filename in objects + ["caller.obj"]:
                data = (directory / filename).read_bytes()
                if struct.unpack_from("<H", data)[0] != 0x8664:
                    raise AssertionError("Expected x64 COFF object")
            if options.debug_info:
                data = (directory / "probe.obj").read_bytes()
                count = struct.unpack_from("<H", data, 2)[0]
                sections = {
                    data[20 + i * 40:28 + i * 40].rstrip(b"\0")
                    for i in range(count)
                }
                if not {b".debug$S", b".debug$T"}.issubset(sections):
                    raise AssertionError("Expected CodeView symbol/type data")
                data = (directory / "probe.pdb").read_bytes()
                if not data.startswith(b"Microsoft C/C++ MSF 7.00"):
                    raise AssertionError("Expected MSF program database")
            data = (directory / "probe.exe").read_bytes()
            pe = struct.unpack_from("<I", data, 60)[0]
            if (data[:2] != b"MZ" or data[pe:pe + 4] != b"PE\0\0" or
                    struct.unpack_from("<H", data, pe + 4)[0] != 0x8664):
                raise AssertionError("Expected native PE x64 executable")
            current["status"] = "Pass"
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
        current["artifact_sha256"] = {
            path.name: digest(path) for path in directory.iterdir()
            if path.is_file()
        }
        results.append(current)
        print(f"{current['status']}: adapted DMC x64 {name}", flush=True)
    stable = baseline == source_snapshot(root) and binary_baseline == {
        str(path): digest(path) for path in binaries
    }
    requirements = {"REQ-0026", "REQ-0027", "REQ-0044"}
    if selected & set(support_sources):
        requirements.update(("REQ-0015", "REQ-0016", "REQ-0017"))
    if selected & {"exception-handler", "exceptional-cleanup"}:
        requirements.update(("REQ-0015", "REQ-0022"))
    if selected & {"rtti-cast", "rtti-typeid"}:
        requirements.add("REQ-0024")
    (output / "results.json").write_text(json.dumps({
        "kind": "Adapted DMC x64 ABI and object/runtime feasibility",
        "requirement_ids": sorted(requirements),
        "test_ids": ["TC" + item[3:] for item in sorted(requirements)],
        "parent_requirements_verified": False,
        "target_optimization": options.optimize,
        "target_debug_info": options.debug_info,
        "allcomdat_workaround": not options.no_nc,
        "runtime_probes_requested": options.runtime_probes,
        "selected_cases": sorted(selected),
        "compiler_d_assertions_enabled": build.get("d_assertions_enabled"),
        "results": results, "baseline_stable": stable,
        "input_sha256": baseline, "binary_input_sha256": binary_baseline,
        "source_copy_adaptations": build["source_copy_adaptations"],
        "limits": ["No strict mode or C++ binary compatibility",
                   "Optional EH/RTTI probes require a separate runtime",
                   "No Tiny++ integration or full parent TC closure"],
    }, indent=2) + "\n", encoding="utf-8")
    print(f"Evidence: {output}")
    return not stable or any(row["status"] != "Pass" for row in results)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, required=True)
    parser.add_argument("--build-record", type=Path, required=True)
    parser.add_argument("--linker", type=Path, required=True)
    parser.add_argument("--optimize", action="store_true")
    parser.add_argument("--debug-info", action="store_true")
    parser.add_argument("--no-nc", action="store_true")
    parser.add_argument("--runtime-probes", action="store_true")
    parser.add_argument("--case", action="append")
    raise SystemExit(bool(probe(parser.parse_args())))
