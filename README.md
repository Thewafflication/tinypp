# Tiny++

An experimental C++98 compiler core drawing from TinyCC and Digital Mars C++.

**Content type:** Project overview and controlled planning index

**Planning baseline:** Proposed, 2026-10-31.

**Current status:** 2026-11-05. An experimental scalar/object compiler path
executes bounded C++ class workloads on Windows x64. Full C++98 conformance
is not claimed, and no M0–M8 milestone is closed.

## Where we are

The selected architecture is a process-isolated DMC semantic worker feeding
owned, validated typed IR and TinyCC emission. The experimental entry point is
`tools/compile_worker.py`; the existing `tinypp` scalar front end remains a
separate working regression path. Class support currently belongs to the
worker entry point.

| Area | Verified progress | Still open |
| --- | --- | --- |
| Owned Windows x64 path | Scalar control flow, overloads, references, class fields, constructors/destructors, cv member overloads, cross-unit class calls and nested cleanup on early return. | Complete object semantics, class value ABI, public ABI bindings, EH/RTTI, source diagnostics and production-driver migration. |
| Pipeline tests | 30 cases pass with each Debug/Release backend/runtime: 25 native executables and five rejection controls. | Complete normative coverage and independent three-target qualification. |
| Boundary and regression checks | 43 typed-body tests, 18 signature tests and canonical Debug/Release, documentation and analysis checks pass. The matching DMC comparison build passes 50 optimized/debug x64 and eight Win32 cases. | Full harness/CI qualification, debugger coverage and release acceptance. |
| Windows x86 | DMC native comparison probes; exploratory TinyCC cross-backend/runtime build emits ELF32/i386 and PE32, with a C smoke executable returning 42 on Windows. | Connect the shared owned semantic/class path and qualify the target contract, runtime and ABI. |
| Windows ARM64 | Exploratory TinyCC cross-backend/runtime build emits ELF64/AArch64 and an ARM64 PE executable from a C smoke fixture. | Semantic handoff, native execution, ABI/runtime/unwind qualification and the shared C++ slice. |

The x86/ARM64 cross-backend experiments are isolated local feasibility work;
they are not integrated CMake targets or additional supported compiler modes.
ARM64 artifacts have not been executed. Retained evidence and exact limitations
are recorded in the [handoff contract](docs/architecture/semantic-handoff.md)
and [roadmap](docs/ROADMAP.md).

Next: establish the shared target contract and connect x86 early, complete
field/lifetime semantics and the x64 EH/RTTI slice, then bring that same slice
to ARM64. Strict C++98 diagnostics, final ISO/IEC 14882:1998 reconciliation,
explicit defect decisions and external-project integration remain required.
Templates and the standard library retain their existing external ownership.

## Controlled project records

- [Research and primary sources](docs/research/standards.md).
- [Useful DMC assets and project boundary](docs/research/dmc-reuse.md).
- [WSP adoption and individual dispositions](docs/process/wsp-adoption.md).
- [44 requirements](docs/requirements/README.md).
- [Ten architecture decisions](docs/architecture/README.md).
- [44 controlled test-case specifications](docs/testing/README.md).
- [Verification strategy](docs/testing/STRATEGY.md).
- [Build/use and implementation evidence](docs/process/compiler-foundation.md).
- [Roadmap and milestone exit gates](docs/ROADMAP.md).
- [Bidirectional allocation table](docs/testing/traceability.csv).

The delivery targets are Windows x86, x64 and ARM64, starting with a complete
x64 vertical slice and bringing up the same slice on the other targets early.
Templates and the standard
library belong to an existing separate project. Tiny++ owns compiler-core
implementation, exception handling, RTTI and integration interfaces. A full
hosted C++98 claim applies to the verified combined delivery.
The `dmc` checkout provides runtime/library candidates; the separate
`Compiler` checkout supplies C/C++ compiler source. Its
[reuse assessment](docs/research/compiler-source-assessment.md) precedes any
front-end replacement. The independent scalar prototype remains operational. The selected integration
direction is a process-isolated DMC semantic worker; its experimental
[signature handoff](docs/architecture/semantic-handoff.md) passes x86/x64
probes. An experimental scalar/object body path now runs DMC semantics through
owned IR and TinyCC using tools/compile_worker.py. Bounded class fields,
constructors, normal destructors and cross-unit class calls execute on x64.
General object semantics, EH/RTTI, the other owned target paths and
production-driver migration remain open.

The exact WSP baseline is pinned after tag 1.4.0; adoption records identify the
commit. Dependencies and existing staged submodule additions are preserved.
All requirements and ADRs await normal review. The scalar foundation has an
executable fixture suite and native evidence; parent capability requirements
remain open. Further fixture expansion and milestone verification are planned.

Run the documentation planning check from the repository root:

```powershell
python tools/check-planning.py
```

This checks artifact structure, IDs, links, reciprocal traceability, manifest
coverage and WSP disposition coverage. It supplies no compiler-test or
release-verification verdict. The scalar suite supplies partial runtime
evidence; M1 still needs full harness qualification and CI execution.
The documentation manifest lists the controlled Markdown volume; TeX cases
remain separately controlled and linked. M1 adds the WSP PDF/report pipeline
and render verification before any release-documentation claim.
