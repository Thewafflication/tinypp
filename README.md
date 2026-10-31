# Tiny++

An experimental C++98 compiler core drawing from TinyCC and Digital Mars C++.

**Content type:** Project overview and controlled planning index

**Planning baseline:** Proposed, 2026-10-31. A bounded scalar prototype is
implemented; full C++98 conformance is not claimed.

- [Research and primary sources](docs/research/standards.md).
- [Useful DMC assets and project boundary](docs/research/dmc-reuse.md).
- [WSP adoption and individual dispositions](docs/process/wsp-adoption.md).
- [44 requirements](docs/requirements/README.md).
- [Nine architecture decisions](docs/architecture/README.md).
- [44 controlled test-case specifications](docs/testing/README.md).
- [Verification strategy](docs/testing/STRATEGY.md).
- [Build/use and implementation evidence](docs/process/compiler-foundation.md).
- [Roadmap and milestone exit gates](docs/ROADMAP.md).
- [Bidirectional allocation table](docs/testing/traceability.csv).

The proposed first target is Windows x86-64. Templates and the standard
library belong to an existing separate project. Tiny++ owns compiler-core
implementation, exception handling, RTTI and integration interfaces. A full
hosted C++98 claim applies to the verified combined delivery.
DMC runtime/library assets are reuse candidates; this checkout has not yielded
a reusable compiler front end. The plan includes an independent front end.

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
