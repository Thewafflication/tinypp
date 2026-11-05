# Tiny++ compiler-core and integration roadmap

**Content type:** Milestone work plan and guidance

**Status:** Proposed

**Updated:** 2026-11-05.

**Planned period:** Dependency ordered; dates set after integration and target
feasibility measurements.

**Inherited baseline:** Existing TinyCC, DMC and WSP gitlinks recorded in
[research](research/standards.md). The initial baseline had no implementation;
[scalar foundation work](process/compiler-foundation.md) now supplies partial
feasibility evidence. No milestone is declared closed.

**Owner:** Project lead (person assignment pending baseline review).

**Approval:** Pending normal project review; no release approval implied.

## Objective and boundary

Deliver the compiler core and integration contracts for a C++98 toolchain
on Windows x86 (32-bit), x64 and ARM64, drawing from audited TinyCC and DMC
assets. Use x64 for the first complete vertical slice, then exercise that same
slice on x86 and ARM64 before broadening language coverage. All three targets
are required for planned compiler-project completion; x64-only evidence does
not close the three-target delivery.

Templates and the standard library remain owned by the existing separate
project; see [project boundary and useful DMC assets](research/dmc-reuse.md).
Tiny++ owns compiler semantics, target adapters, EH/RTTI runtime and integration
contracts. Core-only releases identify their scope. Full hosted conformance
requires the combined delivery and external-project integration evidence.
Every intermediate build remains an experimental subset with published gaps.

