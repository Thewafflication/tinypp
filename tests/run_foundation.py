"""Exercise the scalar compiler, native linker and rejection boundaries.

Each invocation uses a new evidence directory. Expected child return values
are checked explicitly; a compiler crash is never accepted as a diagnostic.
The run documents partial coverage of parent TCs, not their full completion.
"""

import argparse
import datetime
import hashlib
import json
import platform
import random
import struct
import subprocess
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from evidence import dependency_paths, digest, source_snapshot


def run_suite(options):
    """Execute controlled variants; retain results and return failed count."""
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    baseline = source_snapshot(options.root)
    binaries = [options.compiler, options.backend,
                options.compiler.parent / "tinypp_tcc.dll",
                options.runtime / "lib/libtcc1.a"]
    binary_baseline = {str(path): digest(path) for path in binaries}
    run_id = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-")
    output = options.output / (run_id + uuid.uuid4().hex[:8] + " with spaces")
    output.mkdir(parents=True)
    if platform.system() != "Windows" or platform.machine().upper() not in {
        "AMD64", "X86_64",
    }:
        (output / "results.json").write_text(json.dumps({
            "status": "Blocked", "reason": "Native Windows x64 is required",
            "host": platform.platform(), "architecture": platform.machine(),
        }, indent=2) + "\n", encoding="utf-8")
        return 1
    results = []

    def command(arguments, expected=0):
        """Capture a subprocess; mismatches and timeouts fail the variant."""
        began = datetime.datetime.now(datetime.timezone.utc).isoformat()
        try:
            child = subprocess.run(
                [str(arg) for arg in arguments], capture_output=True,
                timeout=15, cwd=output,
            )
        except subprocess.TimeoutExpired as error:
            current["commands"].append({
                "argv": [str(arg) for arg in arguments],
                "started": began, "timeout_seconds": 15,
                "stdout": (error.stdout or b"").decode(errors="replace"),
                "stderr": (error.stderr or b"").decode(errors="replace"),
                "status": "Timed out; variant fails",
            })
            raise
        record = {
            "argv": [str(arg) for arg in arguments],
            "exit_status": child.returncode,
            "started": began,
            "finished": datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat(),
            "stdout": child.stdout.decode("utf-8", errors="replace"),
            "stderr": child.stderr.decode("utf-8", errors="replace"),
        }
        current["commands"].append(record)
        if expected is not None and child.returncode != expected:
            raise AssertionError(f"Expected {expected}, observed {record}")
        return child

    def variant(name, requirement, test, procedure):
        """Preserve an independent verdict for one fixture partition."""
        nonlocal current
        current = {
            "variant_id": name, "requirement_ids": [requirement],
            "test_id": test, "status": "Not run", "commands": [],
            "parent_requirement_verified": False,
        }
        try:
            procedure()
            current["status"] = "Pass"
        except Exception as error:
            current["status"] = "Fail"
            current["reason"] = str(error)
        results.append(current)
        (output / "variants.json").write_text(
            json.dumps(results, indent=2) + "\n", encoding="utf-8",
        )
        print(f"{current['status']}: {name}")

    def translate(name, source, terminated=True):
        """Write exact ASCII fixture bytes and compile to a fresh object."""
        src, obj = output / (name + ".cpp"), output / (name + ".o")
        data = source.encode("ascii")
        src.write_bytes(data if not terminated or data.endswith(b"\n")
                        else data + b"\n")
        command([options.compiler, "-std=c++98", "-c", src, "-o", obj])
        data = obj.read_bytes()
        assert data[:4] == b"\x7fELF", "Expected TinyCC ELF intermediate"
        assert data[4] == 2 and struct.unpack_from("<H", data, 18)[0] == 62
        return obj

    def execute(name, source, expected, terminated=True):
        """Compile owned input, link a PE x64 executable and run it natively."""
        obj = translate(name, source, terminated)
        exe = output / (name + ".exe")
        command([
            options.backend, f"-B{options.runtime}", obj, "-o", exe,
        ])
        data = exe.read_bytes()
        assert data[:2] == b"MZ", "Missing PE DOS signature"
        pe = struct.unpack_from("<I", data, 60)[0]
        assert data[pe:pe + 4] == b"PE\0\0", "Missing PE signature"
        assert struct.unpack_from("<H", data, pe + 4)[0] == 0x8664
        command([exe], expected)

    def rejection(name, source):
        """Require a source diagnostic and no object; preserve old artifacts."""
        src, obj = output / (name + ".cpp"), output / (name + ".o")
        src.write_bytes(source if source.endswith(b"\n") else source + b"\n")
        child = command([
            options.compiler, "-std=c++98", "-c", src, "-o", obj,
        ], expected=None)
        assert child.returncode == 1, "Expected diagnosed source failure"
        assert b": error:" in child.stderr, "Missing source diagnostic"
        assert not obj.exists(), "Rejected source published an object"

    current = {}
    expressions = [
        ("precedence", "2 + 3 * 4", 14),
        ("parentheses", "(2 + 3) * 4", 20),
        ("left-subtract", "20 - 7 - 3", 10),
        ("left-divide", "80 / 4 / 2", 10),
        ("unary", "-(-12) + +3", 15),
        ("not", "!0 + !5", 1),
        ("complement", "~0 + 2", 1),
        ("remainder", "19 % 6", 1),
    ]
    generator = random.Random(98)
    for i in range(12):
        a, b, c = (generator.randrange(1, 25) for _ in range(3))
        expressions.append((f"arithmetic-{i}", f"{a} + {b} * {c}", a + b*c))
    for name, expression, value in expressions:
        # Windows process exit codes retain these small positive int values.
        variant(name, "REQ-0012", "TC-0012", lambda n=name, e=expression,
                v=value: execute(n, f"int main() {{ return {e}; }}", v))

    malformed = {
        "missing-semicolon": b"int main() { return 1 }",
        "trailing-input": b"int main() { return 0; } class X {};",
        "duplicate": b"int f(){return 0;} int f(){return 1;}",
        "keyword-name": b"int class(){return 1;}",
        "overflow": b"int main(){return 4294967296;}",
        "invalid-octal": b"int main(){return 08;}",
        "increment-not-two-unary-plus": b"int main(){return ++1;}",
        "decrement-not-two-unary-minus": b"int main(){return --1;}",
        "comment-eof": b"int main(){return 0;} /* open",
        "nul-in-comment": b"//\0\nint main(){return 0;}",
        "unknown-name": b"int main(){return missing;}",
        "later-lambda": b"int main(){return [](){return 0;}();}",
        "template-external": b"template<class T> int f(){return 0;}",
        "standalone-CR-boundary": b"//hidden\rint main(){return 0;}",
    }
    for name, source in malformed.items():
        variant(name, "REQ-0007", "TC-0007",
                lambda n=name, s=source: rejection(n, s))
    scalar_programs = {
        "parameter-call": (
            "int add(int a,int b){return a+b;}"
            "int main(){return add(12,30);}", 42),
        "overload-exact-int": (
            "int f(int x){return 11;} int f(bool x){return 22;}"
            "int main(){return f(3);}", 11),
        "overload-exact-bool": (
            "int f(int x){return 11;} int f(bool x){return 22;}"
            "int main(){return f(true);}", 22),
        "overload-promotion": (
            "int f(int x){return x+9;} int main(){return f(true);}", 10),
        "bool-normalize-argument": (
            "int f(bool x){return x;} int main(){return f(42);}", 1),
        "bool-normalize-return": (
            "bool f(){return 42;} int main(){return f();}", 1),
        "arithmetic-bool-promotion": (
            "int f(int x){return 11;} int f(bool x){return 22;}"
            "int main(){return f(true+false);}", 11),
        "comparison-type-bool": (
            "int f(int x){return 11;} int f(bool x){return 22;}"
            "int main(){return f(2<3);}", 22),
        "short-circuit": (
            "int div(int x){return 1/x;}"
            "int main(){return (false && div(0)) || (true || div(0));}", 1),
        "alternative-tokens": (
            "int main(){return (not false and true) or false;}", 1),
        "conditional": (
            "int main(){return false ? 99 : true ? 42 : 66;}", 42),
        "recursive-factorial": (
            "int fact(int n){return n < 2 ? 1 : n*fact(n-1);}"
            "int main(){return fact(5);}", 120),
        "conditional-bool-type": (
            "int f(int x){return 11;} int f(bool x){return 22;}"
            "int main(){return f(true ? true : false);}", 22),
        "conditional-arithmetic-type": (
            "int f(int x){return 11;} int f(bool x){return 22;}"
            "int main(){return f(true ? true : 4);}", 11),
        "C-keyword-identifier": (
            "int restrict(int restrict){return restrict;}"
            "int main(){return restrict(5);}", 5),
        "forward-declaration": (
            "int f(int); int main(){return f(41);}"
            "int f(int x){return x+1;}", 42),
        "redeclaration": (
            "int f(int); int f(int x); int f(int y){return y;}"
            "int f(int z); int main(){return f(42);}", 42),
        "mutual-recursion": (
            "bool odd(int); bool even(int n){return n==0 ? true : odd(n-1);}"
            "bool odd(int n){return n==0 ? false : even(n-1);}"
            "int main(){return even(12) && odd(13);}", 1),
        "local-assignment": (
            "int main(){int a=3; int b; b=a*4; a=b+2; return a;}", 14),
        "bool-local-normalize": (
            "int main(){bool b=7; b=42; return b+1;}", 2),
        "if-else": (
            "int f(int x){if(x<3) return 11; else return 22;}"
            "int main(){return f(1)+f(9);}", 33),
        "while-accumulate": (
            "int main(){int n=1; int sum=0; while(n<=9){sum=sum+n; n=n+1;}"
            "return sum;}", 45),
        "while-break-continue": (
            "int main(){int n=0;int sum=0;while(true){n=n+1;"
            "if(n==6) break;if(n==3) continue;sum=sum+n;}return sum;}", 12),
        "lexical-shadow": (
            "int f(int x){{int x=12; x=x+1;} return x;}"
            "int main(){int x=3;{int x=4;}return f(x);}", 3),
        "assignment-value-and-conversion": (
            "int f(bool x){return x;}"
            "int main(){bool b=false;int a=0;return f(b=(a=42));}", 1),
        "dangling-else": (
            "int main(){if(true) if(false) return 1; else return 2;"
            "return 3;}", 2),
        "implicit-main-return": ("int main(){}", 0),
        "namespace-qualified": (
            "namespace N{int f(int x){return x+1;}}"
            "int main(){return N::f(41);}", 42),
        "namespace-reopened": (
            "namespace N{int f(int);}"
            "namespace N{int f(int x){return x+1;}}"
            "int main(){return N::f(41);}", 42),
        "namespace-enclosing-lookup": (
            "namespace A{int f(int x){return x+1;} namespace B{"
            "int g(){return f(41);}}} int main(){return A::B::g();}", 42),
        "namespace-rooted-lookup": (
            "int f(){return 7;} namespace A{int f(){return 3;}"
            "int g(){return ::f();}} int main(){return A::g();}", 7),
        "namespace-overloads": (
            "namespace A{int f(int x){return 11;}"
            "int f(bool x){return 22;}} int main(){return A::f(true);}", 22),
        "namespace-ordinary-main": (
            "namespace A{bool main(){return true;}}"
            "int main(){return A::main();}", 1),
        "namespace-symbol-uniqueness": (
            "namespace A_B{int f(){return 1;}}"
            "namespace A{namespace B{int f(){return 2;}}}"
            "int main(){return A_B::f()+A::B::f();}", 3),
        "namespace-alias-canonical": (
            "namespace Original{int f(){return 42;}}"
            "namespace A=Original;namespace B=A;"
            "int main(){return B::f();}", 42),
        "namespace-alias-redeclaration": (
            "namespace N{int f(){return 42;}}"
            "namespace A=N;namespace A=N;namespace A=A;"
            "int main(){return A::f();}", 42),
        "namespace-alias-reopened-target": (
            "namespace N{}namespace A=N;"
            "namespace N{int f(){return 42;}}"
            "int main(){return A::f();}", 42),
        "namespace-alias-nested-path": (
            "namespace N{namespace M{int f(){return 42;}}}"
            "namespace A=N;namespace B=A::M;"
            "int main(){return A::M::f()+B::f()-42;}", 42),
        "namespace-alias-component": (
            "namespace N{int f(){return 42;}}"
            "namespace M{namespace A=::N;}"
            "int main(){return ::M::A::f();}", 42),
        "namespace-alias-enclosing": (
            "namespace N{int f(){return 42;}}namespace A=N;"
            "namespace M{namespace P{int g(){return A::f();}}}"
            "int main(){return M::P::g();}", 42),
        "namespace-alias-nearest": (
            "namespace N{int f(){return 3;}}namespace A=N;"
            "namespace M{namespace P{int f(){return 42;}}"
            "namespace A=P;int g(){return A::f();}}"
            "int main(){return M::g();}", 42),
        "namespace-alias-rooted-target": (
            "namespace N{int f(){return 42;}}"
            "namespace M{namespace N{int f(){return 3;}}"
            "namespace A=::N;int g(){return A::f();}}"
            "int main(){return M::g();}", 42),
        "namespace-alias-overload-identity": (
            "namespace N{int f(int n){return 11;}"
            "int f(bool b){return 42;}}namespace A=N;"
            "int main(){return A::f(true);}", 42),
        "for-accumulate": (
            "int main(){int s=0;for(int i=0;i<10;i=i+1){s=s+i;}return s;}",
            45),
        "for-continue-step": (
            "int main(){int s=0;for(int i=0;i<5;i=i+1){"
            "if(i==2)continue;s=s+i;}return s;}", 8),
        "for-empty-clauses": (
            "int main(){int n=0;for(;;){n=n+1;if(n==4)break;}return n;}", 4),
        "for-shadow": (
            "int main(){int i=7;for(int i=0;i<3;i=i+1){}return i;}", 7),
        "for-inner-shadow": (
            "int main(){int n=0;for(int i=0;i<3;i=i+1){"
            "{int i=8;n=n+i;}}return n;}", 24),
        "void-parameter-list": (
            "int f(void){return 42;} int main(void){return f();}", 42),
        "unnamed-definition-parameter": (
            "int f(int, bool){return 42;} int main(){return f(1,true);}", 42),
        "C-linkage-inherited-definition": (
            'extern "C" int f(int); int f(int x){return x+1;}'
            'int main(){return f(41);}', 42),
        "C-linkage-block": (
            'extern "C"{int f(int x){return x+1;}}'
            'int main(){return f(41);}', 42),
        "C-linkage-namespace-alias": (
            'namespace A{extern "C" int f(int);}'
            'namespace B{extern "C" int f(int x){return x+1;}}'
            'int main(){return A::f(41)+B::f(0);}', 43),
        "reference-parameter-mutation": (
            "int set(int& x){x=42;return 0;}"
            "int main(){int n=1;set(n);return n;}", 42),
        "reference-local-alias": (
            "int main(){int n=3;int& a=n;int& b=a;b=42;return n;}", 42),
        "reference-bool-normalize": (
            "int set(bool& b){b=42;return 0;}"
            "int main(){bool n=false;set(n);return n;}", 1),
        "reference-assignment-identity": (
            "int set(int& x){x=x+1;return 0;}"
            "int main(){int n=0;set(n=41);return n;}", 42),
        "reference-conditional-identity": (
            "int set(int& x){x=42;return 0;}"
            "int main(){int a=3;int b=4;set(true?a:b);return a+b;}", 46),
        "reference-overload-rvalue": (
            "int f(int x){return 11;}int f(int& x){return 22;}"
            "int main(){return f(3);}", 11),
        "reference-exact-before-conversion": (
            "int f(bool x){return 11;}int f(int& x){return 22;}"
            "int main(){int n=3;return f(n);}", 22),
        "assignment-lvalue-chaining": (
            "int main(){int a=1;int b=2;(a=b)=42;return a;}", 42),
        "assignment-reference-no-duplicate-effect": (
            "int add(int& x){x=x+1;return 0;}"
            "int main(){int a=1;int b=2;add((a=b)=42);return a;}", 43),
        "conditional-assignment-lvalue": (
            "int main(){int a=1;int b=2;(true?a:b)=42;return a+b;}", 44),
        "reference-conditional-no-duplicate-effect": (
            "int set(int& x){x=42;return 0;}"
            "int main(){int i=0;int a=3;int b=4;"
            "set((i=i+1)?a:b);return a+b+i;}", 47),
        "long-overload-exact": (
            "int f(int x){return 11;}int f(long x){return 22;}"
            "int main(){return f(1L);}", 22),
        "unsigned-decimal-98-type": (
            "int f(unsigned int x){return 11;}"
            "int f(unsigned long x){return 22;}"
            "int main(){return f(2147483648);}", 22),
        "unsigned-hex-type": (
            "int f(unsigned int x){return 11;}"
            "int f(unsigned long x){return 22;}"
            "int main(){return f(0xFFFFFFFF);}", 11),
        "unsigned-octal-type": (
            "int f(unsigned int x){return 11;}"
            "int f(unsigned long x){return 22;}"
            "int main(){return f(037777777777);}", 11),
        "unsigned-wrap": (
            "int main(){unsigned n=4294967295U;return n+1U==0U;}", 1),
        "unsigned-comparison": (
            "int main(){return (-1<1U)==false;}", 1),
        "unsigned-division": (
            "int main(){return 4294967295U/2U==2147483647U;}", 1),
        "long-unsigned-usual-conversion": (
            "int f(unsigned int x){return 11;}"
            "int f(unsigned long x){return 22;}"
            "int main(){return f(1L+2U);}", 22),
        "unsigned-reference-mutation": (
            "int add(unsigned& x){x=x+1U;return 0;}"
            "int main(){unsigned x=4294967295U;add(x);return x==0U;}", 1),
        "integer-type-specifier-order": (
            "long unsigned int f(unsigned long int x){return x;}"
            "int main(){return f(42UL);}", 42),
        "prefix-reference-identity": (
            "int main(){int n=1;int& r=++n;r=42;return n;}", 42),
        "postfix-old-value": (
            "int main(){int n=1;int old=n++;return old*10+n;}", 12),
        "nested-prefix-postfix": (
            "int main(){int n=1;int old=(++n)++;return old*10+n;}", 23),
        "unsigned-update-wrap": (
            "int main(){unsigned n=4294967295U;++n;return n==0U;}", 1),
        "bool-update-98": (
            "int main(){bool b=false;bool old=b++;++b;return !old && b;}", 1),
        "compound-bool-normalize": (
            "int main(){bool b=true;b-=2;return b;}", 1),
        "compound-lvalue-identity": (
            "int main(){int n=1;int& r=(n+=2);r=42;return n;}", 42),
        "compound-integer-operators": (
            "int main(){unsigned n=3U;n*=4U;n/=2U;n%=5U;n|=8U;"
            "n^=2U;n&=15U;n<<=1;n>>=1;return n;}", 11),
        "compound-address-once": (
            "int main(){int n=1;int a=3;int b=4;"
            "(n++?a:b)+=2;return n*10+a;}", 25),
        "shift-precedence": ("int main(){return 1+2<<2;}", 12),
        "unsigned-right-shift": (
            "int main(){return (0x80000000U>>31)==1U;}", 1),
        "shift-result-type": (
            "int f(int x){return 11;}int f(unsigned x){return 22;}"
            "int main(){return f(1<<1U);}", 11),
        "for-postfix-step": (
            "int main(){int s=0;for(int i=0;i<5;i++){s+=i;}return s;}", 10),
        "alternative-compound-tokens": (
            "int main(){int n=3;n and_eq 1;n or_eq 8;n xor_eq 2;return n;}",
            11),
        "comma-statement-sequencing": (
            "int main(){int n=0;n=3,n+=4;return n;}", 7),
        "comma-return": ("int main(){int n=0;return n=3,n+4;}", 7),
        "comma-reference-identity": (
            "int set(int& x){x=42;return 0;}"
            "int main(){int n=0;int a=3;set((n++,a));return n+a;}", 43),
        "comma-call-argument-boundary": (
            "int f(int a,int b){return a*10+b;}"
            "int main(){return f((1,2),3);}", 23),
        "conditional-middle-comma": (
            "int main(){int n=0;return true?n=3,n+4:9;}", 7),
        "for-comma-step": (
            "int main(){int n=0;for(int i=0;i<3;i++,n+=2){}return n;}", 6),
        "comma-result-type": (
            "int f(int x){return 11;}int f(bool x){return 22;}"
            "int main(){return f((1,true));}", 22),
        "signed-division-policy": (
            "int main(){return -23/4==-5 && -23%4==-3;}", 1),
        "signed-right-shift-policy": (
            "int main(){return (-8>>2)==-2;}", 1),
        "out-of-range-signed-conversion-policy": (
            "int main(){int n=4294967295U;long m=4294967295UL;"
            "return n==-1 && m==-1L;}", 1),
        "functional-cast-type": (
            "int f(int x){return 11;}int f(long x){return 22;}"
            "int main(){return f(long(3));}", 22),
        "functional-zero-initialization": (
            "int main(){return int()==0 && bool()==false && long()==0L;}", 1),
        "C-style-cast": (
            "int main(){return (unsigned long)(-1)==4294967295UL;}", 1),
        "static-cast-type": (
            "int f(unsigned x){return 11;}int f(unsigned long x){return 22;}"
            "int main(){return f(static_cast<unsigned long>(3));}", 22),
        "bool-cast-normalization": (
            "int main(){return bool(42)==true && static_cast<bool>(-3);}", 1),
        "reference-cast-identity": (
            "int main(){int n=3;int& r=static_cast<int&>(n);"
            "r=42;return n;}", 42),
        "C-style-reference-identity": (
            "int main(){int n=3;((int&)n)=42;return n;}", 42),
        "cast-comma-effect-once": (
            "int main(){int n=0;int x=static_cast<int>((n++,42));"
            "return n+x;}", 43),
        "parenthesized-functional-cast": (
            "int main(){return (int(42));}", 42),
        "parenthesized-cast-overload-type": (
            "int f(int x){return 11;}int f(long x){return 22;}"
            "int main(){return f((long(3)));}", 22),
        "multiple-local-declarators": (
            "int main(){int a=3,b=a+4,c; c=b+2;return a+b+c;}", 19),
        "mixed-reference-declarators": (
            "int main(){int a=3,&r=a,b=4;r=42;return a+b;}", 46),
        "direct-initialization": (
            "int main(){int a(3),b(a+4);bool yes(42);return a+b+yes;}", 11),
        "direct-reference-initialization": (
            "int main(){int a(3);int& r(a);r=42;return a;}", 42),
        "for-multiple-declarators": (
            "int main(){int s=0;for(int i=0,j=4;i<j;++i){s+=i;}return s;}",
            6),
        "for-reference-declarator": (
            "int main(){int n=0;for(int& r=n;r<4;++r){}return n;}", 4),
        "const-local-values": (
            "int main(){const int a=3,b=4;return a+b;}", 7),
        "const-trailing-qualifier": (
            "int main(){unsigned long const n=42UL;return n;}", 42),
        "const-parameter-redeclaration": (
            "int f(int);int f(const int x){return x+1;}"
            "int main(){return f(41);}", 42),
        "const-parameter-ignored-in-signature": (
            "int f(const int);int f(int x){++x;return x;}"
            "int main(){return f(41);}", 42),
        "const-value-overload": (
            "int f(int x){return 11;}int f(long x){return 22;}"
            "int main(){const int n=3;return f(n);}", 11),
        "const-nonconst-reference-viability": (
            "int f(bool x){return 11;}int f(int& x){return 22;}"
            "int main(){const int n=3;return f(n);}", 11),
        "const-shadow-scope": (
            "int main(){const int n=42;{int n=1;++n;}return n;}", 42),
        "const-conditional-read": (
            "int main(){const int a=42,b=3;return true?a:b;}", 42),
        "const-value-cast": (
            "int main(){const int n=42;return static_cast<const int>(n);}", 42),
        "discarded-uninitialized-lvalue": (
            "int main(){int n;n;(n,42);return 7;}", 7),
        "discarded-prefix-retains-effects": (
            "int main(){int n=0;++n;(++n,42);return n;}", 2),
        "prefix-bool-does-not-need-old-value": (
            "int main(){bool b;++b;return b;}", 1),
        "phase-spliced-identifier": ("int ma\\\nin(){return 42;}", 42),
        "phase-spliced-number": ("int main(){return 4\\\n2;}", 42),
        "phase-spliced-comment": (
            "//hidden\\\nint broken( {;\nint main(){return 42;}", 42),
        "phase-trigraph-braces": ("int main()??<return 42;??>", 42),
        "phase-trigraph-xor": ("int main(){return 2??'3;}", 1),
        "phase-trigraph-spliced-comment": (
            "//hidden??/\nint broken( {;\nint main(){return 42;}", 42),
        "phase-trigraph-CRLF-splicing": (
            "//hidden??/\r\nint broken( {;\r\nint main(){return 42;}", 42),
        "phase-no-trigraph-reprocessing": (
            "//?\\\n?/\nint main(){return 42;}", 42),
        "void-function-return": (
            "void f(){return;}int main(){f();return 42;}", 42),
        "void-function-fallthrough": (
            "void set(int& n){n=42;}int main(){int n=0;set(n);return n;}", 42),
        "void-expression-return": (
            "void g(){return;}void f(){return g();}"
            "int main(){f();return 42;}", 42),
        "void-value-initialization": (
            "void f(){return void();}int main(){f();return 42;}", 42),
        "void-casts-discard-effects": (
            "int main(){int n=0;(void)++n;static_cast<void>(++n);"
            "void();return n;}", 2),
        "void-functional-cast-literal": (
            "int main(){void(42);return 7;}", 7),
        "void-conditional-branches": (
            "void add(int& n){++n;}int main(){int n=0;"
            "true?add(n):add(n);return n;}", 1),
        "void-comma-left": (
            "void f(){return;}int main(){return f(),42;}", 42),
        "parenthesized-declarator": (
            "int main(){int(n)=42;return n;}", 42),
        "parenthesized-reference-declarator": (
            "int main(){int a=3;int(&r)=a;r=42;return a;}", 42),
        "functional-cast-expression-statement": (
            "int main(){int n=3;int(n+1);return n;}", 3),
        "do-executes-once": (
            "int main(){int n=0;do{n=n+1;}while(false);return n;}", 1),
        "do-continue-condition": (
            "int main(){int n=0;int s=0;do{n=n+1;"
            "if(n==3)continue;s=s+n;}while(n<5);return s;}", 12),
    }
    for name, (source, value) in scalar_programs.items():
        parent = "0014"
        if name in {
            "local-assignment", "if-else", "while-accumulate",
            "while-break-continue", "dangling-else", "implicit-main-return",
            "recursive-factorial", "mutual-recursion",
        }:
            parent = "0013"
        if name.startswith("for-") or name.startswith("do-"):
            parent = "0013"
        if name.startswith("phase-"):
            parent = "0008"
        if name.startswith("void-"):
            parent = "0013"
        if name == "lexical-shadow" or name.startswith("namespace-"):
            parent = "0011"
        variant(name, f"REQ-{parent}", f"TC-{parent}", lambda n=name, s=source,
                v=value: execute(n, s, v))
    invalid_calls = {
        "ambiguous-ranking": (
            "int f(int x,bool y){return 0;}"
            "int f(bool x,int y){return 1;}"
            "int main(){return f(true,true);}"),
        "ambiguous-not-rank-sum": (
            "int f(int x,int y){return 0;}"
            "int f(bool x,bool y){return 1;}"
            "int main(){return f(true,1);}"),
        "return-only-overload": (
            "int f(int x){return 0;} bool f(int x){return true;}"),
        "duplicate-parameter": "int f(int x,int x){return x;}",
        "forward-unavailable": (
            "int main(){return later();} int later(){return 0;}"),
        "wrong-arity": "int f(int x){return x;} int main(){return f();}",
        "parameter-hides-function": (
            "int f(){return 0;} int g(int f){return f();}"),
        "main-call-prohibited": "int main(){return main();}",
        "bool-main-prohibited": "bool main(){return false;}",
        "local-redeclaration": "int main(){int x=1;int x=2;return x;}",
        "parameter-redeclaration": "int f(int x){int x=2;return x;}",
        "block-binding-expired": "int main(){{int x=1;}return x;}",
        "if-binding-expired": "int main(){if(true) int x=1;return x;}",
        "break-outside-loop": "int main(){break;return 0;}",
        "continue-outside-loop": "int main(){continue;return 0;}",
        "nonassignable": "int main(){(1+2)=3;return 0;}",
        "namespace-function-conflict": "namespace N{} int N(){return 0;}",
        "function-namespace-conflict": "int N(); namespace N{}",
        "namespace-hidden-overload": (
            "int f(int,int); namespace N{int f(bool);"
            "int g(){return f(1,2);}}"),
        "namespace-qualifier-hidden": (
            "namespace N{int f();} namespace A{namespace N{}"
            "int g(){return N::f();}}"),
        "namespace-unclosed": "namespace N{int f(){return 0;}",
        "namespace-alias-unknown": "namespace A=Missing;",
        "namespace-alias-function-target": "int f();namespace A=f;",
        "namespace-alias-retarget": (
            "namespace N{}namespace M{}namespace A=N;namespace A=M;"),
        "namespace-alias-real-conflict": "namespace N{}namespace N=N;",
        "namespace-alias-function-conflict": (
            "namespace N{}int f();namespace f=N;"),
        "namespace-alias-function-after": (
            "namespace N{}namespace A=N;int A();"),
        "namespace-alias-reopen-prohibited": (
            "namespace N{}namespace A=N;namespace A{}"),
        "namespace-alias-qualified-hidden": (
            "namespace N{namespace P{int f(){return 42;}}}"
            "namespace M{namespace Q{}namespace N=Q;"
            "int g(){return N::P::f();}}"),
        "namespace-alias-hidden-target": (
            "namespace N{namespace P{}}"
            "namespace M{namespace N{}namespace A=N::P;}"),
        "namespace-alias-before-target": "namespace A=N;namespace N{}",
        "for-binding-expired": (
            "int main(){for(int i=0;i<1;i=i+1){}return i;}"),
        "for-outermost-redeclaration": (
            "int main(){for(int i=0;i<1;i=i+1){int i=2;}return 0;}"),
        "invalid-for-init": "int main(){for(return 0;true;1){}return 0;}",
        "missing-do-while": "int main(){do{}return 0;}",
        "conflicting-C-linkage": (
            'int f(int); extern "C" int f(int);'),
        "conflicting-C++-linkage-block": (
            'extern "C" int f(int); extern "C++" {int f(int);}'),
        "conflicting-C-signature": (
            'namespace A{extern "C" int f(int);}'
            'namespace B{extern "C" int f(bool);}'),
        "reference-temporary": (
            "int f(int& x){return x;}int main(){return f(42);}"),
        "reference-converted-binding": (
            "int f(int& x){return x;}int main(){bool n=true;return f(n);}"),
        "reference-value-ambiguity": (
            "int f(int x);int f(int& x);int main(){int n=1;return f(n);}"),
        "reference-local-no-initializer": "int main(){int& n;return 0;}",
        "reference-local-temporary": "int main(){int& n=42;return n;}",
        "conflicting-type-signs": "unsigned signed int f();",
        "long-long-extension": "long long f();",
        "invalid-integer-suffix": "int main(){return 1LL;}",
        "hex-missing-digits": "int main(){return 0x;}",
        "bool-decrement": "int main(){bool b=true;--b;return b;}",
        "postfix-reference-prohibited": (
            "int f(int&);int main(){int n=1;return f(n++);}"),
        "postfix-not-lvalue": "int main(){int n=1;(n++)=42;return n;}",
        "comma-final-not-lvalue": "int main(){int n=1;(n,42)=3;return n;}",
        "value-cast-not-lvalue": "int main(){int n=1;(int(n))=3;return n;}",
        "reference-cast-temporary": (
            "int main(){return static_cast<int&>(42);}"),
        "reference-cast-wrong-type": (
            "int main(){bool n=true;return static_cast<int&>(n);}"),
        "functional-cast-multiple-arguments": "int main(){return int(1,2);}",
        "duplicate-declarator": "int main(){int a=1,a=2;return a;}",
        "direct-init-multiple-arguments": "int main(){int a(1,2);return a;}",
        "const-assignment": "int main(){const int n=1;n=3;return n;}",
        "const-compound-assignment": "int main(){const int n=1;n+=3;return n;}",
        "const-prefix-update": "int main(){const int n=1;return ++n;}",
        "const-postfix-update": "int main(){const int n=1;return n++;}",
        "const-reference-binding": (
            "int main(){const int n=1;int& r=n;return r;}"),
        "const-static-reference-cast": (
            "int main(){const int n=1;return static_cast<int&>(n);}"),
        "const-parameter-write": "int f(const int n){return ++n;}",
        "const-no-initializer": "int main(){const int n;return 0;}",
        "const-conditional-write": (
            "int main(){const int a=1,b=2;(true?a:b)=3;return a;}"),
        "const-comma-write": "int main(){const int n=1;(3,n)=42;return n;}",
        "const-reference-feature-boundary": "int f(const int&);",
        "void-return-value-prohibited": "void f(){return 42;}",
        "nonvoid-bare-return": "int f(){return;}",
        "nonvoid-return-void": "void f(){}int main(){return f();}",
        "void-local-object": "int main(){void n;return 0;}",
        "void-call-argument": (
            "void f(){}int g(int);int main(){return g(f());}"),
        "void-binary-operand": "void f(){}int main(){return 1+f();}",
        "void-unary-operand": "void f(){}int main(){return !f();}",
        "void-condition": "void f(){}int main(){if(f())return 1;return 0;}",
        "void-conditional-mismatch": "void f(){}int main(){true?f():1;}",
        "void-cast-to-value": (
            "void f(){}int main(){return static_cast<int>(f());}"),
        "void-parenthesized-declaration": "int main(){void(n);return 0;}",
        "ambiguous-syntax-redeclaration": (
            "int main(){int n=1;int(n);return n;}"),
    }
    for name, source in invalid_calls.items():
        parent = "0011" if "namespace" in name else "0014"
        variant(name, f"REQ-{parent}", f"TC-{parent}", lambda n=name, s=source:
                rejection(n, s.encode("ascii")))
    for name, expression in (
        ("nested-boundary", "(" * 129 + "1" + ")" * 129),
        ("flat-boundary", "+".join(["1"] * 130)),
    ):
        variant(name, "REQ-0037", "TC-0037", lambda n=name, e=expression:
                rejection(n, ("int main(){return " + e + ";}").encode()))
    variant("accepted-expression-boundary", "REQ-0037", "TC-0037",
            lambda: execute("depth-accepted", "int main(){return " +
                            "(" * 127 + "1" + ")" * 127 + ";}", 1))
    variant("accepted-tree-boundary", "REQ-0037", "TC-0037",
            lambda: execute("tree-accepted", "int main(){return " +
                            "+".join(["1"] * 128) + ";}", 128))
    parameters = ",".join(f"int x{i}" for i in range(16))
    values = ",".join(str(i + 1) for i in range(16))
    addition = "+".join(f"x{i}" for i in range(16))
    variant("accepted-parameter-boundary", "REQ-0037", "TC-0037",
            lambda: execute("parameters-accepted",
                            f"int f({parameters}){{return {addition};}}"
                            f"int main(){{return f({values});}}", 136))
    variant("rejected-parameter-boundary", "REQ-0037", "TC-0037",
            lambda: rejection("parameters-rejected",
                              (f"int f({parameters},int x16);"
                               ).encode("ascii")))
    identifier = "f" + "x" * 1023
    variant("accepted-identifier-boundary", "REQ-0037", "TC-0037",
            lambda: execute("identifier-accepted",
                            f"int {identifier}(){{return 42;}}"
                            f"int main(){{return {identifier}();}}", 42))
    variant("rejected-identifier-boundary", "REQ-0037", "TC-0037",
            lambda: rejection("identifier-rejected", (
                "int " + identifier + "x(){return 0;}"
            ).encode("ascii")))
    scope = "N" * 1024
    variant("rejected-qualified-name-expansion", "REQ-0037", "TC-0037",
            lambda: rejection("namespace-size-rejected", (
                ("namespace " + scope + "{") * 5 + "}" * 5
            ).encode("ascii")))
    alias_chain = "namespace N{int f(){return 42;}}namespace A0=N;" + "".join(
        f"namespace A{i}=A{i-1};" for i in range(1, 256)
    )
    variant("accepted-namespace-alias-boundary", "REQ-0037", "TC-0037",
            lambda: execute("alias-chain", alias_chain +
                            "int main(){return A255::f();}", 42))
    variant("rejected-namespace-alias-boundary", "REQ-0037", "TC-0037",
            lambda: rejection("aliases-rejected", (alias_chain +
                              "namespace A256=A255;").encode("ascii")))
    namespace_set = "".join(f"namespace N{i}{{}}" for i in range(256))
    variant("accepted-named-namespace-boundary", "REQ-0037", "TC-0037",
            lambda: translate("namespace-count", namespace_set +
                              "int main(){return 0;}"))
    variant("rejected-named-namespace-boundary", "REQ-0037", "TC-0037",
            lambda: rejection("namespaces-rejected", (namespace_set +
                              "namespace N256{}").encode("ascii")))
    variant("conversion-tree-boundary", "REQ-0037", "TC-0037",
            lambda: rejection("conversion-depth", (
                "bool f(){return " + "+".join(["1"] * 128) + ";}"
            ).encode("ascii")))

    def malformed_corpus():
        """Exercise bounded invalid-token partitions; never accept a crash."""
        generator = random.Random(981)
        tokens = ["int", "bool", "main", "(", ")", "{", "}", ";", "return",
                  "if", "while", "=", "+", "1", "true", "f", ",", "?", ":"]
        for index in range(64):
            source = " ".join(
                generator.choice(tokens) for _ in range(generator.randrange(
                    1, 80
                ))
            )
            rejection(f"seeded-malformed-{index}", source.encode("ascii"))

    variant("seeded-malformed-corpus", "REQ-0037", "TC-0037",
            malformed_corpus)

    def separate_units():
        """Verify the provisional symbol contract against independent C."""
        obj = translate("answer", "int answer() { return 42; }")
        harness = output / "caller.c"
        harness.write_text(
            "extern int tinypp_fn_answer__v(void);\n"
            "int main(void) { return tinypp_fn_answer__v() == 42 ? 0 : 1; }\n",
            encoding="ascii",
        )
        exe = output / "separate.exe"
        command([
            options.backend, f"-B{options.runtime}", harness, obj, "-o", exe,
        ])
        command([exe])

    variant("separate-C-boundary", "REQ-0027", "TC-0027", separate_units)

    def declared_c_boundary():
        """Link a declared C entry and call it from an independent C unit."""
        obj = translate("export-C", 'extern "C" int answer(){return 42;}')
        harness = output / "C-caller.c"
        harness.write_text(
            "extern int answer(void);int main(void){return answer();}\n",
            encoding="ascii",
        )
        exe = output / "C-linkage.exe"
        command([
            options.backend, f"-B{options.runtime}", harness, obj, "-o", exe,
        ])
        command([exe], 42)

    variant("declared-C-linkage-boundary", "REQ-0025", "TC-0025",
            declared_c_boundary)

    def separate_cpp_units():
        """Resolve a declared C++ overload across separately emitted objects."""
        producer = translate("cpp-producer", "int answer(int x){return x+1;}")
        consumer = translate(
            "cpp-consumer", "int answer(int); int main(){return answer(41);}",
        )
        exe = output / "cpp-separate.exe"
        command([
            options.backend, f"-B{options.runtime}", producer, consumer,
            "-o", exe,
        ])
        command([exe], 42)

    variant("separate-C++-units", "REQ-0025", "TC-0025", separate_cpp_units)

    def separate_namespace_aliases():
        """Alias spellings must preserve the original external symbol."""
        producer = translate("alias-producer",
                             "namespace N{int answer(int n){return n+1;}}")
        consumer = translate("alias-consumer",
                             "namespace N{int answer(int);}namespace A=N;"
                             "int main(){return A::answer(41);}")
        exe = output / "aliases-separate.exe"
        command([
            options.backend, f"-B{options.runtime}", producer, consumer,
            "-o", exe,
        ])
        command([exe], 42)

    variant("namespace-alias-separate-units", "REQ-0011", "TC-0011",
            separate_namespace_aliases)

    def driver_link():
        """Compile and link through the owned driver, then execute natively."""
        src, exe = output / "driver.cpp", output / "driver.exe"
        src.write_text(
            "int square(int x){return x*x;} int main(){return square(7);}\n",
            encoding="ascii",
        )
        command([
            options.compiler, "-std=c++98", "--runtime", options.runtime,
            src, "-o", exe,
        ])
        command([exe], 49)

    variant("driver-native-link", "REQ-0027", "TC-0027", driver_link)

    def driver_multiple_sources():
        """Compile each source independently before linking the typed units."""
        first, second = output / "unit one.cpp", output / "unit two.cpp"
        first.write_text(
            "int add(int,int);int main(){return add(12,30);}\n",
            encoding="ascii",
        )
        second.write_text(
            "int add(int a,int b){return a+b;}\n", encoding="ascii",
        )
        exe = output / "multiple.exe"
        command([
            options.compiler, "--runtime", options.runtime, first, second,
            "-o", exe,
        ])
        command([exe], 42)

    variant("driver-multiple-source-link", "REQ-0025", "TC-0025",
            driver_multiple_sources)

    def driver_atomic_failure():
        """A later source diagnostic must prevent executable publication."""
        first, second = output / "valid-unit.cpp", output / "bad-unit.cpp"
        first.write_text("int main(){return 42;}\n", encoding="ascii")
        second.write_text("int bad(){return missing;}\n", encoding="ascii")
        exe = output / "must-not-publish.exe"
        child = command([
            options.compiler, "--runtime", options.runtime, first, second,
            "-o", exe,
        ], expected=1)
        assert b"bad-unit.cpp:1:" in child.stderr
        assert not exe.exists()
        command([
            options.compiler, "-c", first, second, "-o", exe,
        ], expected=2)
        assert not exe.exists()

    variant("driver-later-source-failure", "REQ-0007", "TC-0007",
            driver_atomic_failure)

    def driver_input_count():
        """Reject an over-limit command before attempting file access."""
        arguments = [f"absent-{index}.cpp" for index in range(33)]
        child = command([
            options.compiler, "--runtime", options.runtime, *arguments,
            "-o", output / "over-limit.exe",
        ], expected=2)
        assert b"source file limit exceeded" in child.stderr

    variant("driver-source-count-limit", "REQ-0037", "TC-0037",
            driver_input_count)

    def native_unwind_tables():
        """Inspect OS unwind metadata; this does not prove C++ EH cleanup."""
        execute("unwind-metadata", "int f(int x){return x+1;}"
                "int main(){return f(41);}", 42)
        data = (output / "unwind-metadata.exe").read_bytes()
        pe = struct.unpack_from("<I", data, 60)[0]
        count, optional_size = struct.unpack_from("<H", data, pe + 6)[0], (
            struct.unpack_from("<H", data, pe + 20)[0]
        )
        optional = pe + 24
        assert struct.unpack_from("<H", data, optional)[0] == 0x20B
        directory, length = struct.unpack_from("<II", data, optional + 136)
        assert directory and length >= 12 and length % 12 == 0
        sections = []
        for index in range(count):
            header = optional + optional_size + index * 40
            virtual_size, rva, raw_size, raw = struct.unpack_from(
                "<IIII", data, header + 8
            )
            sections.append((rva, virtual_size, raw, raw_size))

        def offset(rva):
            """Map a file-backed PE RVA, rejecting absent or virtual bytes."""
            for start, size, raw, raw_size in sections:
                delta = rva - start
                if 0 <= delta < size and delta < raw_size:
                    return raw + delta
            raise AssertionError(f"RVA {rva:#x} is not file backed")

        table = offset(directory)
        previous = 0
        for index in range(length // 12):
            begin, end, unwind = struct.unpack_from(
                "<III", data, table + index * 12
            )
            assert previous <= begin < end, "Unsorted or invalid unwind range"
            offset(begin)
            offset(end - 1)
            assert data[offset(unwind)] & 7 == 1, "Unknown unwind version"
            previous = end
        current["observation"] = {
            "runtime_function_entries": length // 12,
            "scope": "PE x64 unwind structure; no C++ handler/cleanup proof",
        }

    variant("native-unwind-table-structure", "REQ-0026", "TC-0026",
            native_unwind_tables)

    def preserve_output():
        """Ensure successful emission cannot overwrite an existing path."""
        src, obj = output / "preserve.cpp", output / "preserve.o"
        src.write_text("int main(){return 0;}\n", encoding="ascii")
        obj.write_bytes(b"original artifact")
        command([options.compiler, "-c", src, "-o", obj], expected=1)
        assert obj.read_bytes() == b"original artifact"
        command([options.compiler, "-c", src, "-o", src], expected=2)
        assert src.read_text() == "int main(){return 0;}\n"
        assert not list(output.glob("tpp*.tmp")), "Temporary outputs leaked"

    variant("output-preservation", "REQ-0037", "TC-0037", preserve_output)
    variant("comment-location", "REQ-0012", "TC-0012", lambda: execute(
        "comments", "// header\nint /* type */ main() { return 3/*x*/+4; }", 7
    ))
    def diagnostic_location(newline, name):
        """Require a semantic error at the identifier, not later lookahead."""
        src, obj = output / (name + ".cpp"), output / (name + ".o")
        src.write_bytes(newline.join([
            b"int main(){", b"  return missing;", b"}",
        ]) + newline)
        child = command([options.compiler, "-c", src, "-o", obj], expected=1)
        assert b":2:10: error: undeclared identifier 'missing'" in child.stderr
        assert not obj.exists()

    for name, newline in (("diagnostic-LF", b"\n"),
                          ("diagnostic-CRLF", b"\r\n")):
        variant(name, "REQ-0006", "TC-0006", lambda n=name, e=newline:
                diagnostic_location(e, n))
    def spliced_diagnostic():
        """Check physical coordinates for an identifier joined across lines."""
        src, obj = output / "spliced-error.cpp", output / "spliced-error.o"
        src.write_bytes(b"int main(){\n  return mis\\\nsing;\n}\n")
        child = command([options.compiler, "-c", src, "-o", obj], expected=1)
        assert b":2:10: error: undeclared identifier 'missing'" in child.stderr
        assert not obj.exists()

    variant("phase-physical-diagnostic", "REQ-0008", "TC-0008",
            spliced_diagnostic)
    def trigraph_diagnostic():
        """Check byte columns after a three-byte source character mapping."""
        src, obj = output / "trigraph-error.cpp", output / "trigraph-error.o"
        src.write_bytes(b"int main()??< return missing; ??>\n")
        child = command([options.compiler, "-c", src, "-o", obj], expected=1)
        assert b":1:22: error: undeclared identifier 'missing'" in child.stderr
        assert not obj.exists()

    variant("phase-trigraph-physical-column", "REQ-0008", "TC-0008",
            trigraph_diagnostic)
    variant("implicit-final-newline-policy", "REQ-0034", "TC-0034",
            lambda: execute("implicit-final-newline",
                            "int main(){return 42;}", 42, False))
    failed = sum(result["status"] != "Pass" for result in results)
    revision = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"], cwd=options.root,
        capture_output=True, text=True, check=False,
    )
    owned = [options.root / "CMakeLists.txt"]
    for directory in ("src", "tools", "tests"):
        owned.extend(
            path for path in (options.root / directory).rglob("*")
            if path.suffix in (".cpp", ".hpp", ".py")
        )
    specs = {
        result["test_id"] for result in results
    }
    dependency_revisions = {}
    for name in dependency_paths(options.root):
        dependency_revisions[name] = subprocess.check_output(
            ["git", "-C", str(options.root / name), "rev-parse", "HEAD"],
            text=True,
        ).strip()
    host_records = list((options.compiler.parent.parent / "CMakeFiles").glob(
        "*/CMakeCXXCompiler.cmake"
    ))
    evidence = {
        "kind": "Partial compiler-foundation evidence; not full TC closure",
        "started": started,
        "finished": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "host": platform.platform(), "architecture": platform.machine(),
        "configuration": options.configuration,
        "dependency_revisions": dependency_revisions,
        "host_toolchain_record": host_records[0].read_text("utf-8")
        if len(host_records) == 1 else "Not available for this build path",
        "compiler": str(options.compiler),
        "compiler_sha256": hashlib.sha256(
            options.compiler.read_bytes()
        ).hexdigest(),
        "backend_sha256": digest(options.backend),
        "backend_library_sha256": digest(
            options.compiler.parent / "tinypp_tcc.dll"
        ),
        "runtime_archive_sha256": digest(options.runtime / "lib/libtcc1.a"),
        "owned_source_sha256": {
            path.relative_to(options.root).as_posix(): digest(path)
            for path in sorted(owned)
        },
        "test_specification_sha256": {
            tid: digest(options.root / f"docs/testing/cases/{tid}.tex")
            for tid in sorted(specs)
        },
        "input_sha256": {
            path.name: digest(path) for path in sorted(output.iterdir())
            if path.suffix in (".cpp", ".c")
        },
        "source_revision": revision.stdout.strip() if not revision.returncode
        else "unborn HEAD; uncommitted working tree",
        "results": results, "failed": failed,
    }
    stable = baseline == source_snapshot(options.root) and binary_baseline == {
        str(path): digest(path) for path in binaries
    }
    evidence["baseline_stable"] = stable
    evidence["controlled_input_sha256"] = baseline
    evidence["binary_input_sha256"] = binary_baseline
    (output / "results.json").write_text(
        json.dumps(evidence, indent=2) + "\n", encoding="utf-8",
    )
    print(f"Evidence: {output / 'results.json'}")
    return failed or not stable


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("compiler", "backend", "root", "output", "runtime"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--configuration", required=True)
    raise SystemExit(bool(run_suite(parser.parse_args())))
