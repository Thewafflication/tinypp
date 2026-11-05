# Experimental DMC semantic handoff

**Content type:** Interface contract and migration work plan

**Status:** Proposed experimental interface. Updated 2026-11-04.

## Purpose and ownership

[ADR-0010](ADR-0010.md) selects a process-isolated DMC semantic worker as the
integration direction. One worker owns parser/configuration globals, symbol
and type pointers, reference counts and allocation until process exit. Tiny++
receives copied values and owns the decoded result. Target settings and source
identity belong to the invocation; a worker does not switch targets mid-unit.
Templates and the standard library remain allocated to the external project.

The first protocol conveys resolved function/type signatures only. It is not
executable IR, a complete class inventory, function-body semantics or a
production front-end replacement. The current worker still invokes the legacy
native emitter; native execution checks instrumentation transparency only.
The production boundary must eventually bypass that emitter and connect
owned IR to target adapters.

## Producer

`tools/build_dmc_source.py --semantic-signatures` inserts the owned
`tools/dmc_semantic_export.d` helper into an output copy of out.d, with guarded
sites and hashes. The hook observes definitions selected for native emission and runs before
local-symbol transfer, inlining and
late target parameter lowering. The pinned source checkout is unchanged.
Private helper functions use D linkage; their FILE implementation type never
crosses the worker boundary.

A caller sets TINYPP_SEMANTIC_EXPORT to a fresh output file for one invocation.
The first record truncates that file and later records append. Separate units
use separate files. With the variable absent the helper writes no stream.
Open/write/close failure terminates the worker nonzero with an export error;
a caller must require successful process status as well as a valid stream.
An empty or absent stream is not success, even when compilation succeeds.

## Signature protocol v1

The wire format is UTF-8 JSON Lines, schema tinypp.semantic-signature.v1 and
ABI dmc-experimental-v1. This ABI label records legacy layout observations;
it is not the frozen project ABI or a vendor compatibility promise.

Each record contains exactly:

- schema, target and abi; target is windows-x86 or windows-x64 in this pilot.
- function_kind: function, constructor or destructor.
- linkage: c or c++; other calling/mangling forms are unsupported.
- path_hex: ordered owner/name components as lowercase hex compiler bytes.
  No host encoding, pointer identity or transient symbol-table number is used.
- const_member, volatile_member and variadic booleans.
- result: a type record for functions, null for constructors/destructors.
- parameters: ordered explicit type records, excluding the implicit this.

A type record has kind, const and volatile. Supported scalar kinds preserve
C++ type identity, including bool versus int and int versus long even when
widths match; bytes records the observed target width. Pointer and
lvalue-reference nodes have a nested to record. Record types contain path_hex,
bytes and alignment. Incomplete layouts are rejected by the consumer.
The producer marks other forms unsupported; the consumer rejects them rather
than infer semantics. Arrays, enums, member/function pointers and further
language forms need explicit protocol extensions and tests.

Limits are 4 MiB per stream, 4096 records, 65536 bytes per line, 256 explicit
parameters, 32 levels of type nesting and symbol ownership, and 512 bytes per
identifier component. Consumer file reads are bounded before JSON decoding.
Unknown/missing fields, duplicate keys/records, incompatible schema/ABI/target,
invalid booleans, malformed identifier bytes and unsupported types fail closed.
The protocol carries type shapes, not pointer values or executable addresses.

## Verification and limits

`tests/test_semantic_signatures.py` checks acceptance and failure controls;
CTest runs it as semantic-signature-boundary. The real producer/consumer probe
is `tools/probe_dmc_semantics.py`, with explicit compiler, build record, linker
and target arguments. It checks namespace-qualified types, member cv overloads,
class value types, target-dependent record layout, constructors/destructors
and language linkage; positive
programs must still compile/link/run with native result 42. Separate controls
cover disabled export, output I/O failure and unsupported function pointers.
Control success does not mean an unsupported language feature was compiled
through Tiny++ or that a parent requirement has been verified.

