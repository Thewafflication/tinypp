# WSP adoption record

**Content type:** Project adoption and tailoring record

**Project:** Tiny++ (tinypp)

**WSP baseline:** Immutable commit after release 1.4.0

**Submodule path:** `wsp/`

**Pinned commit:** `5c185eb4a8819c2125182fe9b4424b2c172a69f5`

**Status:** Proposed

**Approval:** Pending normal baseline review; no approval inferred.

## Common baseline and selected profiles

Common requirements management, project lifecycle/process, documentation,
source conventions, commit checks and testing apply to project-owned work.
Select personal process, CLI UX, information for users, Security/DFS, C/C++,
Python, PowerShell, YAML/JSON, Make/CMake when owned, static analysis, native
hardening, Windows version resources, Windows signing/Defender and common
tools for the proposed Windows product. C# and Visual Basic profiles are
proposed Not applicable because no owned source uses those languages.

The CLI UX profile covers discoverable help, diagnostics, output accessibility
and predictable workflows; it does not imply building a graphical IDE.
User-information work covers installation, tutorial, invocation and reference.
Security scope includes source/object/library inputs, include paths, subprocess
launches, output writes and untrusted generated-program execution in tests.
M1 creates the DFS trust-boundary and abuse-case record before implementation
baseline acceptance. Compiler robustness is distinct from making arbitrary
user-generated native programs safe to execute.

Unmodified dependencies remain under provenance and change-control review.
Imported or modified code needs a scoped style/analysis decision; no blanket
exception to WSP is implied. CMake, Make or host implementation language
selection is finalized in M1, with individual dispositions revised accordingly.

## Individual dispositions and tailoring

[wsp-dispositions.csv](wsp-dispositions.csv) contains one row for every
identified normative WSP requirement heading in the pinned baseline. Each row
records source, disposition, rationale, owner, completion condition,
compensating control, approval state and project artifacts. Coverage is
conservative: conditional profile obligations stay Deferred until their
applicability and satisfaction are reviewed; unused-language rows propose
Not applicable. This avoids silently omitting conditional requirements.

Deferred rows mean not yet satisfied, not approved to bypass a release gate.
All non-applicable/deferred approvals remain pending. They do not establish
current WSP compliance. M0 reviews applicability and assigns named owners;
M1 and M8 establish the allocated evidence. Before a release, replace planning
dispositions with inspected Applicable satisfaction records or explicitly
approved tailoring/deferrals. A carried deferral is outside that release's
claims and cannot simultaneously be one of its required gates.

No WSP release-PDF satisfaction, CI operation, signing, security evaluation or
compiler conformance is claimed by this documentation-only planning change.
Template and standard-library implementation are externally allocated to an
existing project. The combined conformance claim retains these obligations;
compiler-only release scope and gates exclude their implementation. Local
interface and integration obligations remain controlled here.

## Tool integration and implementation language

WSP's TeX test template is used for controlled cases. Its current traceability
tool searches C case files; a format-aware project planning checker covers
these TeX artifacts. M1 integrates runtime evidence and CI checks with negative
controls. This compatibility wrapper does not weaken the WSP obligation.

Product C++98 conformance does not determine the compiler implementation
language. M1 selects that language and tools, then controls warnings,
formatting, Doxygen and clang-tidy as applicable. TinyCC as host compiler,
GDB and other defaults require feasibility verification; any substitution
uses explicit impact analysis and approved tailoring.

## Baseline history

| Date | Baseline | Change and review |
| --- | --- | --- |
| 2026-10-31 | Exact commit above, 1.4.0-4-g5c185eb | Initial proposed adoption; acceptance pending. |
