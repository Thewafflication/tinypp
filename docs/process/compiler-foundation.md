# Compiler foundation work record

**Content type:** Implementation and verification record

**Status:** Experimental; M0 and M1 remain open.

## Implemented scope

The project owns a source reader, ASCII tokenizer, bounded parser, scalar
types, lexical bindings, overload selection and typed expression/statement
trees. Lowering is isolated in src/lowering.cpp; parsing and semantic checks
remain in src/frontend.cpp. Shared category queries live in src/ast.cpp and
initial translation phases in src/source.cpp. TinyCC emits the validated lowering and links native Windows x64
executables. Build files and generated runtime artifacts stay outside the
three dependency checkouts.

Current subset:

- Bool, int, long, unsigned int and unsigned long declarations/definitions,
  up to 16 parameters, redeclarations, recursion and separate translation units.
  The current Windows target uses 32-bit int and long.
- Exact-match, bool-to-int promotion and scalar-conversion overload ranking with
  per-argument dominance; ambiguous candidates receive diagnostics.
- Decimal, octal and hexadecimal 32-bit integer literals with U/L suffixes,
  true/false, scalar names and function calls. Literal typing follows the
  C++98 candidate lists rather than the target C compiler default.
- Signed/unsigned usual arithmetic conversions and unsigned modulo arithmetic.
- Unary arithmetic/logical operations, arithmetic, comparisons, bitwise and
  short-circuit operators, alternative tokens and conditional expressions.
- Scoped scalar locals, copy/direct initialization and multiple declarators,
  scalar-lvalue assignment, return,
  blocks, if/else, while, break, continue and empty statements.
- Parenthesized expressions, whitespace and line/block comments.
- Trigraph replacement followed by line splicing, with original physical
  coordinates retained across joined tokens and comments. LF/CRLF input
  normalization precedes lexical analysis.
- Reopened/nested named namespaces, qualified/rooted function names and
  enclosing-namespace lookup with scalar overload sets.
- For and do/while loops with loop-variable scope and continue semantics.
- Explicit C/C++ linkage declarations/blocks and inherited C linkage for a
  later definition; same-symbol C declarations are checked for consistency.
- Non-const scalar lvalue-reference parameters and local aliases, with
  exact-type binding, alias mutation and reference-aware overload viability.
- Assignment and same-type conditional lvalues retain identity and evaluate
  effects once when bound to a reference.
- Prefix/postfix integer and C++98 bool increment, compound assignments, shifts
  and comma sequencing with category/type retention. Bool decrement is rejected.
- Scalar functional, C-style and static casts, including exact non-const
  reference casts. Value casts remain rvalues.
- Const scalar objects and const value parameters with readonly checks; value
  parameter const is ignored in function identity as required.
- Void functions, bare and void-expression returns, discarded-value casts
  and conditional expressions with two void branches.
- Namespace-scope aliases with canonical target identity, alias chains,
  identical redeclarations and qualified/rooted namespace resolution.

Limits: 1 MiB source, ASCII bytes, expression/statement nesting bounded at
128, namespace nesting at 32, 256 distinct function signatures,
4096 statements per function and
Windows narrow paths shorter than MAX_PATH. Operator coverage remains a
subset: pointer/member operators, sizeof, allocation and class casts are not
yet implemented. Unnamed parameters and a sole
void parameter-list marker are supported. Headers, macros, conditional
inclusion and #line are not implemented; those directives receive diagnostics.
The source front end implements initial character/line translation, not the
complete C++98 preprocessor. Files without a final newline receive an implicit
logical newline as an explicit implementation policy.

Templates and the standard library remain external. Classes, const references,
reference return types and the broader pointer/volatile type model,
object lifetime, exceptions, RTTI and the final ABI remain work. Namespace
aliases inside blocks, using declarations/directives, unnamed namespaces and
ADL for class types remain outside the implemented namespace subset.

The C-linkage subset intentionally rejects mixed C/C++ overload sets for a
name; full language-linkage rules remain future work. Language-linkage strings
are restricted to the canonical spellings C and C++. The internal C adapter
uses a scoped target-C statement expression for assignment lvalue identity;
this is generated backend text, not a source-language extension accepted from
the C++ user. Final lowering and ABI review remain open.
None of the parent capability requirements is closed by the scalar suite.

## Build and use

Prerequisites: Windows x64, Visual Studio 2022 C++ tools/SDK, CMake 3.20+ and
Python 3.12+ and PowerShell 7. Doxygen checks require Doxygen separately.
The canonical dispatcher also needs the configured toolset clang-tidy.

Run all local foundation gates with `python tools/verify.py`. Every invocation
retains immutable command logs and source hashes under output/verification.
For individual commands:

```powershell
cmake -S . -B output/build -G "Visual Studio 17 2022" -A x64
cmake --build output/build --config Debug
ctest --test-dir output/build -C Debug --output-on-failure
cmake --build output/build --config Release
ctest --test-dir output/build -C Release --output-on-failure
doxygen Doxyfile
python tools/analyze.py --build output/build
python tools/probe_dmc.py
```

Emit an intermediate object:

```powershell
output/build/Debug/tinypp.exe -std=c++98 -c example.cpp -o example.o
```

Compile and link through the owned driver:

```powershell
output/build/Debug/tinypp.exe --runtime output/build/runtime/Debug `
    example.cpp -o example.exe
