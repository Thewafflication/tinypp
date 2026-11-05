"""Validate Tiny++ planning artifacts without claiming compiler verification.

Run from any directory. Reads controlled project files and the pinned WSP;
prints an artifact summary and exits nonzero for inconsistent records.
"""

import csv
import hashlib
import json
import re
from pathlib import Path


def check_reuse_audit(root):
    """Check selected notice records and bytes; never approve reuse rights."""
    path = root / "docs/research/reuse-audit.csv"
    fields = {
        "component", "path", "revision", "sha256", "notice", "observed_terms",
        "use", "disposition", "open_action",
    }
    errors, seen = [], set()
    if not path.is_file():
        return ["Missing selected-file reuse audit"]
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if set(reader.fieldnames or []) != fields:
            return ["Reuse audit schema mismatch"]
        for row in reader:
            label = f"Reuse audit {row.get('component')}/{row.get('path')}"
            if set(row) != fields or not all(row.values()):
                errors.append(f"{label}: incomplete row")
                continue
            key = (row["component"], row["path"])
            if key in seen:
                errors.append(f"{label}: duplicate file")
            seen.add(key)
            if row["component"] not in {"tinycc", "dmc", "Compiler"}:
                errors.append(f"{label}: unknown component")
                continue
            base = (root / row["component"]).resolve()
            source = (base / row["path"]).resolve()
            if not source.is_relative_to(base) or not source.is_file():
                errors.append(f"{label}: missing or escaping source path")
                continue
            if not re.fullmatch(r"[0-9a-f]{40}", row["revision"]):
                errors.append(f"{label}: malformed pinned revision")
            actual = hashlib.sha256(source.read_bytes()).hexdigest()
            if row["sha256"] != actual:
                errors.append(f"{label}: source hash mismatch")
    if not seen:
        errors.append("Selected-file reuse audit is empty")
    return errors


def check_dmc_defects(root, requirements):
    """Check feasibility records without treating them as ISO defect rulings."""
    fields = {
        "id", "trigger", "source_observation", "expected", "observed",
        "adaptation_or_workaround", "disposition", "requirement_ids",
    }
    path = root / "docs/research/dmc-defects.csv"
    if not path.is_file():
        return ["Missing DMC feasibility defect ledger"]
    errors, seen = [], set()
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if set(reader.fieldnames or []) != fields:
            return ["DMC feasibility defect schema mismatch"]
        for row in reader:
            if set(row) != fields or not all(row.values()):
                errors.append("Incomplete DMC feasibility defect row")
                continue
            identifier = row["id"]
            if not re.fullmatch(r"DM-(BUILD|X64)-\d{3}", identifier):
                errors.append(f"Malformed DMC feasibility ID: {identifier}")
            if identifier in seen:
                errors.append(f"Duplicate DMC feasibility ID: {identifier}")
            seen.add(identifier)
            references = row["requirement_ids"].split(";")
            if len(references) != len(set(references)):
                errors.append(f"{identifier}: duplicate requirement reference")
            for reference in references:
                if reference not in requirements:
                    errors.append(f"{identifier}: unknown {reference}")
    if not seen:
        errors.append("DMC feasibility defect ledger is empty")
    return errors