Before production migration, add stable declaration identities, source spans,
typed CFG/body operations, conversions, lifetime regions, exceptional exits,
RTTI and target/layout requests. Define invalidation, diagnostics, partial-unit
failure and external instantiation behavior. Version and test these changes;
do not interpret signature-only success as body or EH handoff.

ARM64 requires a target profile, protocol acceptance and native adapter/runtime
qualification. A label or existing TinyCC backend alone cannot establish it.
See the [roadmap](../ROADMAP.md) for the three-target completion gates.

## Executed pilot evidence

All nine cases pass on each target, including six positive signature cases and
three controls. Eight native programs per target return 42; the output-failure
control exits nonzero as required. The optional hook also retains all 50
optimized/debug x64 ABI/object probes and eight Win32 regressions.

- Signature-worker build: output/dmc-source/20261101-191122-d0e6a7fd/results.json.
- x64 handoff: output/dmc-semantics/20261101-191434-5cd06159/results.json.
- x86 handoff: output/dmc-semantics/20261101-191434-2a9ce253/results.json.
- x64 native regressions: output/dmc-x64/20261101-191339-6cf425eb/results.json.
- Win32 regressions: output/dmc-native/20261101-191339-7271a23a/results.json.

These are development fixtures with parent requirements unverified. The
existing independent scalar compiler remains the working product prototype;
this signature consumer does not route functions into TinyCC yet.

## Typed function body protocol v2

The experimental body path now connects the worker to owned IR validation,
owned target-C generation and TinyCC emission. `--semantic-bodies` requires
`--semantic-signatures` when building the worker; it inserts the owned
`tools/dmc_semantic_body.d` helper into an output copy of out.d. The body hook
runs after semantic blocks and local bindings exist, before inlining and ABI
parameter lowering. It retains logical type identities rather than exporting
backend register assignments or DMC pointer values.

Set TINYPP_SEMANTIC_BODY to a fresh per-unit stream and
TINYPP_SEMANTIC_BODY_ONLY=1 for compilation through Tiny++. This mode queues
referenced function bodies, including internal/inline functions, exports each
body, releases its copied blocks and clears active symbol bindings. It skips
native function emission. The legacy object-writer lifecycle still runs;
its object artifacts are retained but never used by the owned target linker.
The worker must exit successfully. An IR file from a failing worker is not
accepted. The eight-argument native backend failure in DM-X64-013 motivated
this separation; that upstream native failure remains open.

The JSON Lines schema is tinypp.function-ir.v2, ABI dmc-experimental-v1.
V1 body records are rejected; the separate signature-only protocol remains v1.
Each function record has exactly schema, target, abi, emission, function,
variables and blocks. The consumer requires emission=semantic-only and the
expected target. An observation stream from ordinary native emission cannot
substitute for successful semantic-only compilation.

- function contains path_hex, C/C++ linkage, function_kind, member cv flags,
  variadic, internal, result, explicit parameter types, receiver and
  lowered_result. Free/static functions have a null receiver. Logical
  constructor/destructor results remain null.
- variables contain unique function-local integer IDs, storage
  (parameter/local) and types. Parameter entries occur in logical binding
  order, followed by locals; their IDs preserve original expression bindings.
  Parameter bindings must match the signature.
- blocks contain ordered unique IDs, exit, successors and expression.
  Goto and branch have one and two successors respectively; returns have none.
  Every successor must resolve within the function. Reachable result types
  must agree with the signature; dead implicit return blocks are omitted.
- Expressions contain a closed operation tag, logical type and checked
  operands. Literal values are bounded decimal integers; variable references
  carry local IDs and currently require zero offsets. Calls carry resolved
  function identities, a separate receiver expression (or null) and ordered
  explicit arguments. No raw C or assembly is accepted.