```

An existing destination is preserved: choose a new output path. Object files
are ELF64 intermediates consumed by the bundled TinyCC linker, even on Windows.
Executables are PE x64. See ADR-0008 for provisional symbols and carrier types.

## Verification and evidence

`tests/run_foundation.py` defines executable fixture variants associated with
parent TC identifiers. Each run creates a new directory under
`output/build/evidence/<configuration>/`, including exact input bytes,
objects/executables, captured commands/output, per-variant records and a
results.json summary. Source and binary hashes identify uncommitted work
even before this repository has its first commit. Original failures remain.

The suite covers scalar execution, ambiguity and invalid syntax, unsupported
subset boundaries, resource limits, cross-unit calls, paths containing spaces
and output preservation. A passing variant is partial evidence only; valid
C++98 constructs rejected by this prototype remain documented limitations.
The runner is the controlled input generator; parent TeX specifications
remain authoritative. Runtime infrastructure errors are never successful
negative compiler tests.

Local source physical-style and Doxygen checks have passed during development.
The WSP clang-tidy baseline is applied to all owned C++ translation units by
the analysis tool. It selects the configured MSVC headers and uses C++14 to
parse that vendor STL; this is not strict C++98 host portability evidence.
Three narrowly scoped enum-size suppressions retain C++98 enum syntax, which
cannot specify a smaller underlying type. Their rationale is recorded at
each enum; acceptance review is pending with ADR-0008.

WSP's complete analyzer qualification, GDB/backtrace, PDF and release-evidence
gates are not yet satisfied. The current execution history is retained in output;
milestone acceptance requires reviewed evidence, not just this work record.

## Numeric oracle notes

The historical [WG21 integer literal table](https://www.open-std.org/jtc1/sc22/open/n2356/lex.html)
places unsigned long after int/long for unsuffixed decimal literals, while
non-decimal literals can select unsigned int. With 32-bit int and long,
2147483648 therefore selects unsigned long and 0xFFFFFFFF selects unsigned int.
The front end selects and canonicalizes these types before target emission.
The final edition and adopted defect ledger remain the acceptance authority.

## Const and conversion boundary

Const references are rejected at declaration/cast boundaries until temporary
lifetime ownership is implemented. Mixed-const conditional lvalues are also
explicitly rejected pending final-edition/defect reconciliation. Other const
scalar conditional and comma results preserve readonly behavior. The initial
qualifier parser supports leading or trailing const, not every interleaving
of declaration specifiers.

The validation tools compare start/end snapshots of controlled source,
requirements/specifications and dependency revisions/diffs. Changed baselines
cannot yield a successful overall run. Native runs also compare compiler,
backend, DLL and runtime-archive binary identities. Negative controls have
confirmed detection of added and changed controlled inputs, with the original
baseline restored afterwards. This detects observed input changes; it is not
a filesystem lock or a complete build-environment attestation.

## Source-phase evidence

Fixtures cover spliced identifiers/numbers, comment continuation, trigraph
braces/operators, trigraph-created splices, CRLF and the rule that phase-one
trigraph recognition is not repeated after splicing. Error fixtures assert
original physical line/byte columns for joined identifiers and tokens after
three-byte trigraphs. Standard-based positive fixture files end in a newline;
a separate implementation-choice probe covers implicit final-newline handling.

## Driver aggregation and resource bounds

The driver parses each source independently before any target compilation.
Link mode accepts up to 32 source files; compile-only mode accepts one.
Aggregate source and lowered-text limits are 16 MiB each, with at most 1024
signature entries across the input units. Each source remains limited to
1 MiB and 256 signatures. A later source error prevents final publication.

Identifiers are capped at 1024 ASCII bytes, and qualified names/namespace
paths at 4096 bytes. These bounds prevent namespace-prefix expansion from
multiplying a small input into unbounded symbol/lowering storage. Existing
output destinations remain preserved in single- and multi-source modes.

A multi-source invocation uses the same explicit runtime directory:

```powershell
output/build/Debug/tinypp.exe --runtime output/build/runtime/Debug `
    consumer.cpp producer.cpp -o program.exe
```

The shared type/lifetime migration for pointer, class and const-reference
support is recorded in proposed ADR-0009. It does not move template or
standard-library implementation into this project.

## Void functions and statement disambiguation

The scalar front end supports void function declarations and definitions,
bare returns, void-expression returns, void calls and discarded-value casts.
A void-expression return evaluates the expression before emitting a bare
return in target C. Both branches of a conditional expression may be void;
mixed void/value branches are rejected. Void objects, value parameters,
arithmetic operands and controlling expressions are diagnosed.

Syntax-only lookahead distinguishes declarations from functional-cast
expressions without suppressing declaration diagnostics. An ambiguous
`int(n);` is treated as a declaration, while `int(n + 1);` remains an
expression. Development fixtures cover these distinctions and the void
boundaries. They remain partial evidence for their parent capabilities.

The later 1997 working draft explicitly permits void-expression returns;
the older public review text does not contain that paragraph. See the
[standards research](../research/standards.md) for the source hierarchy.
Neither draft replaces final-edition reconciliation.

## Namespace alias boundary

Aliases are bound to the original namespace at their declaration point.
Alias chains store canonical targets directly, so lookup does not recurse
through alias chains or invent additional function identities. Qualified
lookup stops at the nearest visible first namespace component; a missing
nested component cannot fall back to a hidden outer namespace. Reopening an
original namespace exposes its new members through existing aliases.

Each translation unit permits up to 256 named namespaces and 256 distinct
namespace-scope aliases, in addition to the existing nesting/path limits.
Repeated identical alias declarations do not consume another slot. Different
target redeclarations, unknown targets, function/namespace conflicts and
attempts to reopen aliases as original namespaces are diagnosed. Block-scope
aliases remain unsupported. Fixtures include exact count boundaries and
independently compiled producer/consumer units with different alias spellings.

The provisional oracle is the later working draft's
[namespace alias clause](https://www.open-std.org/jtc1/sc22/wg21/docs/wp/html/nov97-2/dcl.html).
Final-edition reconciliation and the remaining lookup partitions are open.