def check_planning(root):
    """Return structural errors for the controlled baseline at root."""
    errors = []
    controlled = [root / "README.md"] + [
        path for path in (root / "docs").rglob("*")
        if path.suffix in (".md", ".tex", ".csv", ".json")
    ]
    for path in controlled:
        if path.is_file():
            try:
                path.read_bytes().decode("utf-8")
            except UnicodeDecodeError as error:
                errors.append(f"Invalid UTF-8 in {path}: {error}")
    if errors:
        return errors, (0, 0, 0)
    errors.extend(check_reuse_audit(root))
    requirements = {}
    cases = {}
    for folder, pattern, prefix, records in (
        ("requirements", "REQ-*.md", "REQ", requirements),
        ("testing/cases", "TC-*.tex", "TC", cases),
    ):
        for path in sorted((root / "docs" / folder).glob(pattern)):
            identifier = path.stem
            if not re.fullmatch(prefix + r"-\d{4}", identifier):
                errors.append(f"Malformed ID: {path}")
            if identifier in records:
                errors.append(f"Duplicate ID: {identifier}")
            records[identifier] = path.read_text(encoding="utf-8")
    if not requirements or not cases:
        errors.append("Requirement or test inventory is empty")
    errors.extend(check_dmc_defects(root, requirements))
    edges = set()
    for rid, body in requirements.items():
        for section in (
            "Scope", "Requirement", "Rationale", "Verification",
            "Relationships", "Tailoring", "Implementation Record",
        ):
            if f"## {section}\n" not in body:
                errors.append(f"{rid}: missing {section}")
        normative = body.split("## Requirement\n", 1)[-1].split("\n## ")[0]
        if len(re.findall(r"\bshall\b", normative)) != 1:
            errors.append(f"{rid}: expected one normative shall statement")
        refs = set(re.findall(r"\bTC-\d{4}\b", body))
        if not refs:
            errors.append(f"{rid}: no planned verification")
        for tid in refs:
            edges.add((rid, tid))
            if tid not in cases:
                errors.append(f"{rid}: missing {tid}")
    fields = (
        "TCID", "TCTitle", "TCPurpose", "TCPriority", "TCRequirementRef",
        "TCDesignRef", "TCFeatureRef", "TCTestTechnique", "TCPreconditions",
        "TCEnvironment", "TCAssumptions", "TCInputData", "TCInitialState",
        "TCProcedure", "TCExpectedResult", "TCPostConditions",
    )
    reverse = set()
    for tid, body in cases.items():
        for field in fields:
            if not re.search(r"\\def\\" + field + r"\{[^}]+", body):
                errors.append(f"{tid}: empty or missing {field}")
        if f"\\def\\TCID{{{tid}}}" not in body:
            errors.append(f"{tid}: inconsistent internal ID")
        for rid in set(re.findall(r"\bREQ-\d{4}\b", body)):
            reverse.add((rid, tid))
            if rid not in requirements:
                errors.append(f"{tid}: missing {rid}")
    for edge in edges ^ reverse:
        errors.append(f"Nonreciprocal requirement/test reference: {edge}")
    with (root / "docs/testing/traceability.csv").open(
        encoding="utf-8", newline=""
    ) as stream:
        allocations = list(csv.DictReader(stream))
    mapped = [(row["requirement_id"], row["test_id"]) for row in allocations]
    if set(mapped) != edges or len(mapped) != len(set(mapped)):
        errors.append("Allocation table is incomplete or duplicated")
    for row in allocations:
        if row["status"] != "Not run":
            errors.append("Planning allocation falsely implies execution")
        if not re.fullmatch(r"M[0-8]", row["milestone"]):
            errors.append("Unknown milestone in allocation")
    wsp_ids = set()
    for path in (root / "wsp").rglob("*.md"):
        if path.name == "README.md":
            continue
        wsp_ids.update(re.findall(
            r"^#{2,4} (WSP-[A-Z0-9]+-\d{4})\s+[—–-]",
            path.read_text(encoding="utf-8"), re.M,
        ))
    with (root / "docs/process/wsp-dispositions.csv").open(
        encoding="utf-8", newline=""
    ) as stream:
        dispositions = list(csv.DictReader(stream))
    recorded = [row["wsp_id"] for row in dispositions]
    if set(recorded) != wsp_ids or len(recorded) != len(set(recorded)):
        errors.append("WSP disposition coverage mismatch or duplicate")
    for row in dispositions:
        if not all(row.values()):
            errors.append(f"Incomplete disposition: {row['wsp_id']}")
    manifest = json.loads(
        (root / "docs/documentation-manifest.json").read_text("utf-8")
    )
    files = manifest["files"]
    expected = {"README.md"} | {
        path.relative_to(root).as_posix()
        for path in (root / "docs").rglob("*.md")
    }
    if set(files) != expected or len(files) != len(set(files)):
        errors.append("Documentation manifest coverage mismatch")
    for name in files:
        path = root / name
        if not path.is_file():
            errors.append(f"Missing manifest input: {name}")
            continue
        for target in re.findall(
            r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")
        ):
            if "://" in target or target.startswith("#"):
                continue
            if not (path.parent / target.split("#")[0]).exists():
                errors.append(f"Broken local link in {name}: {target}")
    for path in (root / "docs/architecture").glob("ADR-*.md"):
        body = path.read_text(encoding="utf-8")
        for section in (
            "Context", "Decision Drivers", "Considered Options", "Decision",
            "Rationale", "Consequences", "References",
        ):
            if f"## {section}\n" not in body:
                errors.append(f"{path.stem}: missing {section}")
    return errors, (len(requirements), len(cases), len(wsp_ids))


if __name__ == "__main__":
    failures, counts = check_planning(Path(__file__).resolve().parents[1])
    for failure in failures:
        print(f"ERROR: {failure}")
    if failures:
        raise SystemExit(1)
    print(
        f"Planning artifacts valid: {counts[0]} requirements, "
        f"{counts[1]} cases, {counts[2]} WSP dispositions."
    )
    print("Full capability verification: Not run; scalar evidence is separate.")