The function contract validates receiver pointer/record shape, owning class
identity and member cv consistency. A constructor's lowered result is its
receiver pointer. DMC represents a destructor with a lowered int placeholder;
this is not a C++ value, and its body can end in a bare return. Ordinary
functions retain their logical result convention. Export uses cpp_thistype
and the function's semantic return type, then releases the temporary receiver
type inside the worker. No allocation ownership crosses the process boundary.

The exporter separates xfunccall's appended receiver from the explicit argument
tree before applying argument ordering. DMC stores explicit member parameters
backwards for tyrevfunc conventions; the exporter reverses that binding list
while preserving expression IDs, leaving the receiver first. The importer
checks types and emits definitions/calls in logical receiver-first order.
Weighted constructor/member fixtures distinguish argument order even when
parameter types are identical.

The current profile implements bool/int/unsigned/long scalar values, pointers
and references to supported carriers, scalar operations, assignments/lvalue
identity, calls, branches, loops and returns. It also implements bounded record
storage, checked field byte addresses, receiver calls, constructors and normal
destructors. General class value parameters/results, dynamic dispatch, lifetime
region markers, mutable cv adjustments, exception exits, switch tables and
unresolved external bodies remain unsupported. The command leaves DMC EH
disabled; a specific throw/catch control requires the -Ae diagnostic and no
TinyCC execution. Wider normative coverage remains part of M2–M4.

The field-address operation has exactly op, type, offset and a one-element
args list. The base must be a pointer to a record and the result a pointer to
a supported non-void type. The importer checks the complete field span,
offset and base alignment, and qualification preservation. It emits byte
arithmetic, not C pointer scaling. Typed indirection must retain pointee cv.
This checks typed layout bounds; full field-declaration identity, mutable
member rules and arbitrary source pointer arithmetic remain future contracts.

Record carriers use hashed names and aligned byte storage, with target compiler
checks for sizeof and alignment. Conflicting layouts for the same record path
are rejected across the entire program. This target-C representation relies
on TinyCC's supported storage/address behavior; it is not a portable C source
interface or a promise of vendor C++ binary compatibility. Constructors return
their lowered receiver; destructors emit void. Validation rejects consuming a
destructor's internal int placeholder, including through nested expressions.
Direct calls recognize the exact *( &function ) destructor wrapper without
enabling arbitrary function-pointer or virtual calls.

Bounds are 256 functions and 8 MiB per worker stream, 1 MiB per line,
1024 variables, 512 blocks and 4096 expression nodes per function, 64 levels
of expression nesting and 256 explicit call arguments. The driver bounds
sources to 32 .cpp inputs, 1 MiB per file and 16 MiB total; aggregate body
streams and generated C are each bounded to 16 MiB. Files are bounded before
JSON parsing; duplicate keys, unknown fields and unsupported forms fail closed.
The object profile bounds each record to 1 MiB and alignment 16, with at most
256 distinct record layouts per program. These are experimental limits.

## Owned importer and compiler command

`tools/semantic_ir.py` validates ownership, IDs, CFG edges, types and supported
operations before generating target C. It uses fixed type/operator spellings
and hashed function names. C++ overload identities remain distinct; internal
functions are scoped to their translation unit. C linkage identities share
their external name across namespace owners. All call bodies must be supplied
in this profile. Public C symbol exports and external-runtime bindings are
not yet qualified.

`tools/compile_worker.py` accepts ordinary .cpp source files and creates a
Windows x64 executable through that path. It accepts zero-argument int main(),
including implicit return zero, or int answer() for development fixtures.
Arguments to main and the full hosted startup/termination contract remain open.
The input .cpp restriction also prevents legacy command parsing from treating
an object/dependency file input as an output destination. Worker object paths
are explicitly confined to the attempt directory.

Example from the repository root, using a recorded local worker build:

```powershell
python tools/compile_worker.py `
  --worker output/dmc-source/20261104-201421-187bd7e3/source/scppn.exe `
  --build-record output/dmc-source/20261104-201421-187bd7e3/results.json `
  --backend output/build/Debug/tinypp_backend.exe `
  --runtime output/build/runtime/Debug `
  -o output/example.exe example.cpp
```

The command retains source/tool/runtime identities, worker streams, owned C,
TinyCC objects, native artifact and diagnostics under output/worker-compilation.
It checks input stability and x64 artifact identity before publication. A
same-directory temporary and exclusive link publish a new output atomically;
an existing output is preserved, including a file created after preflight.
Compilation does not execute the resulting user program.

Quoted includes retain the original source directory search path. Complete
header dependency closure and source-correlated body diagnostics remain open;
current records do not qualify a release build's complete preprocessing inputs.
Templates and the standard library remain with their existing external owner.

`tools/probe_dmc_ir.py` exercises the actual command, then independently runs
positive executables and checks control rejection before TinyCC. Each target
link input is an explicitly named TinyCC ELF64 object, never a DMC object.
`tests/test_semantic_ir.py` supplies boundary failure controls in CTest.

## Executed body pilot evidence, 2026-11-04

All 21 end-to-end command cases pass: 18 executables run natively (17 return
42 and implicit main returns 0), and three unsupported cases fail before
TinyCC starts. The cases cover ordinary main, source/header paths with spaces,
local state, control flow, recursion, overloads, namespaces, ordered and eight
arguments, updates, unsigned values, reference mutation/results, cross-unit
calls and internal-name collisions. Existing-output rejection preserves the
artifact without executing the worker. Three further input controls reject
object files, missing inputs and directory inputs without invoking a compiler.

- Worker build: output/dmc-source/20261104-192235-ed786b6f/results.json.
- Command pipeline: output/dmc-ir/20261104-193429-3006eebb/results.json.
- Input controls: output/worker-driver-controls/
  9dbc74692e664f20b55d0b6be768f8b1/results.json.
- Legacy x64 regressions: output/dmc-x64/20261104-192630-4703bcf2/results.json.
- Legacy Win32 regressions: output/dmc-native/20261104-192630-f15f4c4a/results.json.

The 19 typed-body and 18 signature boundary unit tests pass. The normal tinypp
front end remains operational; this experimental command is a second entry
into the selected worker/importer architecture. Class/lifetime/EH/RTTI body
coverage, strict diagnostics, full header identity, public ABI binding and the
other target emitters remain open. Parent capabilities remain unverified.

An additional `unsupported-lifetime` command control passes in
output/dmc-ir/20261104-194601-b333f8f6/results.json: a local class constructor
and destructor program is rejected before TinyCC and produces no executable.
Inspection of the worker stream finds the constructor's hidden receiver and
lowered pointer result, plus an unsupported lifetime node hiding the destructor
dependency. That worker's stream contains main and the constructor, but not the
destructor body. This is an exporter limitation, not evidence that the source
has no destructor. The roadmap's B1/B2 gates require explicit receiver/result
metadata and complete lifetime dependency discovery before accepting classes.
The subsequent bounded dependency prepass walks unary/binary expression
children independently of supported export operations and queues OPctor's
destructor symbol explicitly. It resolves aliases and uses the existing
function emission queue; no private worker pointers enter the stream. Bounds
remain 64 expression levels and 4096 visited nodes per function. This addresses
the observed dependency omission without accepting unsupported class semantics.

The updated worker and full 22-case suite now pass. The lifetime control checks
the exact main/constructor/destructor identities in the retained stream as well
as rejection before TinyCC. Eighteen native executables and four rejection
controls pass; the older 21-case run above remains historical evidence.

- Worker build: output/dmc-source/20261104-194843-4029351d/results.json.
- Command pipeline: output/dmc-ir/20261104-194934-391d55e1/results.json.
- Optimized/debug x64: output/dmc-x64/20261104-194954-0a85a975/results.json.
- Win32 comparison: output/dmc-native/20261104-194954-6670dff7/results.json.

These results establish the observed destructor dependency and preserve scalar
regressions. They do not establish complete object dependency closure, normal
lifetime lowering, EH/RTTI or any additional target's body emission.

## Receiver-aware v2 milestone, 2026-11-04

The v2 worker build passes all 24 command cases: 19 native executions and five
pre-emission rejection controls. Static class members now have an independent
native fixture. The lifetime and qualified-member controls validate receiver
types, definition parameter bindings, explicit call arguments and lowered
results in retained streams while requiring rejection before TinyCC. The
qualified-member fixture covers const volatile member calls and static calls
in one class; the lifetime fixture retains destructor dependency discovery.

Thirty-three body boundary tests pass, including constructor/destructor result
conventions, missing/invalid receiver metadata, owner and cv mismatches, C++
linkage, distinct cv overload identities, v1 rejection and scalar regressions.
A real retained v1 worker also fails at protocol validation without starting
TinyCC or publishing an executable. The separate signature protocol is unchanged.

- Worker build: output/dmc-source/20261104-195750-61ddce5b/results.json.
- Command pipeline: output/dmc-ir/20261104-195940-92f00815/results.json.
- Optimized/debug x64: output/dmc-x64/20261104-195939-a4a847e1/results.json.
- Win32 comparison: output/dmc-native/20261104-195939-592dc663/results.json.
- Real v1 rejection: output/worker-compilation/
  20261104-200009-94b0b470/results.json.

This is a protocol milestone within B1, not acceptance of classes. Record
identity/layout reconciliation, checked field byte operations, lifetime nodes,
normal cleanup lowering and exceptional control flow remain implementation
work. An internal DMC destructor int placeholder must never be consumed as a
C++ expression value when that lowering is implemented.

## First owned class execution, 2026-11-04

The 30-case command suite passes: 25 native executables (24 return 42 and
implicit main returns 0) and five rejections before TinyCC. New native cases
cover constructor/destructor mutation, two distinct fields, const volatile
members, cross-unit classes, nested cleanup on early return, member cv
overloads and weighted constructor/member arguments. The former lifetime and
qualified-member rejection controls are now positive workloads with retained
stream metadata checks. Forty-three independent body boundary tests pass.

The remaining controls reject class value return ABI, mutable qualification
adjustment, EH-disabled throw/catch, switch and unresolved external calls.
Boundary tests independently reject field overrun, negative/misaligned offsets,
cv removal, record layout conflicts, excess storage, binding type changes and
destructor result consumption. Parent REQ-0015/0016 and their TCs receive partial
evidence only; full lifetime/class capabilities remain unverified.

- Worker build: output/dmc-source/20261104-201421-187bd7e3/results.json.
- Debug pipeline: output/dmc-ir/20261104-201523-223f9b84/results.json.
- Release pipeline: output/dmc-ir/20261104-202007-2fe422b3/results.json.
- Optimized/debug x64: output/dmc-x64/20261104-201523-f4348c14/results.json.
- Win32 comparison: output/dmc-native/20261104-201523-c07c83e9/results.json.
- Canonical checks: output/verification/20261104-201834-dd8c0aa9/results.json.

Both Debug and Release backend/runtime configurations pass the 30-case suite.
The same optimized, assertions-enabled semantic worker supplies both runs;
these labels identify the owned backend/runtime builds, not a claim of target
program optimization coverage. Canonical Debug/Release checks, documentation,
analysis and input stability also pass for the implementation increment.

The source worker still supplies normal cleanup sequencing; exceptional regions
and cleanup state are not modeled by this increment. Complete field metadata,
const-object construction, temporaries, copies, inheritance/virtual behavior,
EH/RTTI, public ABI bindings and the other owned target emitters remain work.
Templates and standard-library implementation retain external ownership.
