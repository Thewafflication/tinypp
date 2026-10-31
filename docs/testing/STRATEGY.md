# Tiny++ verification strategy

**Content type:** Project test strategy

**Status:** Proposed

This strategy applies the pinned WSP test requirements and 29119-aligned
terminology. It remains Proposed. The scalar suite now supplies partial
execution evidence; no parent capability requirement is declared complete.

## Project ownership and release profiles

Templates and the standard library belong to an existing separate project.
TC-0019–0021 and TC-0028–0033 are external-delivery integration cases; they
require producer identity, revision, interface/ABI versions and component
evidence. They do not schedule component implementation in this repository.
Compiler-core releases verify core requirements and disclose their boundary.
Combined hosted conformance additionally requires these external allocations
and local integration acceptance. The missing external project identity is
an M0 integration task, not an assumption about its current progress.

## Levels and oracles

Use unit tests for token/type/lookup services, integration tests for lowering
and runtime contracts, and system tests for driver, separate compilation,
linking, executable behavior and installation. Inspect process artifacts and
analyze standards coverage. The standards lead reviews final-edition anchors
and adopted defect resolutions before a fixture becomes release evidence.

The controlled TC-NNNN.tex files are authoritative. Each fixture variant
records its parent TC, input files and hashes, source anchor, expected
diagnostic or value, allowed-result set, target applicability, invocation
arguments, timeout and cleanup. Fixture IDs append a suffix to the parent TC;
they never replace or reuse controlled TC IDs. Expand capability cases into
clause-level partitions, boundaries and interactions; the initial 44 cases
are not an exhaustive conformance suite.

Positive cases compile/link/run as appropriate. Negative cases isolate one
diagnosable violation; require an actual compiler diagnostic and strict-mode
nonzero status. A crash, missing runtime or linker failure cannot satisfy a
compile-negative oracle. No-diagnostic-required cases are classified
separately. Undefined behavior is excluded from portable result comparisons;
unspecified behavior uses permitted sets. Implementation-defined behavior is
checked against the published target policy. Floating-point tolerances need
a justified oracle. Allowed copy elision must not create false failures.

Pinned GCC/Clang strict C++98 modes and DMC can corroborate supported subsets.
Record versions and flags; adjudicate disagreements against the standard.
Do not require those references to pass export cases they cannot implement.

## Proposed release matrix

| Host / target | Build | Required evidence |
| --- | --- | --- |
| Windows x86-64 / Windows x86-64 | Debug | Native compiler and generated-program execution, symbols and failure backtraces. |
| Windows x86-64 / Windows x86-64 | Release | Native compiler and generated-program execution; install/package checks. |

Pin OS image, host compiler, linker, C runtime and dependency revisions during
M1. All applicable cases run in both configurations unless a reviewed
equivalence analysis identifies an invariant and residual risk. x86 and ARM64
are outside the initial matrix. Future ARM64 claims require native ARM64
execution or explicitly approved emulation, not cross-build-only evidence.

File, redirected pipe and genuine console input are separate cases where
supported. Use actual OS handles and exact bytes; shell object pipelines do
not establish transport fidelity. Include accepting, rejecting and EOF paths
for consequential input decisions. Provision named locales explicitly.

## Harness and evidence contract

A scalar foundation runner and Windows Debug/Release CI workflow now exist.
Local execution supplies partial evidence. Hosted CI execution, harness
qualification and full release-result validation remain M1 work.
Launch child processes using explicit argument vectors, separate stdout and
stderr capture, bounded timeouts and fresh output directories. Compile
cross-unit cases separately; prohibit unity-build shortcuts for export and
linkage tests. Run native test executables on the declared architecture.
Isolate compiler fuzz cases and runtime termination cases in child processes.

Store each run beneath `output/evidence/<run-id>/`, with immutable original
inputs, commands, stdout/stderr, artifacts or digests and execution metadata:
TC/spec revision, requirement IDs, source version/commit, target, build
configuration, host/OS/tool/runtime versions, timestamps, exit status,
controlled final status and evidence locations. Preserve failed records and
link any corrective change and successful rerun. Do not overwrite failures.

Statuses are Pass, Fail, Blocked, Inconclusive, Not run and Not applicable.
Only Pass satisfies a required gate. Missing tools/fixtures are Blocked;
insufficient observations are Inconclusive. A run is Pass only when every
required variant meets its oracle. Retain a rationale for other statuses.

For Debug CI, retain tested binaries, usable debugger symbols, results and
failure output together. Use GDB by default and TinyCC `-gdwarf` where
applicable. On abnormal or failing native runs capture batch backtraces for
all threads without replacing the original result. Any platform substitution
requires explicit WSP tailoring. Provisioning failure must fail clearly.

## Gates and reporting

Planning checks validate IDs, links, normative statements and reciprocal
traceability. M1 adds fixture schema validation, mutation checks and CI that
fails on any required non-Pass result. Generate test reports from controlled
specifications, execution records and build identity, never duplicated manual
procedures. Verify reports fail on missing, duplicate or contradictory input.

At M8, inspect the scope-specific inventory against the exact release
matrix. For a combined hosted claim, inspect the entire normative inventory
including the external project allocations. No unsupported obligation, missing evidence or waiver can establish
full C++98 conformance. Experimental releases may disclose subsets. Ordinary
finite tests support the reviewed claim; they do not prove every possible
program correct.

Verification lead owns harness and result integrity. Standards lead owns
oracles. Release lead retains release evidence and hashes for the supported
release lifetime plus five years; proposed policy requires baseline review.
Use immutable release artifacts or an access-controlled archive with digest
verification. CI must retain evidence on failed runs as well as success.

## Tool compatibility

The pinned WSP Test-Traceability.ps1 discovers `tc-*.c`, although WSP's
published test-case template is TeX. Do not run it against these TeX cases and
accept a vacuous result. The project planning checker validates TeX references.
M1 adapts or wraps the shared tool with format-aware positive and negative
checks and release-result enforcement, without editing the WSP submodule.
