# Tiny++ compiler-core and integration roadmap

**Content type:** Milestone work plan and guidance

**Status:** Proposed

**Planned period:** Dependency ordered; dates set after M1 measurements.

**Inherited baseline:** Existing TinyCC, DMC and WSP gitlinks recorded in
[research](research/standards.md). The initial baseline had no implementation;
[scalar foundation work](process/compiler-foundation.md) now supplies partial
feasibility evidence. No milestone is declared closed.

**Owner:** Project lead (person assignment pending baseline review).

**Approval:** Pending normal project review; no release approval implied.

## Objective and boundary

Deliver the compiler core and integration contracts for a C++98 toolchain,
drawing from audited TinyCC and DMC assets. Templates and the standard
library are owned by an existing separate project; see
[project boundary and useful DMC assets](research/dmc-reuse.md). Proposed first completion target: Windows x86-64, native execution,
Debug and Release. Compiler-project completion covers the core scope; full
hosted conformance is a combined-delivery claim requiring the external
templates and library plus successful integration evidence. Each intermediate milestone is an experimental
subset with published gaps. Additional architectures follow a separate port
roadmap; omitting them does not weaken the initial target's language scope.

## Work packages and required exit gates

| ID | Deliverables and responsible role | Entry dependency | Required exit evidence |
| --- | --- | --- | --- |
| M0 — Baseline and feasibility inventory | Standards lead: final-edition obligation inventory and defect decisions. Dependency lead: per-file provenance and source-availability audit. Project lead: adoption dispositions and ADR review. | This planning package | Final-text/draft reconciliation reviewed; no unresolved scope or reuse assumption in the accepted baseline. REQ-0001–0003 and REQ-0035 reviewed successfully. |
| M1 — Toolchain foundation | Backend lead: native artifact path, typed lowering contract and scalar prototype. Runtime lead: EH/unwind spike and external-project ABI/interface agreement. Verification lead: fixture format, runner, evidence validator, CI and document build. | M0 | Native x64 compile/link/run, extern C boundary, cleanup/unwind spike and debugger symbols demonstrated; build identity and fail-closed evidence/traceability checks pass. REQ-0026–0027, REQ-0038–0040, REQ-0044. |
| M2 — Translation layer | Front-end lead: source manager, lexer, C++ preprocessor adapter and strict-mode driver. Security lead: bounded malformed-input testing. | M1 adapter feasibility | Reviewed translation-phase fixtures, macro rescanning, lexical forms, edition macro, limits register and malformed-input containment pass. REQ-0004–0005, REQ-0008–0009, REQ-0034, REQ-0037. |
| M3 — Core semantics | Front-end lead: declarations/types, scopes, lookup, expressions, statements and overload resolution. | M2 | Positive and diagnosable-negative partitions pass; required diagnostics and strict exit policy verified. REQ-0006–0007, REQ-0010–0014. |
| M4 — Object model and runtime | Runtime/backend leads: lifetime, layout, inheritance, virtual dispatch, allocation, EH, exception specifications, RTTI, startup and linkage. | M3; M1 unwind proof | Cross-unit lifetime, multiple/virtual inheritance, adjusted calls, unwind cleanup, unexpected/terminate and RTTI probes pass. ABI revision published. REQ-0015–0018, REQ-0022–0025. |
| M5 — Template integration | External project owns template implementation; Tiny++ front-end lead supplies type/lookup/instantiation interfaces and acceptance tests. | M3; M4; pinned external delivery | Agreed interface and external evidence reviewed; local definition/instantiation and specialization probes pass. REQ-0019–0020 remain external allocations. |
| M6 — Export integration | External project owns export implementation/repository; Tiny++ supplies emission/linkage and invalidation interfaces. | M5; M4; external export delivery | Declaration-only consumer, separate compilation and invalidation checks pass. REQ-0021 is required for combined conformance, not core-only completion. |
| M7 — Standard-library integration | Existing external project owns library implementation and component coverage; Tiny++ owns ABI/runtime boundary and acceptance workloads. | M4; M5; pinned external library delivery | Producer evidence and local compile/link/run tests agree on ABI/runtime versions. REQ-0028–0033 remain external allocations; no duplicate library implementation. |
| M8 — Scoped release and combined claim | Verification lead: complete clause/matrix evidence and independent oracle review. Release lead: packages, licensing, user documentation, security and WSP release records. | M0–M4 core closure; M5–M7 only for combined claim | REQ-0036, REQ-0041–0043 pass; complete obligation inventory has no unsupported applicable normative item; all required target/configuration results Pass; release review and artifact identity retained. |

M0–M4 and core release verification define compiler-only completion. M5–M7
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
| No DMC front-end source | Significant new compiler work | Dependency lead confirms M0; front-end lead estimates an independent front end. |
| TinyCC emission cannot represent EH/layout needs | Adapter redesign or backend replacement | Backend lead proves scalar and unwind contracts M1; revise ADR before continuing. |
| DMC source assumes 32-bit or incompatible runtime ABI | Port or replace components | Runtime lead audits and measures M1 prototypes. |
| External template/export interface or delivery changes | Combined-delivery delay | Integration lead pins versions and preserves core-only scope; M5/M6 verify contracts. |
| Draft/final or defect disagreement | Wrong acceptance or oracle | Standards lead resolves against final edition and pinned ledger. |
| Legacy library gaps or license uncertainty | Replacement work or distribution block | Library/dependency leads maintain per-component decisions. |
| Fuzzing/reference consensus mistaken for conformance | Unsupported claims | Verification lead requires clause allocation and reviewed oracles. |

## Estimate and replanning

No staffing, productivity or effort history is available, so calendar dates
and numerical effort estimates would be invented. M1 records actual effort,
defects, adapter changes and prototype throughput. The project lead then
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
| Windows x86 and ARM64 ports | Backend lead | Separate target ADR and native verification matrix | Outside first target scope; no support claim | Proposed scope decision |
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
