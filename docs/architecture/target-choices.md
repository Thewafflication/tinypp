# Experimental Windows x64 scalar choices

**Content type:** Partial implementation-choice and interface record

**Status:** Experimental; final ABI and obligation inventory remain open.

These choices describe the scalar prototype and its TinyCC target adapter.
They do not replace the complete implementation-defined behavior inventory
required by REQ-0034. The hosted library and templates remain external.

| Topic | Current choice | Evidence / boundary |
| --- | --- | --- |
| Host/target | Windows x86-64 native | PE machine and native execution checked by the foundation suite. |
| Intermediate objects | ELF64 x86-64 | Consumed by TinyCC's linker; no COFF interchange claim. |
| Scalar carriers | int/unsigned int and long/unsigned long are 32-bit target C types | Distinct semantic types/ranks remain in the owned AST; final data-layout review is open. |
| Bool | Values zero or one, held in an int carrier | Prototype ABI only; not a claim about final C++ bool object layout. |
| Non-const references | Target pointers to the matching scalar carrier | Exact-type lvalue binding; const/reference returns are future work. |
| Negative integer division | Quotient truncates toward zero; remainder follows dividend sign | Native probes include -23/4 and -23%4. |
| Negative signed right shift | Arithmetic, sign-extending shift | Native probe includes -8 shifted right by two. |
| Out-of-range unsigned-to-signed conversion | Low 32 bits interpreted in two's-complement form | Native int/long conversion probes; full policy reconciliation remains open. |
| Unsigned arithmetic | Modulo 2^32 for implemented unsigned types | Native wrap/division/shift probes. |
| Literals | Decimal/octal/hex and U/L suffixes; C++98 candidate ordering | Canonicalized before C emission to preserve historical type selection. |
| Source text | ASCII, LF or CRLF, byte-oriented locations | Non-ASCII and standalone CR are rejected; trigraphs and line splicing are applied with physical locations retained. |
| Limits | 1 MiB, expression/statement depth 128, declaration-scope depth 32, 256 signatures, 16 parameters/arguments and 4096 statements per function | Boundary probes are partial; not a complete Annex B evaluation. |
| Output publication | Temporary file in destination directory; existing destinations preserved | Invalid source, backend failure and collision checks retain previous bytes. |

Signed overflow and invalid shift counts have no portable execution oracle.
The tests avoid relying on those results. Literal values above the supported
32-bit candidate types receive a diagnostic; long long is outside the strict
C++98 subset implemented here. Character, floating, aggregate, pointer and
full cv behavior still need type-model work and explicit choices.

The internal generated-C adapter uses scoped statement expressions to retain
assignment/update lvalue identity and evaluate addresses once. This target
mechanism is not accepted as an extension in user C++ source. M1/M4 must still
prove the final object model, cleanup and exception-handling interface.

## Qualified scalar subset

Local const objects and const value parameters are supported. Their values
can participate in ordinary scalar conversion, while mutation and binding to
non-const references are rejected. Const on a value parameter does not create
a distinct overload. Const references, qualifier-changing reference casts,
volatile and mixed-const conditional lvalues remain explicit feature limits.

## Initial source translation

Source characters are ASCII, with LF or CRLF physical endings. Trigraphs are
replaced before line splicing, and are not recognized a second time after
splicing joins bytes. Source maps retain physical byte columns. A missing
final newline is supplied as an implementation policy; its synthetic byte
maps to physical EOF. Includes, macros and #line remain outside this stage.

## Name and driver limits

Source identifiers are limited to 1024 bytes; qualified spellings and
namespace paths to 4096 bytes. Link mode accepts 32 independently parsed
source files, with aggregate source/lowered text capped at 16 MiB and 1024
signature entries. Compile-only mode accepts one source. These are explicit
prototype resource limits; the final complete inventory remains open.
