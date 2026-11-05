"""Attempt an isolated legacy DMC source build with explicit local tools.

No download, install, dependency edit or deployment target is performed.
Every attempt keeps its source copy, exact commands and diagnostics.
Success establishes a Win32 build spike, not x64 or C++98 conformance.
"""

import argparse
import datetime
import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path

from evidence import digest, source_snapshot


def build(options):
    """Build only scppn.exe in a unique copy; retain failures as evidence."""
    root = Path(__file__).resolve().parents[1]
    if options.x64_nontrivial_parameters and not options.x64_pod_parameters:
        raise ValueError("Nontrivial parameters require late POD lowering")
    if options.semantic_bodies and not options.semantic_signatures:
        raise ValueError("Body handoff requires signature helper support")
    baseline = source_snapshot(root)
    dmd = options.dmd.resolve()
    dmc = options.dmc.resolve()
    make = dmc.parent / "make.exe"
    linker = options.linker.resolve()
    for tool in (dmd, dmc, make, linker):
        if not tool.is_file():
            raise FileNotFoundError(tool)
        if " " in str(tool):
            raise ValueError("Legacy make needs tool paths without spaces")
    tool_identities = {str(tool): digest(tool)
                       for tool in (dmd, dmc, make, linker)}
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-")
    output = root / "output/dmc-source" / (stamp + uuid.uuid4().hex[:8])
    source = output / "source"
    shutil.copytree(root / "Compiler/dm/src/dmc", source)
    patches = []
    if options.cent_field_aliases:
        expected = "69824bc4f030a2585feef1c7a9bc423d14e809ca"
        if baseline["dependency:Compiler:revision"] != expected:
            raise ValueError("Cent adaptation requires the inspected revision")
        path = source / "cdef.d"
        original = path.read_bytes()
        newline = b"\r\n" if b"\r\n" in original else b"\n"
        old = newline.join((b"struct Cent", b"{", b"    targ_ullong lo;",
                            b"    targ_ullong hi;", b"}"))
        new = newline.join((b"struct Cent", b"{", b"    targ_ullong lo;",
                            b"    targ_ullong hi;", b"    alias lsw = lo;",
                            b"    alias msw = hi;", b"}"))
        if original.count(old) != 1:
            raise ValueError("Unexpected Cent definition; adaptation refused")
        before = digest(path)
        path.write_bytes(original.replace(old, new))
        patches.append({
            "path": "cdef.d", "before_sha256": before,
            "after_sha256": digest(path),
            "change": "Add lsw=lo and msw=hi field aliases without storage",
        })
    if options.x64_new_declarations:
        if baseline["dependency:Compiler:revision"] != (
                "69824bc4f030a2585feef1c7a9bc423d14e809ca"):
            raise ValueError("Allocation patch requires inspected revision")
        path = source / "dnwc.d"
        original = path.read_bytes()
        text = original.decode("utf-8")
        start = text.index("    string text =")
        literal = text.index('"extern', start)
        end = text.index('}";', literal) + 2
        old = text[start:end + 1]
        value = text[literal:end]
        if value.count("operator new(unsigned)") != 1:
            raise ValueError("Unexpected scalar allocation declaration")
        wider = value.replace("operator new(unsigned)",
                              "operator new(unsigned long long)")
        new = "    string text = I64 ?\n" + wider + " :\n" + value + ";"
        text = text.replace(old, new, 1)
        prefix = '"extern \\"C++\\" { void * __cdecl operator new[](unsigned),"'
        suffix = '"__cdecl operator delete[](void *); }"'
        if text.count(prefix) != 1:
            raise ValueError("Unexpected array allocation declaration")
        start = text.index(prefix)
        end = text.index(suffix, start) + len(suffix)
        token = text[start:end]
        text = text.replace(token, "(I64 ? " + token.replace(
            "new[](unsigned)", "new[](unsigned long long)"
        ) + " : " + token + ")", 1)
        before = digest(path)
        path.write_bytes(text.encode("utf-8"))
        patches.append({
            "path": "dnwc.d", "before_sha256": before,
            "after_sha256": digest(path),
            "change": "Use 64-bit size for synthesized new/new[] on I64",
        })
    if options.x64_parameter_registers:
        if baseline["dependency:Compiler:revision"] != (
                "69824bc4f030a2585feef1c7a9bc423d14e809ca"):
            raise ValueError("Parameter adaptation requires inspected revision")
        path = source / "out.d"
        original = path.read_bytes()
        newline = b"\r\n" if b"\r\n" in original else b"\n"
        anchor = b"                if (si == 0 && FuncParamRegs_alloc"
        if original.count(anchor) != 1:
            raise ValueError("Unexpected parameter allocation site")
        lines = (
            "                if (I64 && config.exe == EX_WIN64)",
            "                {",
            "                    s.Sclass = FuncParamRegs_alloc(fpr,",
            "                        s.Stype, s.Stype.Tty,",
            "                        &s.Spreg, &s.Spreg2)",
            "                        ? SCshadowreg : SCparameter;",
            "                    s.Sfl = FLpara;",
            "                    goto L3;",
            "                }",
        )
        insertion = newline.join(line.encode("ascii") for line in lines)
        before = digest(path)
        path.write_bytes(original.replace(anchor, insertion + newline + anchor))
        patches.append({
            "path": "out.d", "before_sha256": before,
            "after_sha256": digest(path),
            "change": "Allocate all Win64 parameters with shadow-stack slots",
        })
    if options.x64_pod_parameters:
        if baseline["dependency:Compiler:revision"] != (
                "69824bc4f030a2585feef1c7a9bc423d14e809ca"):
            raise ValueError("POD adaptation requires inspected revision")
        path = source / "out.d"
        original = path.read_bytes()
        newline = b"\r\n" if b"\r\n" in original else b"\n"
        helper = (root / "tools/dmc_pod_lowering.d").read_bytes()
        if options.x64_nontrivial_parameters:
            marker = b"tinypp_indirect_nontrivial = false;"
            if helper.count(marker) != 1:
                raise ValueError("Unexpected nontrivial lowering switch")
            helper = helper.replace(marker,
                b"tinypp_indirect_nontrivial = true;")
        scope = b"// Determine if this Symbol is stored in a COMDAT"
        anchor = b"    FuncParamRegs fpr = FuncParamRegs_create(tyf);"
        if original.count(scope) != 1 or original.count(anchor) != 1:
            raise ValueError("Unexpected ABI lowering insertion sites")
        before = digest(path)
        adapted = original.replace(scope, helper + newline + scope)
        adapted = adapted.replace(anchor,
            b"    tinypp_lower_pod_parameters();" + newline + anchor)
        path.write_bytes(adapted)
        patches.append({
            "path": "out.d", "before_sha256": before,
            "after_sha256": digest(path),
            "change": "Lower Win64 POD parameters after inline expansion",
            "nontrivial_parameters": options.x64_nontrivial_parameters,
        })
    if options.x64_pod_returns:
        if baseline["dependency:Compiler:revision"] != (
                "69824bc4f030a2585feef1c7a9bc423d14e809ca"):
            raise ValueError("Return adaptation requires inspected revision")
        path = source / "dexp2.d"
        original = path.read_bytes()
        newline = b"\r\n" if b"\r\n" in original else b"\n"
        anchor = b"    mangle = type_mangle(tfunc);"
        if original.count(anchor) != 1:
            raise ValueError("Unexpected aggregate return classifier")
        lines = (
            "    if (I64 && config.exe == EX_WIN64 && ty == TYstruct)",
            "    {",
            "        template_instantiate_forward(tn.Ttag);",
            "        if (!(tn.Ttag.Sstruct.Sflags & STRnotpod))",
            "        {",
            "            targ_size_t size = type_size(tn);",
            "            return size == 1 || size == 2 || size == 4 ||",
            "                size == 8 ? RET_REGS : RET_STACK;",
            "        }",
            "    }",
        )
        insertion = newline.join(line.encode("ascii") for line in lines)
        before = digest(path)
        path.write_bytes(original.replace(anchor, anchor + newline + insertion))
        patches.append({
            "path": "dexp2.d", "before_sha256": before,
            "after_sha256": digest(path),
            "change": "Classify Win64 POD returns as RAX or hidden storage",
        })
    if options.x64_relocation_widths:
        if baseline["dependency:Compiler:revision"] != (
                "69824bc4f030a2585feef1c7a9bc423d14e809ca"):
            raise ValueError("Relocation patch requires inspected revision")
        path = source / "cgen.d"
        original = path.read_bytes()
        newline = b"\r\n" if b"\r\n" in original else b"\n"
        anchor = b"case CFoff:         numbytes = tysize(TYnptr);      break;"
        if original.count(anchor) != 1:
            raise ValueError("Unexpected deferred relocation width site")
        replacement = newline.join((
            b"case CFoff:",
            b"                numbytes = I64 && !(flags & CFoffset64)",
            b"                    ? 4 : tysize(TYnptr);",
            b"                break;",
        ))
        before = digest(path)
        path.write_bytes(original.replace(anchor, replacement))
        patches.append({
            "path": "cgen.d", "before_sha256": before,
            "after_sha256": digest(path),
            "change": "Reserve 4 bytes for deferred Win64 32-bit references",
        })
    if options.coff_debug_filename:
        if baseline["dependency:Compiler:revision"] != (
                "69824bc4f030a2585feef1c7a9bc423d14e809ca"):
            raise ValueError("Debug adaptation requires inspected revision")
        path = source / "dnwc.d"
        original = path.read_bytes()
        anchor = b"            Obj.term(null);"
        if original.count(anchor) != 1:
            raise ValueError("Unexpected object finalization site")
        replacement = (b"            Obj.term(config.objfmt == OBJ_MSCOFF"
                       b" ? foutname : null);")
        before = digest(path)
        path.write_bytes(original.replace(anchor, replacement))
        patches.append({
            "path": "dnwc.d", "before_sha256": before,
            "after_sha256": digest(path),
            "change": "Supply COFF object filename to CodeView finalization",
        })
    if options.coff_aggregate_debug:
        if baseline["dependency:Compiler:revision"] != (
                "69824bc4f030a2585feef1c7a9bc423d14e809ca"):
            raise ValueError("Aggregate debug patch needs inspected revision")
        path = source / "dcgcv.d"
        original = path.read_bytes()
        newline = b"\r\n" if b"\r\n" in original else b"\n"
        old = newline.join((
            b"version (MARS)", b"{",
            b"                typidx = cv8_fwdref(t.Ttag);", b"}",
        ))
        if original.count(old) != 1:
            raise ValueError("Unexpected CV8 aggregate type branch")
        extra = newline.join((
            b"else version (SCPP)", b"{",
            b"                typidx = t.Ttag.Stypidx ? t.Ttag.Stypidx",
            b"                    : cv8_fwdref(cast(Symbol*)t.Ttag);", b"}",
        ))
        adapted = original.replace(old, old + newline + extra)
        anchor = b"idx_t cv4_struct(Classsym *s,int flags)"
        start = adapted.index(anchor)
        brace = adapted.index(b"{", start) + 1
        early = newline.join((
            b"", b"version (SCPP)", b"{",
            b"    if (config.fulltypes == CV8)",
            b"        return s.Stypidx ? s.Stypidx",
            b"            : cv8_fwdref(cast(Symbol*)s);", b"}",
        ))
        adapted = adapted[:brace] + early + adapted[brace:]
        old_symbols = newline.join((
            b"version (MARS)", b"{", b"        case CV8:",
            b"            cv8_outsym(s);", b"            break;", b"}",
        ))
        new_symbols = newline.join((b"        case CV8:",
            b"            cv8_outsym(s);", b"            break;"))
        if adapted.count(old_symbols) != 1:
            raise ValueError("Unexpected CV8 symbol dispatch site")
        adapted = adapted.replace(old_symbols, new_symbols)
        before = digest(path)
        path.write_bytes(adapted)
        patches.append({
            "path": "dcgcv.d", "before_sha256": before,
            "after_sha256": digest(path),
            "change": "Route C++ CV8 symbols and opaque aggregate records",
        })
    if options.coff_function_publication:
        if baseline["dependency:Compiler:revision"] != (
                "69824bc4f030a2585feef1c7a9bc423d14e809ca"):
            raise ValueError("COFF publication patch needs inspected revision")
        path = source / "out.d"
        original = path.read_bytes()
        anchor = (b"(config.objfmt == OBJ_OMF || config.objfmt == OBJ_MSCOFF)"
                  b" && !(config.flags4 & CFG4allcomdat)")
        if original.count(anchor) != 1:
            raise ValueError("Unexpected duplicate function publication site")
        before = digest(path)
        path.write_bytes(original.replace(anchor,
            b"config.objfmt == OBJ_OMF && !(config.flags4 & CFG4allcomdat)"))
        patches.append({
            "path": "out.d", "before_sha256": before,
            "after_sha256": digest(path),
            "change": "Leave COFF function publication to func_start",
        })
    if options.x64_register_save_mask:
        if baseline["dependency:Compiler:revision"] != (
                "69824bc4f030a2585feef1c7a9bc423d14e809ca"):
            raise ValueError("Register mask patch needs inspected revision")
        path = source / "cod3.d"
        original = path.read_bytes()
        start = original.index(b"void cod3_set64()")
        end = original.index(b"FLOATREGS = FLOATREGS_64;", start)
        region = original[start:end]
        if region.count(b" | mES") != 2:
            raise ValueError("Unexpected 64-bit callee-saved register masks")
        before = digest(path)
        path.write_bytes(original[:start] + region.replace(b" | mES", b"") +
                         original[end:])
        patches.append({
            "path": "cod3.d", "before_sha256": before,
            "after_sha256": digest(path),
            "change": "Exclude legacy ES bit from 64-bit register save masks",
        })
    if options.x64_local_alignment:
        if baseline["dependency:Compiler:revision"] != (
                "69824bc4f030a2585feef1c7a9bc423d14e809ca"):
            raise ValueError("Local alignment patch needs inspected revision")
        path = source / "cgcod.d"
        original = path.read_bytes()
        newline = b"\r\n" if b"\r\n" in original else b"\n"
        anchor = b"Auto.offset = _align(sz,Auto.offset);"
        if original.count(anchor) != 2:
            raise ValueError("Unexpected local stack allocation sites")
        replacement = newline.join((
            b"Auto.offset = I64 && config.exe == EX_WIN64 &&",
            b"                    s.Salignment > 0",
            b"                    ? (Auto.offset + alignsize - 1) &",
            b"                      ~(cast(targ_size_t)alignsize - 1)",
            b"                    : _align(sz,Auto.offset);",
        ))
        before = digest(path)
        path.write_bytes(original.replace(anchor, replacement))
        patches.append({
            "path": "cgcod.d", "before_sha256": before,
            "after_sha256": digest(path),
            "change": "Honor explicit Win64 local alignment in stack layout",
        })
    if options.semantic_signatures:
        if baseline["dependency:Compiler:revision"] != (
                "69824bc4f030a2585feef1c7a9bc423d14e809ca"):
            raise ValueError("Semantic handoff needs inspected revision")
        path = source / "out.d"
        original = path.read_bytes()
        newline = b"\r\n" if b"\r\n" in original else b"\n"
        scope = b"// Determine if this Symbol is stored in a COMDAT"
        anchor = b"    /* Copy local symbol table onto main one, making sure"
        if original.count(scope) != 1 or original.count(anchor) != 1:
            raise ValueError("Unexpected semantic signature handoff sites")
        helper = (root / "tools/dmc_semantic_export.d").read_bytes()
        before = digest(path)
        adapted = original.replace(scope, helper + newline + scope)
        adapted = adapted.replace(anchor,
            b"    tinypp_semantic_signature(sfunc);" + newline + anchor)
        path.write_bytes(adapted)
        patches.append({
            "path": "out.d", "before_sha256": before,
            "after_sha256": digest(path),
            "change": "Optional copied signature stream before target lowering",
        })
    if options.semantic_bodies:
        path = source / "out.d"
        original = path.read_bytes()
        newline = b"\r\n" if b"\r\n" in original else b"\n"
        scope = b"// Determine if this Symbol is stored in a COMDAT"
        anchor = b"    assert(startblock);"
        if original.count(scope) != 1 or original.count(anchor) != 1:
            raise ValueError("Unexpected semantic body handoff sites")
        helper = (root / "tools/dmc_semantic_body.d").read_bytes()
        before = digest(path)
        adapted = original.replace(scope, helper + newline + scope)
        replacement = newline.join((anchor,
            b"    if (tinypp_semantic_body(sfunc))",
            b"    {", b"        blocklist_free(&startblock);",
            b"        globsym.setLength(0);", b"        return;", b"    }"))
        adapted = adapted.replace(anchor, replacement)
        path.write_bytes(adapted)
        patches.append({
            "path": "out.d", "before_sha256": before,
            "after_sha256": digest(path),
            "change": "Optional typed body stream before inline/ABI lowering",
        })
    copied_inputs = {path.relative_to(source).as_posix(): digest(path)
                     for path in source.rglob("*") if path.is_file()}
    environment = os.environ.copy()
    environment["PATH"] = os.pathsep.join((
        str(dmd.parent), str(dmc.parent), environment.get("PATH", ""),
    ))
    records = []

    def command(label, arguments, timeout):
        """Retain tool output, status and timing, including timeouts."""
        began = datetime.datetime.now(datetime.timezone.utc).isoformat()
        record = {"label": label, "argv": [str(a) for a in arguments],
                  "started": began, "cwd": str(source)}
        log = output / (label + ".txt")
        try:
            with log.open("wb") as stream:
                result = subprocess.run(
                    arguments, cwd=source, env=environment, stdout=stream,
                    stderr=subprocess.STDOUT, timeout=timeout,
                )
            record["exit_status"] = result.returncode
        except subprocess.TimeoutExpired:
            record["exit_status"] = None
            record["reason"] = f"Timed out after {timeout} seconds"
        record["finished"] = datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()
        record["log"] = log.name
        records.append(record)
        return record["exit_status"]

    command("dmd-version", [str(dmd), "--version"], 15)
    command("dmc-version", [str(dmc)], 15)
    arguments = [
        str(make), f"CC={dmc}", f"DMD={dmd}",
        f"DMCDIR={dmc.parent.parent}", f"LINKN={linker}",
        "TARGET=SCPP", "OPT=-o", "DEBUG= -DSTATIC= -Nc",
        "DOPT=-O -inline" if options.enable_assertions else
        "DOPT=-O -release -inline",
        "LFLAGS=/noi/noe/map/co", "scppn.exe",
    ]
    status = command("build", arguments, 300)
    executable = source / "scppn.exe"
    built = status == 0 and executable.is_file()
    if built:
        command("source-built-banner", [str(executable)], 15)
    stable = (baseline == source_snapshot(root) and tool_identities == {
        str(tool): digest(tool) for tool in (dmd, dmc, make, linker)
    } and copied_inputs == {
        name: digest(source / name) for name in copied_inputs
    })
    record = {
        "kind": "Isolated DMC Win32 source-build feasibility",
        "status": "Pass" if built and stable else "Fail",
        "baseline_stable": stable, "commands": records,
        "source_copy_adaptations": patches,
        "d_assertions_enabled": options.enable_assertions,
        "copied_input_sha256": copied_inputs,
        "generated_source_sha256": {
            path.relative_to(source).as_posix(): digest(path)
            for path in source.rglob("*")
            if path.suffix in (".d", ".di", ".c", ".h") and
            path.relative_to(source).as_posix() not in copied_inputs
        },
        "input_sha256": baseline,
        "tools_sha256": tool_identities,
        "output_sha256": digest(executable) if built else None,
        "limits": ["Not a Windows x64 compiler integration",
                   "Not complete C++98 verification",
                   "Tool provenance is recorded separately from build success"],
    }
    (output / "results.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8",
    )
    print(f"{record['status']}: DMC source build")
    print(f"Evidence: {output}")
    if not built:
        print((output / "build.txt").read_text(
            encoding="utf-8", errors="replace",
        )[-6000:])
    return not built or not stable


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dmd", type=Path, required=True)
    parser.add_argument("--dmc", type=Path, required=True)
    parser.add_argument("--linker", type=Path, required=True)
    parser.add_argument("--cent-field-aliases", action="store_true")
    parser.add_argument("--x64-new-declarations", action="store_true")
    parser.add_argument("--x64-parameter-registers", action="store_true")
    parser.add_argument("--x64-pod-parameters", action="store_true")
    parser.add_argument("--x64-pod-returns", action="store_true")
    parser.add_argument("--enable-assertions", action="store_true")
    parser.add_argument("--x64-relocation-widths", action="store_true")
    parser.add_argument("--coff-debug-filename", action="store_true")
    parser.add_argument("--coff-aggregate-debug", action="store_true")
    parser.add_argument("--coff-function-publication", action="store_true")
    parser.add_argument("--x64-register-save-mask", action="store_true")
    parser.add_argument("--x64-nontrivial-parameters", action="store_true")
    parser.add_argument("--x64-local-alignment", action="store_true")
    parser.add_argument("--semantic-signatures", action="store_true")
    parser.add_argument("--semantic-bodies", action="store_true")
    raise SystemExit(bool(build(parser.parse_args())))
