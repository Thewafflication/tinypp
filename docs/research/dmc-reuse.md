# Useful DMC assets and cross-project ownership

**Content type:** Dependency research and integration guidance

**Status:** Proposed implementation decisions; project boundary supplied by user.

## Project boundary

The standard library and templates belong to an existing separate project.
Tiny++ owns the compiler core and its integration contracts. This repository
does not duplicate that project's library or template implementation work.
The other project's name, repository, interfaces and release revision have
not been supplied; no identity or completion status is inferred.

Template language support (deduction, instantiation, dependent lookup and
export) still needs compiler cooperation. Its implementation ownership stays
with the separate project as instructed; Tiny++ records the token/AST/type,
lookup, instantiation, diagnostic, lowering and linkage interfaces it needs.
M5/M6 are integration gates rather than a second implementation effort.
Library headers, facilities and their internal tests stay with that project;
M7 verifies integration against a pinned delivery from it.

Keep REQ-0019–0021 and REQ-0028–0033 as stable external allocations and their
TCs as integration/acceptance specifications. Record producer revision,
interface/ABI version, owner, upstream evidence and local integration results
before claiming verification. Compiler-only delivery can close its own scope
without those external implementations being complete. A combined hosted
C++98 claim still needs all language and library obligations verified.

## Inspected reuse candidates

Observations refer to DMC commit
`9478d25a677f70dbe4fc0ed317cc5a5e5050ef8b`. These are source candidates,
not a finding that code is portable or licensed for every intended use.

| Asset | Useful material | Owning workstream / caveat |
| --- | --- | --- |
| [src/core/except.cpp](../../dmc/src/core/except.cpp), [EHDATA.CPP](../../dmc/src/core/EHDATA.CPP) and [rtti.cpp](../../dmc/src/core/rtti.cpp) | C++ exception propagation, exception state/allocation hooks and RTTI matching. | Compiler/runtime design reference; legacy frame, segmented-memory and type-encoding assumptions require review. These are more directly relevant to C++ EH than the WIN32 SEH helpers alone. |
| [src/WIN32/EHSUP.C](../../dmc/src/WIN32/EHSUP.C), EHSUP2.C, EHSUP3.C and EHINIT.C | Exception-runtime and initialization implementation to study for compiler/runtime contracts. | Compiler/runtime work; inspect architecture assumptions before adapting. |
| [src/INCLUDE/ehsup.h](../../dmc/src/INCLUDE/ehsup.h) | Concrete compiler/runtime EH data and calling contracts. | Compiler reference. Contains 16/32-bit model logic, ECX this-passing and packed structures; no x64 drop-in assumption. |
| [src/core/_NEW.CPP](../../dmc/src/core/_NEW.CPP) and allocation/deallocation variants | Operator new/delete wrappers and allocation-helper boundaries. | Coordinate runtime ABI with external library owner. This file carries a Northwest Software notice: root-license coverage needs specific review. |
| [src/IOS](../../dmc/src/IOS) | Historical stream, file-buffer and strstream implementation examples. | External standard-library project; evaluate edition and portability before reuse. |
| [stlport/stlport](../../dmc/stlport/stlport) and [stlport/src](../../dmc/stlport/src) | STLport headers and stream implementation candidates. | External project. Bundled README identifies STLport 4.5 and notes a DMC-modified version. |
| [stlport/test/regression](../../dmc/stlport/test/regression) and [stlport/test/eh](../../dmc/stlport/test/eh) | Container/algorithm and exception-safety regression cases. | Useful external-project test seeds and compiler integration workloads; review each oracle and notice. |
| [include](../../dmc/include), [src/core](../../dmc/src/core) and [src/INCLUDE](../../dmc/src/INCLUDE) | C/CRT declarations and runtime implementation patterns. | Coordinate C-runtime boundary; avoid duplicating externally owned facilities. |
| [html/ctg/CPP-Language-Implementation.html](../../dmc/html/ctg/CPP-Language-Implementation.html) | Vendor behavior, implementation choices and documented conformance gaps. | Compiler research/reference; DMC lacks export and is not the normative oracle. |

No reusable C++ compiler parser/semantic front end has been identified in
the checked-out distribution. Runtime source and a compiler executable do
not establish that one is available. Bundled binaries are optional comparison
tools; their ABI and target restrictions require independent checking.

## Executed comparison probe

The checked-in dmc.exe reports **Digital Mars Compiler Version 8.42n**.
Do not infer its version from a repository tag. `tools/probe_dmc.py` has run
ten isolated compile-only probes with `-A -mn -c`: scalar calls, bool
overloads, recursion and scoped loops compiled; undeclared names and an
ambiguous overload were rejected. Additional probes accept void-expression
returns and namespace aliases, and reject void objects and alias retargeting.
Negative probes require the observed diagnostic exit status 1, so a crash
cannot count as an expected rejection. Exact inputs, object hashes, banner and
process results are retained under `output/dmc-comparison/`.

This is optional Windows x86 comparison evidence, not x64 execution evidence
or a conformance result. The source parser/semantic implementation is still
unavailable in this checkout. The probe uses DMC's default output naming in
isolated directories and does not link its objects into Tiny++ artifacts.

## Next integration work

At M0, identify the existing external project's actual repository and owner.
At M1, agree interface versions, ownership of runtime helpers, diagnostics,
instantiation requests, object symbols and evidence exchange. Pin deliveries
before M5–M7 integration runs. Offer the assets above as candidates; this
planning change does not copy files or modify the other project.

## File-level notice inventory

The [initial reuse audit](reuse-audit.csv) records 19 inspected candidate
files, their pinned revisions, exact SHA-256 identities, observed notices,
current use and remaining decisions. It distinguishes files built locally
from DMC reference candidates that have not been copied or compiled.
This is a partial notice inventory, not complete provenance or permission
to distribute the compiler/runtime bundle. Includes, assembly, headers,
import definitions, transitive dependencies and binary tools remain to audit.

The inspected EH support files name Digital Mars, a holder covered by the
root grant. The inspected RTTI and EH shared-data openings do not identify
a holder, so their grant coverage remains unresolved. `_NEW.CPP` names
Northwest Software; a separate written-by credit does not make the root
holder list sufficient. STLport's iostream source has its own SGI/Fomitchev
notice and grant, which the external library project must preserve and review.

TinyCC compiler source headers and the runtime `libtcc1.c` use different
terms. The latter contains an explicit compiled-linking exception. The
RELICENSING contributor list is not treated as a completed blanket change.
Runtime files with no grant in their opening comments remain unresolved;
absence of a file header does not establish permission.
