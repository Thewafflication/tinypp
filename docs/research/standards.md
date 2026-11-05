# C++98 standards and dependency research

**Content type:** Research and guidance

**Research date:** 2026-10-31

## Findings and source hierarchy

ISO/IEC 14882:1998 is the requested first-edition target (S1). C++03 and
later editions are separate baselines. Compiler modes may incorporate later
defect resolutions (S7), so edition identity and explicit defect decisions
are necessary.

The public 1997 review document provides historical clause anchors (S2).
It is a draft, not the final authority. The final edition was unavailable in
this repository during research. M0 obtains lawful access, reconciles the
draft and builds the complete normative-obligation inventory before baseline
acceptance. This package contains original requirements, not copied ISO text.

The historical conformance model covers acceptance and correct execution of
well-formed programs within resource limits, and diagnostics for diagnosable
violations. Hosted and freestanding implementations differ in library scope.
Undefined behavior supplies no portable output oracle; unspecified behavior
can permit several results. A nonzero strict-mode rejection policy is an
additional project obligation, beyond ISO's minimum diagnostic rule (S2a).

Exported templates support use where the definition is absent from the
consumer translation unit (S2b). Recognizing or ignoring `export` is
insufficient. DMC documents incomplete C++98 conformance, including missing
export (S6). GCC also identifies export as an exception (S7). Neither is a
universal oracle for this project.

Hosted completion includes language support, diagnostics, utilities, strings,
localization, containers, iterators, algorithms, numerics and I/O, together
with required C interfaces (S2c). Deprecated C++98 facilities remain in scope,
including `auto_ptr`, `strstream` and dynamic exception specifications.

Core and library issues span multiple editions and change over time (S3, S4).
The empty initial defect ledger adopts no resolutions implicitly. Each
adoption needs an issue ID, pinned resolution, applicability, impact and tests.

## Primary source register

