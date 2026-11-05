# Digital Mars compiler source assessment

**Content type:** Dependency research and feasibility work plan

**Status:** Adapted Win32 build and bounded x64 C ABI probes demonstrated;
Tiny++ integration and complete ABI/runtime acceptance remain open.

**Date:** 2026-10-31. Updated 2026-11-01.

## Identity and changed finding

The user added [DigitalMars/Compiler](https://github.com/DigitalMars/Compiler)
as the `Compiler` submodule at
`69824bc4f030a2585feef1c7a9bc423d14e809ca`. The checkout is clean.
This repository supplies C/C++ compiler implementation, distinct from the
previously inspected `dmc` distribution/runtime checkout. The earlier
source-availability limitation does not apply to this new repository.

The files are largely D modules with C/C++ external interfaces and shared
DMD backend types. Availability changes the reuse options; it does not yet
establish that a component can be extracted or that the compiler is C++98
conforming. Source comments also contain later maintenance and extensions.

## Candidate module map

Paths below are relative to Compiler/dm/src/dmc. Selection follows inspected
file descriptions, declarations and representative implementation bodies;
it is not an exhaustive code or conformance review.

| Area | Files and inspected entry points | Tiny++ allocation and next check |
| --- | --- | --- |
| Parser contracts and C++ semantics | parser.d, dcpp.d; conversion-match records and C++ routines | M3, REQ-0010/0012/0014: inspect representation, overload ranking and backend dependencies. parser.d includes contracts; do not mistake it for the entire parser. |
| Scope and namespace lookup | dscope.d, nspace.d, adl.d; namespace_definition and using-directive machinery | M3, REQ-0011: compare hiding, aliases, using and associated-scope rules against reviewed cases. ADL comments explicitly identify C++98 lookup. |
| Type representation | dtype.d; type_setcv, type_allocmemptr, typematch | M3, ADR-0009: evaluate qualified/nested types, ownership and equality; separate shared D-specific forms from C++ types. |
| Classes and inheritance | dstruct.d, dcpp.d | M4, REQ-0015/0016/0017: inspect incomplete types, bases, access and virtual dispatch before selecting layout machinery. |
| Expressions and conversions | exp.d, dexp2.d | M3, REQ-0012/0014: extract semantic dependencies and lifetime effects; avoid assuming target C conversions implement C++ rules. |
| Statements and lifetime | func.d; func_expr_dtor, func_adddestructors, return/loop/try handlers | M3/M4, REQ-0013/0015: map full expressions and all cleanup exits into ADR-0009's explicit regions. |
| C++ EH emission | eh.d; except_obj_ctor, except_obj_dtor, except_throw_expression, except_gentables | M4, REQ-0022/0023: distinguish compiler metadata generation from runtime exception propagation in dmc/src/core/except.cpp. |
| RTTI emission | rtti.d; rtti_cast, rtti_typeid | M4, REQ-0024: map emitted descriptors and required runtime helpers; compare with dmc runtime matching. |
| Native emission references | nteh.d, mscoffobj.d | M1/M4, REQ-0026/0027/0044: inspect target guards and unwind/object contracts. File presence is not proof of a working C++ x64 backend. |
| Templates | dtemplate.d | External M5/M6 owner only: offer as a candidate; no duplicate template engine or inferred export completeness. |

## Build evidence and discrepancies

The local README documents a Win32 build using DMC and DMD 2.074.1 with a
runtime-header adjustment. The checked-in .github/workflows/ci.yml instead
selects DMD 2.092.0, a DMC 8.57 archive and Windows 2019. Its archive SHA-256
is `aabd977b83134d38615e56d105ea1f505778d1a3a29c88836b95ce2339b10057`.
That hash is an upstream configuration observation, not a locally verified
download identity. This workflow was not executed during this assessment; a separate local
build attempt and its controlled adaptation are recorded below.

The makefile uses D betterC, disabled bounds checking, module remapping and
SCPP/SPP/HTOD configurations. It contains legacy installation paths plus
copy/upload and release targets. An isolated build must invoke only reviewed
build targets, retain the original submodule unchanged and keep generated
files in an output copy. Do not execute packaging/deployment targets as part
of feasibility work.

The README describes Win32 and older targets. Modern shared backend files
do not prove that the C++ front end is ready for Windows x64. Our native
TinyCC path and scalar regressions remain the working baseline.

## Notice assessment

The [reuse inventory](reuse-audit.csv) adds twenty-two files from this checkout
with exact byte hashes and observed holders. All twenty-two have explicit
Boost 1.0 file-header grants. In particular dtype.d, nteh.d and mscoffobj.d
identify the D Language Foundation and carry explicit grants, while the root
LICENSE holder list does not name that foundation. This demonstrates why
per-file inspection remains necessary. Full provenance, transitive headers,
generated source and tool/binary redistribution remain open under REQ-0035
and REQ-0036. Nothing has been imported into the owned compiler source.

## Dependency-ordered feasibility work

| Probe | Procedure and retained evidence | Acceptance boundary |
| --- | --- | --- |
| DM-01: isolated build | Resolve README/CI tool versions; verify downloaded tool identities; build SCPP in a generated source copy; retain commands, diagnostics and binary hashes. | A reproducible source-built compiler, not a claim that the existing dmc.exe was built from this revision. |
| DM-02: behavioral comparison | Run existing scalar positives and diagnosed negatives with the source-built compiler; add final-edition-reviewed lookup and type partitions. | Every outcome retains its oracle source; disagreements are investigated rather than decided by compiler consensus. |
| DM-03: extraction boundary | Trace representative namespace lookup and type/conversion operations through imports, globals, allocation, symbols and emitted elem nodes. | An enumerated dependency closure and ownership/threading model, with measured effort for C++ adaptation versus a D component. |
| DM-04: lifetime and x64 | Trace cleanup construction order, exceptional exits, descriptors and runtime symbols; execute a native x64 cleanup spike after adapting the selected boundary. | Reverse cleanup, handler matching and unwind integration demonstrated; PE unwind-table presence alone is insufficient. |
| DM-05: architecture choice | Compare selective adaptation, a D semantic component and independent implementation against the existing suite and build constraints. | Review ADR-0010 with measurements before changing the production path or final ABI. |

DM-01 now has partial adapted-build evidence and DM-02 has ten compile-only
and eight native partitions. Pristine reproducibility and full comparison
coverage remain open. DM-03 now has configured import measurements and
DM-04 has initial failure/ABI evidence below; extraction closure, native x64
EH/RTTI and the DM-05 decision remain open. These expand M0/M1
inspection and feasibility work under TC-0035, TC-0026/0027 and TC-0044;
they do not close the parent capabilities. Templates and library integration
remain allocated to the existing external project.

## References

- [ADR-0010](../architecture/ADR-0010.md).
- [DMC distribution and project boundary](dmc-reuse.md).
- [Qualified types and lifetimes](../architecture/ADR-0009.md).
- [Roadmap](../ROADMAP.md).

## Executed Win32 build spike

The unmodified source attempt fails in elem.d because it accesses Cent.lsw
and Cent.msw, while cdef.d defines Cent.lo and Cent.hi. An opt-in adaptation
adds D field aliases `lsw = lo` and `msw = hi` in the generated cdef.d copy;
it adds no storage. The helper checks the inspected revision and exact
expected struct before applying it. The original submodule remains clean.
This is an adapted build, not proof that the pristine revision builds.

The successful build uses DMD 2.092.0, the pinned distribution's DMC 8.42n
and make, and Optlink bundled with DMD. The resulting PE x86 compiler banner
is Digital Mars C/C++ Compiler Version 9.01.0n. The downloaded DMD Windows
archive has SHA-256
`417d36819f54279cad7e151bac95738c41ec2790a0ed050e94370d86b30e790c`.
It was retrieved from the official HTTPS release archive; a detached
signature was not verified. Tool and generated-source identities are
recorded separately from the fact that compilation succeeds.

Today's official dm857c.zip has SHA-256
`f51cdfeb45eaf4ffbf7abf0fe9b3d548b202b4528401005c2c3192b00bc32367`,
which differs from the upstream CI pin recorded above. That archive was
not extracted or executed. The local attempt instead uses the already
pinned dmc checkout; it is not a reproduction of upstream CI's tool bundle.

The tools retain unique output/dmc-source, dmc-comparison and dmc-native
run directories, complete commands, diagnostics, input identities and
per-probe verdicts. Start/end checks compare controlled inputs and tool
binaries. The build records hashes of copied inputs and generated source.
The native runner checks PE x86 identity and expected process exit values.
These comparisons are partial development evidence, not parent TC closure.

Reproduce with an explicitly supplied local DMD toolchain:

```powershell
python tools/build_dmc_source.py `
  --dmd output/toolchains/dmd-2.092.0/dmd2/windows/bin/dmd.exe `
  --dmc dmc/bin/dmc.exe `
  --linker output/toolchains/dmd-2.092.0/dmd2/windows/bin/optlink.exe `
  --cent-field-aliases
```

Use that run's source/scppn.exe and results.json with `--compiler` and
`--build-record` in tools/probe_dmc.py and tools/probe_dmc_native.py.
The compiler's direct invocation needs an explicit distribution header path;
the comparison helper supplies it. Negative probes now require the intended
diagnostic, preventing missing-header failures from masquerading as correct
rejections. The original ten comparisons pass with both 8.42n and 9.01.0n.

The eight native partitions cover scalars, using-directives, virtual dispatch,
normal cleanup, catch matching, exceptional cleanup, const-reference temporary
lifetime and ADL. Objects come from the source-built compiler; the distribution
driver links them against its Win32 runtime. This does not demonstrate the
Tiny++ C adapter, external library integration or Windows x64 EH/ABI.

## Executed x64 COFF and C ABI spike

The C++ target selector in dgetcmd.d accepts `-m64`, sets EX_WIN64 and
OBJ_MSCOFF, and selects 64-bit type sizes. This is stronger source evidence
than the legacy README, but the unadapted path fails in several measured
ways. The [defect ledger](dmc-defects.csv) separates those failures from
successful probe results.

The opt-in adaptations in the output copy enable bounded execution:

- dnwc.d selects unsigned long long for synthesized allocation sizes on I64;
  Win32 declarations stay unchanged. This fixes the compiler's own declaration
  diagnostics; it does not supply a working x64 allocation runtime.
- out.d calls the existing Win64 parameter allocator for every parameter,
  classifies register parameters with shadow slots, and retains the legacy
  path for other targets. The old first-symbol-only logic produced a wrong
  result for an eight-integer MSVC-to-DMC call.
- A late lowering pass handles indirect POD parameters and arguments after
  inline expansion. It clones ABI parameter symbols, rewrites accesses through
  the incoming pointer and creates aligned caller temporaries for value copies.
  Original semantic parameter types and inline bodies remain intact.
- dexp2.d classifies Win64 POD returns: 1/2/4/8-byte values use registers;
  other sizes use hidden result storage. Nontrivial class returns retain the
  legacy path and remain unverified.

The build helper exposes these as `--x64-new-declarations` and
`--x64-parameter-registers`, `--x64-pod-parameters` and `--x64-pod-returns`,
alongside `--cent-field-aliases`. Each records original/adapted file hashes.
All adaptations require the inspected revision and guarded source sites.
The owned lowering source is tools/dmc_pod_lowering.d; it is hashed in
controlled evidence and inserted only into the generated out.d.

Moving indirect parameter representation into parsing fixed the original
cross-compiler read but broke source calls and inlining. The final approach
keeps that ABI transformation after inline expansion and also lowers outgoing
POD arguments. This phase boundary is necessary for value-copy semantics;
matching the incoming register alone is insufficient.

The target contract is Microsoft's
[x64 calling convention](https://learn.microsoft.com/en-us/cpp/build/x64-calling-convention).
Caller temporaries for indirect aggregate arguments have 16-byte alignment.
The experimental lowering restricts its new object handling to PODs;
nontrivial construction and destruction need a separate lifetime contract.

The x64 probe helper initially used `-m64 -Nc`. Without -Nc, the pristine
frontend and COFF backend publish duplicate function symbols, and MSVC rejects
the object with LNK2005/LNK1169. The publication adaptation below removes
that workaround for the tested partitions.
It also avoids strict mode, EH and RTTI and links without a CRT. Therefore
these results are target/ABI feasibility observations, not C++98 conformance.

All 44 native partitions pass both without target optimization and with DMC
-o enabled. They include integer/floating register and stack arguments,
references, pointers, callbacks, local virtual dispatch, normal cleanup,
independent value copies, caller-copy alignment, sizeof and source/inline
calls. POD argument and return probes cover 1 through 9, 12, 16 and 24 bytes.
The original large-POD failure remains a regression fixture with the original
expected result; it was not suppressed or converted to an expected failure.

Both objects are checked as x64 COFF and the linked executable as PE x64.
MSVC compiles a separate C caller and links the objects; every executed
positive expects process status 42. Results, source/object/executable hashes,
commands and outputs remain under output/dmc-x64. The compiler binary is
matched to its successful adapted-build record, and input/tool stability is
checked. The ten Win32 compile-only and eight native Win32 cases also pass
with the additional adaptations enabled.

Strict-mode headers, x64 EH/RTTI runtime, nontrivial class calling conventions,
exception cleanup, variadic/vector cases and complete layout remain open.
Do not select a complete backend replacement from this spike. DM-03 still
needs a reviewed ownership and extraction contract, and DM-05 still needs an
architecture decision. The Tiny++ C adapter has not been replaced.

## Assertions and debug information follow-up

An assertions-enabled build exposed a deferred relocation-width mismatch in
cgen.d during callback emission. `--x64-relocation-widths` reserves four bytes
for rel32 references unless CFoffset64 requests an eight-byte reference.
This fixes the observed COFF writer assertion without disabling assertions.

Two optional debug adaptations address separate CV8 failures:
`--coff-debug-filename` supplies the COFF object filename to Obj.term, avoiding
a null filename in cv8_termfile; `--coff-aggregate-debug` routes SCPP aggregate
forward references and function symbols through the existing CV8 emitters.
Aggregate types remain opaque forward records. Member fields, variable
display and complete class type information are not established.

With the original eight adaptation switches and `--enable-assertions`, the compiler
passes all 44 x64 partitions with `--optimize --debug-info`. The probe checks
COFF debug sections and the linked PDB signature as well as native results.
The ten compile-only and eight Win32 execution partitions also pass.

The optional host fixture tests/pdb_inspection.cpp loads an explicitly named
Microsoft DIA DLL without COM registration. It resolves answer, B::f and D::f
and their source lines in a generated virtual-dispatch PDB. An absent function
and an absent PDB produce distinct nonzero statuses. Build it with the host
DIA SDK, diaguids.lib, ole32.lib, oleaut32.lib and advapi32.lib.
The recorded fixture run is output/pdb-inspection/
f8ccfee109b749cc84e1c8c4ccd02bfc/results.json.

This is symbol-reader evidence, not stepping or debugger qualification.
The installed LLDB cannot start because liblldb.dll is absent, and the WSP
GDB qualification gate remains open. Complete aggregate debug records and
debug variable fidelity require separate probes before acceptance.

## Default COFF function publication

`--coff-function-publication` adds a ninth guarded output-copy adaptation.
The COFF backend already publishes function symbols in MsCoffObj_func_start;
out.d published SCglobal functions again after code generation. The adapted
post-generation path retains OMF publication and leaves COFF publication to
the backend. This changes neither the pristine checkout nor the OMF path.

With this adaptation, `tools/probe_dmc_x64.py --no-nc` passes all 44 cases
without the all-COMDAT workaround. Both unoptimized and optimized/debug
profiles pass with compiler assertions enabled. The eight Win32 native
regressions also pass. Default symbol publication is therefore demonstrated
for these partitions; arbitrary multi-object C++ linkage and COMDAT selection
remain unverified.

Build evidence: output/dmc-source/20261101-093731-da2bcbb0/results.json.
Optimized/debug x64 evidence: output/dmc-x64/
20261101-093818-08b1f168/results.json. Unoptimized x64 evidence:
output/dmc-x64/20261101-093840-9048d2db/results.json.

## Configured semantic imports and ownership observations

`tools/trace_dmc_dependencies.py` runs the recorded DMD compiler with `-o-`
and `-deps` against a successful isolated SCPP source build. It checks copied
and generated input hashes, retains raw dependency records and commands, and
hashes imported sources. Paths rather than module names define reachability
because some interfaces have aliases. It does not modify the source checkout.

| Seed | Direct local imports | Reachable local files | Reachable toolchain files |
| --- | --- | --- | --- |
| dscope.d | 10 | 24 | 31 |
| dtype.d | 13 | 24 | 31 |
| nspace.d | 17 | 25 | 31 |
| exp.d | 19 | 26 | 31 |
| eh.d | 18 | 26 | 31 |
| rtti.d | 14 | 25 | 31 |

These are configured semantic imports, including potentially unused code;
they are not link dependencies or an extraction closure. Evidence is under
output/dmc-dependencies/20261101-182829-43db472f. Parser controls reject empty,
unrecognized and missing-file records and check physical-path traversal;
see output/dmc-dependency-controls/aacc744c006e4719bda472337e0b9299.

Inspection also finds shared mutable state: dscope.d owns scope_end and a
scope free list; cc.d exposes config and pstate; global.d includes errcnt;
dtype.d uses type/parameter free lists and Tcount reference counting.
A borrowed Symbol/type pointer therefore needs an explicit session lifetime
and ownership contract. These routines are not established as reentrant.
Import counts do not measure port effort, prove concurrency safety or select
between full adoption, a D semantic component and selective extraction.
DM-03 still needs symbol-level dependencies and a measured bridge prototype.

## Cross-unit object model and runtime probes

The x64 helper now compiles independent probe.cpp and worker.cpp units for
constructor/destructor ordering, a nontrivial value parameter, and adjusted
virtual dispatch through a secondary base. Size variants at 8, 12 and 24
bytes also check copied payload, original-object isolation, exact copy and
destruction counts, and 16-byte caller-temporary alignment. These supplement
the original 44 ABI cases and use the same expected native result of 42.

`--x64-register-save-mask` removes the obsolete ES bit from 64-bit saved
register masks. Throw/catch and exceptional-cleanup probes then compile and
reach runtime link failures instead of the epilogue assertion.
`--x64-nontrivial-parameters` requires the existing late POD lowering switch;
it extends that output-copy pass to retain the semantic copy constructor,
construct directly in an ABI temporary and pass a pointer. It does not
replace construction with a byte copy. Classification checks SCPP copy and
destructor records because STRnotpod alone is not a reliable C++ parser flag.
Nontrivial return classification remains unverified and needs the same audit.

The 12-byte nontrivial case exposed a separate stack alignment failure after
its copy, mutation and destruction checks passed. Both stack allocation paths
use size-based alignment, and the legacy _align helper rounds a request of
16 down to register-size alignment. `--x64-local-alignment` uses explicit
rounding for Win64 symbols with an alignment request, preserving other paths.
Validation status is recorded in the feasibility defect ledger.

`--runtime-probes` adds throw/catch, exceptional cleanup, dynamic_cast and
typeid cases. They retain their compile/link/run oracle and currently fail
at link time: EH requires __eh_throw and __eh_cv; RTTI requires __rtti_cast,
Type_info and allocation support. No success is inferred from object emission,
and no no-op runtime is supplied. See output/dmc-x64/
20261101-183106-cb5bd1e7/results.json for the retained failures.

The selected legacy runtime references still contain 32-bit frame assumptions
and unresolved source-grant questions. A native runtime bridge must define
exception objects, matching, cleanup metadata, handler entry, allocation and
unwinding rather than link the Win32 binary library into x64 output.
Windows platform contracts are documented in Microsoft's
[x64 exception handling](https://learn.microsoft.com/en-us/cpp/build/exception-handling-x64)
and [ARM64 exception handling](https://learn.microsoft.com/en-us/cpp/build/arm64-exception-handling).
These OS contracts do not by themselves supply C++ matching or cleanup logic.

### Executed object-slice follow-up

With the register-mask, nontrivial-parameter and explicit-alignment switches,
all 50 default x64 probes pass unoptimized and optimized with debug data and
compiler assertions enabled, without -Nc. In particular the 12-byte class
copy constructor now receives a 16-byte-aligned destination; payload, value
isolation, one copy and two destructions also pass. The eight Win32 native
and ten compile-only regressions pass with this source-built binary.

- Build: output/dmc-source/20261101-184500-cf1af7c2/results.json.
- Optimized/debug: output/dmc-x64/20261101-184747-3e7d8dcb/results.json.
- Unoptimized: output/dmc-x64/20261101-184747-129bccc4/results.json.
- Win32: output/dmc-native/20261101-184747-9dc90e11/results.json.
- Compile-only: output/dmc-comparison/20261101-184805-5ba14eb6/results.json.
- Repeated imports: output/dmc-dependencies/20261101-184805-66362736/results.json.
- EH/RTTI link failures: output/dmc-x64/20261101-184805-91ffce5c/results.json.

The default 50-case suite excludes the four optional runtime probes; those
four still fail. These results do not close the shared vertical slice or
select a front-end integration strategy. Nontrivial returns, construction
failure, exception matching/propagation, RTTI execution and debugger variable
fidelity remain open. All source adaptations remain opt-in output-copy edits.

## Selected integration direction and signature worker

[ADR-0010](../architecture/ADR-0010.md) now selects a process-isolated semantic
worker with an owned, versioned handoff. Direct x64 compilation of dtype,
dscope and rtti succeeded in exploratory object builds. A dtype qualification
wrapper still failed to link with 45 unresolved symbols despite /OPT:REF;
parser/template services, target tables and allocation remained coupled.
The object symbol table contained 54 undefined entries before CRT resolution.
This is evidence about that extraction attempt, not proof that an in-process
library cannot be engineered. Its retained artifacts are under
output/dmc-bridge-discovery/0831618eb8984297b843f07ecec8a062 and
output/dmc-bridge-discovery/f9927f8797b24a6396350b93510eee88.

The owned optional signature exporter runs inside the existing complete worker
build, before inline and parameter lowering. Private export helpers use D
linkage because this DMD cannot C++-mangle its shared FILE implementation type.
A bounded JSON Lines consumer validates copied values, target/ABI versions,
qualifiers, identities and layouts. No DMC pointer or implementation structure
crosses the process boundary. Unknown types fail closed.

The [handoff contract](../architecture/semantic-handoff.md) records the format,
limits, native producer/consumer tests and migration gates. Nine cases pass
on x86 and x64, including namespace/type and member-cv facts, record sizes,
constructor/destructor categories, language linkage and three controls.
The independent 18-test protocol suite passes. Full-body/control-flow IR,
lifetimes, EH/RTTI, external instantiation and ARM64 profiles remain open.
The DMC emitter is still used to check instrumentation transparency; this does
not substitute for connecting the handoff to owned IR and TinyCC adapters.

## First owned body emission, 2026-11-04

The selected worker boundary now has an end-to-end scalar path: successful
semantic-only DMC export, owned typed CFG validation/lowering, TinyCC ELF64
objects and a Windows x64 executable. No DMC native object enters that link.
The reusable tools/compile_worker.py command accepts .cpp files, preserves
existing outputs and retains compilation identities/artifacts.

The initial 21-case command suite passes, including 18 native executions and
three pre-emission rejections. Scope and exact evidence are in the
[handoff contract](../architecture/semantic-handoff.md). The same worker build
retains 50 optimized/debug legacy x64 probes and eight Win32 native regressions.
A weighted eight-argument case still fails in the legacy emitter; the body
path requires successful semantic-only export and executes it through TinyCC.
This advances M1 integration while class/EH/RTTI bodies and complete target/
standards qualification remain open.

The subsequent receiver-aware v2 body protocol separates logical signatures,
implicit receiver types/arguments and lowered results. It records DMC's legacy
destructor int placeholder without treating it as a C++ result. The expanded
24-case command suite passes (19 native executions and five rejections), with
33 independent body boundary tests. The handoff contract retains build and
control evidence. Field/lifetime lowering and three-target qualification
remain open; this does not allocate templates or library implementation here.

The first owned class increment subsequently passes 30 command cases, including
25 native executables and five controls, with 43 body boundary tests. Typed byte
field addresses, aligned record carriers, logical receiver/parameter binding,
constructor/normal-destructor calls and cross-unit classes now execute through
TinyCC. This also exposes and handles DMC's reversed explicit member parameter
storage and exact indirect-address wrapper for direct destructor calls. Legacy
comparison emission still passes 50 optimized/debug x64 and eight Win32 probes.
The handoff contract retains exact evidence. General value ABI, full lifetime
regions, EH/RTTI and owned x86/ARM64 emission remain open.
