"""Experimental Windows x64 compiler command using the DMC semantic worker.

Accepts the implemented scalar/object profile, not the complete C++98 language.
Retains every attempt and publishes a new executable only after all gates pass.
Templates, library implementation and the normal tinypp driver stay separate.
"""

import argparse
import datetime
import json
import os
import platform
import struct
import subprocess
import tempfile
import uuid
from pathlib import Path

from evidence import digest, source_snapshot
from semantic_ir import lower_units, read_bodies


def compile_sources(options):
    """Compile generic source files through the checked semantic-only path."""
    root = Path(__file__).resolve().parents[1]
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-")
    work = root / "output/worker-compilation" / (stamp + uuid.uuid4().hex[:8])
    work.mkdir(parents=True)
    result = {
        "kind": "Experimental DMC semantic-only/owned IR/TinyCC compilation",
        "status": "Fail", "target": "windows-x64", "commands": [],
        "parent_requirements_verified": False, "tinycc_started": False,
        "target_link_inputs": [], "native_program_executed": False,
        "host": platform.platform(),
        "limits": ["Scalar/object profile; not full C++98 or strict-mode proof",
                   "No EH/RTTI, general value ABI or mutable cv adjustments",
                   "Header closure and source diagnostics incomplete",
                   "No x86/ARM64 emitter or production replacement claim"],
    }
    baseline = source_snapshot(root)
    immutable = {}

    def run(arguments, environment):
        """Record command identity, timing and all failure diagnostics."""
        record = {"argv": [str(arg) for arg in arguments],
            "started": datetime.datetime.now(datetime.timezone.utc).isoformat()}
        try:
            child = subprocess.run(arguments, cwd=work, env=environment,
                                   capture_output=True, timeout=30)
            record.update(exit_status=child.returncode,
                stdout=child.stdout.decode(errors="replace"),
                stderr=child.stderr.decode(errors="replace"))
        except subprocess.TimeoutExpired as error:
            record.update(exit_status=None, timeout_seconds=30,
                stdout=(error.stdout or b"").decode(errors="replace"),
                stderr=(error.stderr or b"").decode(errors="replace"))
        record["finished"] = datetime.datetime.now(
            datetime.timezone.utc).isoformat()
        result["commands"].append(record)
        if record["exit_status"] != 0:
            raise ValueError("Compiler command failed; inspect diagnostics")

    try:
        compiler = options.worker.resolve()
        build_record = options.build_record.resolve()
        backend, runtime = options.backend.resolve(), options.runtime.resolve()
        destination = options.output.resolve()
        sources = [path.resolve() for path in options.sources]
        if destination.exists():
            raise ValueError("Output already exists; it was preserved")
        if (not destination.parent.is_dir() or not 1 <= len(sources) <= 32 or
                len(set(sources)) != len(sources) or destination in sources):
            raise ValueError("Invalid source set or output directory")
        if any(not path.is_file() for path in sources):
            raise ValueError("A source input is not a regular file")
        if any(path.suffix.lower() != ".cpp" for path in sources):
            raise ValueError("This experimental command accepts .cpp inputs")
        sizes = [path.stat().st_size for path in sources]
        if any(size > 1048576 for size in sizes) or sum(sizes) > 16777216:
            raise ValueError("Source input limits exceeded")
        build = json.loads(build_record.read_text(encoding="utf-8"))
        if (build.get("status") != "Pass" or
                build["output_sha256"] != digest(compiler) or not any(
                    "typed body stream" in patch["change"] for patch in
                    build["source_copy_adaptations"])):
            raise ValueError("Worker does not match a successful body build")
        inputs = sources + [compiler, build_record, backend,
                            backend.parent / "tinypp_tcc.dll"]
        inputs += [path for path in runtime.rglob("*") if path.is_file()]
        immutable = {str(path): digest(path) for path in inputs}
        result["consumed_input_sha256"] = immutable
        environment = os.environ.copy()
        environment.pop("TINYPP_SEMANTIC_EXPORT", None)
        environment["TINYPP_SEMANTIC_BODY_ONLY"] = "1"
        streams = []
        for index, source in enumerate(sources):
            stream = work / f"body{index}.jsonl"
            environment["TINYPP_SEMANTIC_BODY"] = str(stream)
            run([str(compiler), "-m64", "-c", f"-I{source.parent}", str(source),
                 f"-o{work / ('worker' + str(index) + '.obj')}"], environment)
            streams.append(stream)
            immutable[str(stream)] = digest(stream)
        if sum(path.stat().st_size for path in streams) > 16777216:
            raise ValueError("Aggregate IR stream size exceeded")
        units = [read_bodies(path, "windows-x64") for path in streams]
        lowered = lower_units(units)
        objects = []
        environment.pop("TINYPP_SEMANTIC_BODY", None)
        environment.pop("TINYPP_SEMANTIC_BODY_ONLY", None)
        for index, text in enumerate(lowered):
            source, obj = work / f"owned{index}.c", work / f"tinycc{index}.o"
            source.write_text(text, encoding="ascii")
            immutable[str(source)] = digest(source)
            result["tinycc_started"] = True
            run([str(backend), f"-B{runtime}", "-c", str(source),
                 "-o", str(obj)], environment)
            data = obj.read_bytes()
            if (data[:5] != b"\x7fELF\x02" or
                    struct.unpack_from("<H", data, 18)[0] != 62):
                raise ValueError("Expected TinyCC ELF64 x64 intermediate")
            objects.append(str(obj))
        artifact = work / "program.exe"
        result["target_link_inputs"] = objects
        run([str(backend), f"-B{runtime}"] + objects +
            ["-o", str(artifact)], environment)
        data = artifact.read_bytes()
        pe = struct.unpack_from("<I", data, 60)[0]
        if (data[:2] != b"MZ" or data[pe:pe + 4] != b"PE\0\0" or
                struct.unpack_from("<H", data, pe + 4)[0] != 0x8664):
            raise ValueError("Expected Windows x64 PE executable")
        stable = baseline == source_snapshot(root) and all(
            Path(path).is_file() and digest(Path(path)) == value
            for path, value in immutable.items())
        result["baseline_stable"] = stable
        if not stable:
            raise ValueError("Compilation input changed; output not published")
        # A same-directory temporary and exclusive link make publication
        # atomic without replacing a file created after the initial check.
        descriptor, temporary = tempfile.mkstemp(
            prefix=".tinypp-", suffix=".tmp", dir=destination.parent)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.link(temporary, destination)
        finally:
            Path(temporary).unlink(missing_ok=True)
        result.update(status="Pass", artifact=str(destination),
                      artifact_sha256=digest(destination))
    except (OSError, ValueError, KeyError, struct.error) as error:
        result["reason"] = str(error)
    result["input_sha256"] = baseline
    result["artifact_sha256_map"] = {
        path.name: digest(path) for path in work.iterdir() if path.is_file()
    }
    (work / "results.json").write_text(json.dumps(result, indent=2) + "\n",
                                      encoding="utf-8")
    return {"status": result["status"], "evidence": str(work / "results.json"),
            "reason": result.get("reason", ""), "experimental": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--build-record", type=Path, required=True)
    parser.add_argument("--backend", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("sources", type=Path, nargs="+", help="C++ .cpp inputs")
    summary = compile_sources(parser.parse_args())
    print(json.dumps(summary))
    raise SystemExit(summary["status"] != "Pass")