| ID | Source | Use and limitation |
| --- | --- | --- |
| S1 | [ISO catalogue](https://www.iso.org/standard/25845.html) | Edition identity; not full normative text. |
| S2 | [1997 public review](https://www.open-std.org/jtc1/sc22/open/n2356/) | Clause navigation; reconcile against final edition. |
| S2a | [General](https://www.open-std.org/jtc1/sc22/open/n2356/intro.html) | Historical conformance model. |
| S2b | [Templates](https://www.open-std.org/jtc1/sc22/open/n2356/template.html) | Instantiation and export. |
| S2c | [Library](https://www.open-std.org/jtc1/sc22/open/n2356/lib-intro.html) | Hosted library scope. |
| S3 | [Core defects](https://www.open-std.org/jtc1/sc22/wg21/docs/cwg_defects.html) | Snapshot before adoption. |
| S4 | [Library issues](https://cplusplus.github.io/LWG/lwg-active.html) | Follow resolved lists and pin each adopted resolution. |
| S5 | [TinyCC manual](https://bellard.org/tcc/tcc-doc.html) | Older 0.9.27 design context. |
| S6 | [DMC implementation](https://digitalmars.com/ctg/CPP-Language-Implementation.html) | Vendor limitations, not behavioral proof. |
| S7 | [GCC standards](https://gcc.gnu.org/onlinedocs/gcc/Standards.html) | Modes and known limitations. |
| S8 | [DMC repository](https://github.com/DigitalMars/dmc) | Distribution identity; local pinned notices govern reuse. |

## Repository evidence

| Component | Pinned revision | Observed assets and candidate use |
| --- | --- | --- |
| TinyCC | `724954021b29e2d5d1d26b67d45228907dc506b7` | tccpp.c, tccgen.c, tccpe.c, x86_64-gen.c, libtcc.c and tests: infrastructure and target-emission candidates. |
| DMC | `9478d25a677f70dbe4fc0ed317cc5a5e5050ef8b` | bin, include, lib, src/core, src/IOS, stlport: runtime/library candidates and comparison behavior. Distribution/runtime checkout; compiler source is separately pinned below. |
| Compiler source | `69824bc4f030a2585feef1c7a9bc423d14e809ca` | DigitalMars/Compiler: C/C++ semantics and backend modules, largely in D; see [assessment](compiler-source-assessment.md). |
| WSP | `5c185eb4a8819c2125182fe9b4424b2c172a69f5` | Process templates and tools; Git description 1.4.0-4-g5c185eb. |

The local TinyCC README lists more modern backends than the older web manual.
Pinned source controls capability assessment. File presence is not evidence
of Tiny++ target support.

TinyCC COPYING contains LGPL 2.1; file headers, RELICENSING and runtime notices
need independent inspection. DMC LICENSE applies Boost terms to files owned
by listed holders; bundled third-party code needs separate review. Compiler
distribution and user-program runtime obligations must be assessed separately.
No dependency or gitlink is modified by this planning work.

## Normative obligation inventory plan

REQ-0002 requires one row per normative obligation: stable obligation ID,
final-edition clause/paragraph and tag, original summary, category, target
applicability, adopted defects, requirement IDs, test and fixture IDs,
implementation unit, disposition, review and evidence references.

Start with clauses 1-16 for language and translation and 17-27 for library
contracts, including exception guarantees and complexity. Inspect all annexes
and incorporated references, retaining normative/informative distinctions.
Annex B quantities are not automatically mandatory minima. Each inventory row
needs an independently reviewed oracle; these initial capability tests do not
establish complete clause coverage.

## Outstanding research

- Standards lead, M0: final-edition access, reconciliation and defect snapshots.
- Dependency lead, M0: front-end availability and per-file reuse rights.
- Backend lead, M1: PE/COFF, EH/unwind and runtime feasibility.
- Technical lead, M1: host implementation language and library selection.
- Project lead, after M1: measured effort forecast and milestone dates.

## Updated project allocation

The user identifies templates and the standard library as work already
started in another project. Hosted scope above describes the complete
combined toolchain, not implementation ownership in this repository. See
[DMC reuse and external integration](dmc-reuse.md) for inspected assets and
the compiler/external-project boundary. Preserve full standards coverage in
the combined inventory while supporting independently completed core scope.

## Implemented numeric research follow-up

The scalar prototype now distinguishes 32-bit signed/unsigned int and long.
The [historical lexical clause](https://www.open-std.org/jtc1/sc22/open/n2356/lex.html)
was consulted for literal candidate ordering, and the
[expression clause](https://www.open-std.org/jtc1/sc22/open/n2356/expr.html)
for arithmetic/conversion context. These remain draft navigation sources;
REQ-0002 final-edition reconciliation is still open. See the compiler
foundation record for implemented scope and retained partial evidence.

## Later working-draft reconciliation

The [WG21 working-paper index](https://www.open-std.org/jtc1/sc22/wg21/docs/wp/)
identifies a November 1997 post-Morristown mailing version, available as
[HTML](https://www.open-std.org/jtc1/sc22/wg21/docs/wp/html/nov97-2/).
This is a later working draft, not the published ISO edition. Its landing
page retains an October title; identify the source by the mailing index and
version path rather than assuming the title establishes its date.

Its [statement clause](https://www.open-std.org/jtc1/sc22/wg21/docs/wp/html/nov97-2/stmt.html)
explicitly permits a void expression in a void function's return statement
and requires evaluation before returning. The older public-review statement
clause lacks that paragraph. The scalar implementation provisionally follows
the later rule. That clause also specifies that discarded expression
statements do not apply lvalue-to-rvalue conversion; lowering preserves
address-evaluation effects without fetching a discarded scalar lvalue.

Its [translation phases](https://www.open-std.org/jtc1/sc22/wg21/docs/wp/html/nov97-2/lex.html)
classify missing final newlines and final backslash-newlines as undefined.
The prototype's implicit final-newline behavior is therefore an explicit
implementation policy probe, separate from standard-based positive cases.
Final-edition checks and explicit defect decisions remain open under M0.