The standards baseline is ISO/IEC 14882:1998. Reconcile the obligation inventory
against the final published edition, record draft differences, and explicitly
accept or reject each applicable later defect resolution with rationale and
oracle impact. Later standards and existing compiler behavior do not silently
change this baseline. See the [source register](research/standards.md) and
[WG21 standards register](https://www.open-std.org/jtc1/sc22/wg21/docs/standards).

## Execution priorities and decision gates

These priorities order implementation inside the existing M0–M8 allocations;
they do not renumber requirements or imply that a milestone has passed.
Standards reconciliation and provenance review proceed alongside feasibility,
and must close before baseline acceptance or a conformance claim.

| Order | Work and owner | Required result before proceeding |
| --- | --- | --- |
| 1 — Resolve DMC integration | Front-end and dependency leads compare full front-end adoption, selected semantic extraction and continued independent implementation under ADR-0010. | Record a selected boundary with measured build/extraction cost, dependency closure, file-level provenance, ownership/allocation and error contracts, external-template interfaces and migration regressions. Resolve how semantics reach TinyCC or another emitter; source presence and passing isolated probes are insufficient. |
| 2 — Complete the x64 vertical slice | Front-end, backend and runtime leads implement one end-to-end workload through the selected production path. | Separate translation units compile/link/run with classes, constructors/destructors, cross-unit calls, throw/catch, unwinding and RTTI. Verify cleanup order, partially constructed objects, handler matching, rethrow and dynamic_cast/typeid behavior, with retained negative controls and source-level debug evidence. |
| 3 — Separate target properties | Backend/runtime leads define a versioned target contract and remove target assumptions from semantic analysis. | Explicit sizes/alignment, data layout, argument/return classification, mangling/object ABI, object format, relocations, stack/unwind and runtime conventions; fixtures exercise both scalar and nontrivial objects. Language rules stay shared; target-dependent language properties are queried through the contract. |
| 4 — Bring up x86 and ARM64 early | Backend/runtime and verification leads port the same vertical slice before expanding language coverage. | Native execution on each target in Debug and Release, including C boundaries, cross-unit class calls, cleanup, EH and RTTI. Cross-compilation or emulator-only output is partial evidence; acquire native runners early. |
| 5 — Complete and qualify | Front-end and integration leads complete language coverage and consume pinned external template/library deliveries; verification/release leads qualify all targets. | Clause-level positive/negative coverage, external integration, robustness, debugger and packaging evidence pass for x86/x64/ARM64. Complete M0–M8 exit gates for the claimed scope. |

The target contract may be drafted during the x64 slice; priority 3 freezes
its tested boundary before port work relies on it. The slice uses only the
language subset needed to expose architecture/runtime risks, rather than
waiting for all M2–M4 features. It does not close M4 by itself.

## Target delivery tracks

| Track | Existing evidence | Remaining entry-to-completion work |
| --- | --- | --- |
| Windows x64 | Tiny++ scalar path and experimental owned class path with constructors, normal cleanup and cross-unit calls; adapted DMC comparison probes include optimized/debug emission. | Complete the class/EH/RTTI slice, nontrivial value ABI, public linkage, debug types and full qualification through the owned path. |
| Windows x86 | Isolated DMC source build and bounded native Win32 probes. An exploratory TinyCC cross-backend/runtime build emits ELF32/i386 and PE32; its C smoke program executes on Windows and returns 42. | Integrate the backend and connect the shared owned semantic/class path through a target contract; qualify calling conventions, layout, runtime, unwind/debug conventions and the shared slice. |
| Windows ARM64 | An exploratory TinyCC cross-backend/runtime build emits ELF64/AArch64 and an ARM64 PE executable from a C smoke fixture; no native execution or owned C++ body qualification. | Integrate the target adapter/runtime and semantic handoff, validate ABI behavior, implement C++ unwind integration and execute the shared slice on a native ARM64 runner. Existing unwind emission does not establish C++ EH. |

Initial orchestration may cross-compile from a Windows x64 host. Target support
does not by itself promise a native compiler host on each architecture.
Keep host and target identities separate in build records. The qualification
matrix covers three targets by Debug/Release, plus each supported runtime/ABI
variant; retain independent artifacts and results for every cell. Vendor C++
binary compatibility remains a separate objective from project ABI and extern C
interoperability.

## Work packages and required exit gates

| ID | Deliverables and responsible role | Entry dependency | Required exit evidence |
| --- | --- | --- | --- |
| M0 — Baseline and feasibility inventory | Standards lead: final-edition obligation inventory and defect decisions. Dependency lead: per-file provenance and source-availability audit. Project lead: adoption dispositions and ADR review. | This planning package | Final-text/draft reconciliation reviewed; no unresolved scope or reuse assumption in the accepted baseline. REQ-0001–0003 and REQ-0035 reviewed successfully. |
| M1 — Integration and target foundation | Front-end/dependency leads select the DMC integration boundary. Backend/runtime leads complete the x64 vertical slice, publish the shared target contract and bring up that slice on x86/ARM64. Verification lead supplies native runners, fixture/evidence validation, CI and document build. | M0 inventory available; exploratory work may precede final baseline acceptance | Selected integration decision and production-path slice pass on all three targets, including C boundaries, cross-unit classes, EH/RTTI and debugger symbols; build identity and fail-closed evidence/traceability checks pass. REQ-0026–0027, REQ-0038–0040, REQ-0044. |
| M2 — Translation layer | Front-end lead: source manager, lexer, C++ preprocessor adapter and strict-mode driver. Security lead: bounded malformed-input testing. | M1 adapter feasibility | Reviewed translation-phase fixtures, macro rescanning, lexical forms, edition macro, limits register and malformed-input containment pass. REQ-0004–0005, REQ-0008–0009, REQ-0034, REQ-0037. |
| M3 — Core semantics | Front-end lead: declarations/types, scopes, lookup, expressions, statements and overload resolution. | M2; M1 integration boundary | Positive and diagnosable-negative partitions pass; required diagnostics and strict exit policy verified. REQ-0006–0007, REQ-0010–0014. |
| M4 — Object model and runtime | Runtime/backend leads: lifetime, layout, inheritance, virtual dispatch, allocation, EH, exception specifications, RTTI, startup and linkage. | M3; M1 three-target slice and target contract | Cross-unit lifetime, multiple/virtual inheritance, adjusted calls, unwind cleanup, unexpected/terminate and RTTI probes pass. ABI revision and complete runtime behavior qualified on all three targets. REQ-0015–0018, REQ-0022–0025. |
| M5 — Template integration | External project owns template implementation; Tiny++ front-end lead supplies type/lookup/instantiation interfaces and acceptance tests. | M3; M4; pinned external delivery | Agreed interface and external evidence reviewed; local definition/instantiation and specialization probes pass. REQ-0019–0020 remain external allocations. |
| M6 — Export integration | External project owns export implementation/repository; Tiny++ supplies emission/linkage and invalidation interfaces. | M5; M4; external export delivery | Declaration-only consumer, separate compilation and invalidation checks pass. REQ-0021 is required for combined conformance, not core-only completion. |
| M7 — Standard-library integration | Existing external project owns library implementation and component coverage; Tiny++ owns ABI/runtime boundary and acceptance workloads. | M4; M5; pinned external library delivery | Producer evidence and local compile/link/run tests agree on ABI/runtime versions. REQ-0028–0033 remain external allocations; no duplicate library implementation. |
| M8 — Scoped release and combined claim | Verification lead: complete clause/matrix evidence and independent oracle review. Release lead: packages, licensing, user documentation, security and WSP release records. | M0–M4 core closure; M5–M7 only for combined claim | REQ-0036, REQ-0041–0043 pass; complete obligation inventory has no unsupported applicable normative item; all x86/x64/ARM64 Debug/Release and supported ABI/runtime results Pass; release review and artifact identity retained. |

M0–M4 on all three targets and core release verification define compiler-only
completion. M5–M7
consume work from the existing external project and verify integration; they
do not schedule a second implementation. M8 can publish a compiler-core
release with explicit scope. A full hosted claim additionally requires
M5–M7 evidence. External incompleteness does not block core-only completion.

## Requirement and verification allocation

The [requirements index](requirements/README.md) and
[traceability table](testing/traceability.csv) allocate every requirement
and controlled TC to a milestone and owner. Core requirements are compiler
exit gates. The nine externally allocated requirements are integration gates
for combined delivery, not local implementation gates. A capability TC must be expanded to the
normative inventory's fixture variants before it can support full coverage.

M0 closes the planning baseline only after acceptance review. None of the
product or process requirements is reported fully verified by the planning
package. Scalar implementation variants provide partial evidence separately.

## Roles and review

| Role | Responsibility | Review condition |
| --- | --- | --- |
| Project lead | Scope, assignment, forecast, change control and acceptance | Assign named people before M0 closure. |
| Standards lead | Final-text inventory, defect applicability and oracles | A second reviewer checks oracle-sensitive cases. |
| Front-end/backend/runtime/library leads | Design and implementation ownership | Record interface and security reviews before integration. |
| Verification lead | Fixtures, evidence, traceability and matrix coverage | Review implementation-independent oracles. |
| Dependency/security leads | Reuse rights, trust boundaries and robustness | Resolve unknown provenance before import. |
| Release lead | Packaging, retention, support and approval record | No full claim with missing required evidence. |

One person may fill several roles. When independent review is unavailable,
record the limitation and the approved compensating review before accepting
evidence; do not manufacture reviewer identity.

## Risks and responses

| Risk / trigger | Impact | Control and owner |
| --- | --- | --- |
| DMC compiler source has D/legacy-build/backend coupling | Adaptation may exceed selective implementation effort | Dependency/front-end leads assess the separately pinned Compiler source under ADR-0010 before selecting reuse scope. |
| TinyCC emission cannot represent EH/layout needs | Adapter redesign or backend replacement | Backend lead proves scalar and unwind contracts M1; revise ADR before continuing. |
| DMC source assumes 32-bit or incompatible runtime ABI | Port or replace components | Runtime lead audits and measures M1 prototypes. |
| External template/export interface or delivery changes | Combined-delivery delay | Integration lead pins versions and preserves core-only scope; M5/M6 verify contracts. |
| Draft/final or defect disagreement | Wrong acceptance or oracle | Standards lead resolves against final edition and pinned ledger. |
| Legacy library gaps or license uncertainty | Replacement work or distribution block | Library/dependency leads maintain per-component decisions. |
| Fuzzing/reference consensus mistaken for conformance | Unsupported claims | Verification lead requires clause allocation and reviewed oracles. |

## Estimate and replanning

No staffing, productivity or effort history is available, so calendar dates
and numerical effort estimates would be invented. M1 records actual effort,
defects, integration/adapter changes and prototype throughput by target.
Forecast the shared semantics work separately from each target port/runtime
and the external integration work. The project lead then
forecasts remaining work by semantic subsystem and fixture count, including
external interface/delivery uncertainty and available reviewer capacity.

Replan immediately on failed feasibility gates, unavailable source, a changed
target/ABI, missing normative text, or an increase in baseline obligations.
Dates and budgets never waive a required exit gate.

## Execution, evidence and recovery

Use the [test strategy](testing/STRATEGY.md). Preserve each failure before a
rerun. Record review, design, build and test revisions in milestone closeout
records based on the WSP templates. Work in reviewable component changes;
retain upstream revisions and isolate adapters so an unsuccessful spike can
be reverted without modifying dependency history or deleting evidence.

## Deferred objectives

| Objective | Owner | Completion condition | Impact and control | Approval |
| --- | --- | --- | --- | --- |
| Vendor C++ ABI compatibility | Technical lead | Dedicated compatibility requirements and tests | Only documented project ABI and extern C boundary claimed | Proposed scope decision |
| Optimization/performance goals | Project lead | Measured baseline and approved numerical requirements | Semantic correctness first; no speed promise | Proposed scope decision |

These are scope proposals, not approved WSP deferrals. Exceptions and RTTI
remain compiler scope. Templates and hosted libraries are external project
allocations, not waived standards obligations; combined claims need their
evidence, while compiler-core release gates exclude their implementation.

## Change control

Changes to accepted requirements require impact analysis across dependent
requirements, ABI, runtime, library, targets, fixtures and existing evidence.
Use a new ADR to supersede an accepted architectural decision. Milestone
closure identifies exact commits, gate results, incidents, residual risks and
approval. Release records close or explicitly carry approved deferrals
without reporting them as satisfied.

## Compiler-source feasibility update

The added DigitalMars/Compiler submodule changes M0's source-availability
finding. M0 now reviews its file-level grants and transitive dependencies;
M1 reproduces an isolated Win32 source build and measures extraction/adaptation
before selecting a front-end strategy. See
[ADR-0010](architecture/ADR-0010.md) and the
[source assessment](research/compiler-source-assessment.md).
Neither source presence nor the upstream workflow closes these gates.
The existing scalar path stays available for regression and comparison.

The isolated adapted DMC source build and initial Win32 comparisons now pass.
The adapted x64 COFF spike passes 44 bounded C ABI partitions with and
without optimization. POD parameter/copy/return adaptations are tested;
a guarded COFF publication fix also passes these partitions without -Nc.
Assertions-enabled optimized/debug probes pass, while aggregate debug fields
and general ABI/EH gates remain open. These observations do not select a
production backend or close the three-target foundation. The next work is the selected semantic handoff and the shared vertical slice.

The next object-slice experiments expand the adapted DMC x64 suite to 50
passing cases, unoptimized and optimized/debug with assertions enabled.
Cross-unit constructor/destructor order, adjusted virtual calls and
nontrivial class value copies now have bounded native evidence. The ES
register-mask and explicit local alignment defects have guarded adaptations.
Four optional EH/RTTI probes still fail at runtime linkage. Production
integration and the complete three-target vertical slice remain open.
Configured semantic import measurements and shared-state observations now
inform DM-03; they are not a symbol-level extraction closure.

The integration direction is now a process-isolated DMC semantic worker feeding
owned typed IR and TinyCC target adapters, as proposed in ADR-0010. Its first
copied-signature protocol passes nine cases on x86 and x64, plus 18 consumer
controls. The scalar body pilot below now connects the worker to owned
validation/lowering and TinyCC emission; it supplements the original compiler
entry point. Next extend that handoff to object and lifetime semantics.
Retain the three-target slice, runtime, external-project, provenance
and final-edition gates before declaring M1 or combined conformance complete.

## Typed body milestone update, 2026-11-04

The semantic worker now hands scalar typed CFG bodies to owned validation and
lowering, followed by TinyCC compile/link/run. The experimental compiler command
supports zero-argument main, scalar control flow, resolved overloads, references
and cross-unit calls. Semantic-only mode bypasses native function emission;
DMC object artifacts never enter the target link. Existing outputs are preserved.

The next body milestones are explicit object layout/field operations and
normal lifetime regions, followed by exceptional cleanup, matching and RTTI.
Extend the target contract and bring the same body slice to x86/ARM64; their
signature metadata probes do not qualify body emission. Header closure,
source diagnostics, strict C++98 selection, final-edition reconciliation and
external template/library integration remain required. No full milestone or
combined conformance claim follows from the scalar body pilot.

## Next implementation gates

Execute these gates in order on the selected worker/importer path. DMC native
comparison results inform the work but cannot satisfy an owned-path gate.
Each gate retains source/tool identities, positive native results and negative
controls under REQ-0044; its tests supplement the allocated parent TCs.

| Gate | Implementation and acceptance workload | Completion evidence |
| --- | --- | --- |
| B1 — Object protocol | Version the body contract for record identity/layout, member byte offsets, implicit receiver binding and lowered constructor/destructor signatures. Preserve the distinction between logical C++ results and ABI results. | Importer rejects conflicting layouts, invalid offsets, receiver mismatches and unsupported versions before emission. A constructor writing two distinct fields produces the expected native values. |
| B2 — Normal lifetime | Export lifetime regions and their complete callee dependencies. Implement constructor calls, normal destructor calls, nested scopes, early return and temporary cleanup. | Same-unit and cross-unit fixtures verify construction/destruction order, exactly-once cleanup and reference/member mutation. Retain unsupported exceptional-flow controls until B4 passes. |
| B3 — Shared target contract | Query sizes, alignment, byte-address operations, argument/return classification and runtime/object identities through a versioned target interface. | Paired x86/x64 layout and nontrivial-call fixtures distinguish target facts from language rules. Build an ARM64 object/link smoke test and identify a native runner before further language expansion. |
| B4 — Exceptions and RTTI | Supply the selected ABI's runtime, handler matching, unwind tables, partial-construction cleanup, rethrow, exception specifications and RTTI descriptors. | Owned-path cross-unit throw/catch, nested cleanup, failed construction, dynamic_cast and typeid workloads pass with source-level debugging. No unresolved runtime stubs or native DMC objects enter the target link. |
| B5 — Three-target slice | Run B1–B4's identical semantic workloads through each target adapter. | Native x86/x64/ARM64 Debug and Release execution, independent target identities, ABI controls and unwind/debug evidence. Cross-compilation alone leaves this gate open. |
| B6 — Coverage and integration | Complete the remaining core obligation inventory, strict C++98 diagnostics, preprocessing identity and external template/library interfaces. | Final ISO/IEC 14882:1998 reconciliation, explicit defect decisions, normative positive/negative tests and pinned external integration pass before the applicable M0–M8 gates close. |

The first B2 inspection found a concrete exporter dependency gap: the lifetime
node hid a destructor reference from the scalar traversal. A bounded semantic
dependency prepass now discovers that destructor, including beneath unsupported
nodes; the 22-case command suite verifies its presence while retaining class
rejection. Constructor calls also carry an implicit receiver
absent from the logical parameter list and return a lowered object pointer.
At that stage the scalar importer rejected the input. The later bounded class
increment below replaces that rejection with native normal-lifetime evidence;
accepting record carriers alone was insufficient. Byte-address operations are
now explicit because DMC has already scaled field offsets; ordinary C pointer
addition would scale twice.

These are implementation gates within M1/M3/M4, not additional requirements or
claims of completed capabilities. Templates and library implementation retain
their external allocation throughout B1–B6.

The receiver-aware body protocol v2 separates logical and lowered results,
distinguishes receivers from explicit arguments, and retains distinct member
cv overload identities. Its initial 24-case suite
passed with class/lifetime rejection and 33 independent boundary tests.

The owned class increment now passes 30 command cases, including 25 native
executables and five pre-emission controls, plus 43 independent boundary tests.
The command suite passes with both Debug and Release backend/runtime builds.
Aligned record carriers, bounded field byte addressing, receiver binding,
constructor/normal-destructor calls, cross-unit classes, cv overloads and nested
cleanup on early return now execute through TinyCC. A weighted member fixture
guards the discovered reversed DMC parameter-storage convention. Destructor
placeholder results cannot be consumed as C++ values.

B1/B2 remain open for complete field declaration/type identity, const-object
construction, temporary/copy lifetime coverage and explicit lifetime regions.
B3–B5 still require a shared target contract, EH/RTTI and owned x86/ARM64 paths.
The bounded normal-cleanup evidence does not close the complete vertical slice.
The [handoff evidence](architecture/semantic-handoff.md) records exact builds
and scope.

## Current checkpoint, 2026-11-05

The selected worker/importer architecture now executes the bounded x64 object
slice through owned IR and TinyCC. Thirty pipeline cases pass independently
with Debug and Release backend/runtime builds: 25 native executables and five
rejection controls per configuration. Forty-three body and 18 signature
boundary tests pass. The matching source-built DMC comparison compiler passes
50 optimized/debug x64 cases and eight Win32 cases. Canonical Debug/Release,
documentation, analysis and input-stability gates pass. These results are
partial requirement evidence; all M0–M8 acceptance gates remain open.

The latest target experiment built x64-hosted TinyCC backends and support
runtimes for both x86 and ARM64, without modifying upstream checkouts. The x86
C fixture emits ELF32 machine 3 and PE machine 0x014c/optional magic 0x010b,
then executes with exit 42. The ARM64 C fixture emits ELF64 machine 183 and PE
machine 0xaa64/optional magic 0x020b. Compile-time fixture checks require the
expected pointer width and 32-bit long. ARM64 execution was not attempted.

This exploratory build lives under output/target-backend-preflight/
4745bb561f5c41acb6db6ef3a5674e18, including its isolated CMake inputs, build log,
runtime and smoke artifacts. It has not yet become a controlled backend target,
a complete ABI validation or an owned C++ semantic port. Local output artifacts
are ignored by Git and are not included in the source commit; the versioned
build/probe tools and the handoff document record the reproducible x64 path.

The next reviewable implementation work is:

1. Implement a versioned target contract consumed by validation, lowering and
   artifact inspection; distinguish target data/layout from host properties.
   Integrate the exploratory x86 backend and run the existing class workloads
   through the owned worker path before broad language expansion.
2. Finish B1/B2 field declaration identity, const-object construction,
   temporaries/copies and explicit lifetime-region handling, retaining the
   normal-cleanup and malformed-layout controls already passing.
3. Supply and qualify x64 EH/RTTI through the owned path, including partial
   construction, rethrow, matching and source-level debugging. An EH-disabled
   rejection or a legacy DMC runtime result cannot close this gate.
4. Connect ARM64 semantics to the target adapter and acquire a native runner;
   run the shared slice in both configurations on all three targets.
5. Complete strict C++98 coverage and final-edition/defect decisions, consume
   the pinned external template/library deliveries, and close the applicable
   M0–M8 qualification and release gates.

Templates and standard-library implementation remain with the existing
external project. This checkpoint does not duplicate that work or change the
ISO/IEC 14882:1998 baseline.
