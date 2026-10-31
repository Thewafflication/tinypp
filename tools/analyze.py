"""Run the WSP analyzer baseline against owned compiler translation units.

Use the configured MSVC toolset headers instead of whichever Visual Studio
installation clang discovers first. Analysis uses C++14 for the vendor STL;
this is not a claim of a strict C++98 host-source build. Findings and tool
errors fail the run and retain complete diagnostics under output/analysis/.
"""

import argparse
import datetime
import hashlib
import json
import re
import subprocess
import uuid
from pathlib import Path

from evidence import source_snapshot


def analyze(build):
    """Analyze all owned C++ units using the configured host toolset."""
    root = Path(__file__).resolve().parents[1]
    baseline = source_snapshot(root)
    records = list((build / "CMakeFiles").glob("*/CMakeCXXCompiler.cmake"))
    if len(records) != 1:
        raise RuntimeError("Expected one configured CMake C++ toolset record")
    cache = records[0].read_text(encoding="utf-8")
    compiler = re.search(r'set\(CMAKE_CXX_COMPILER "([^"]+)"\)', cache)
    if compiler is None:
        raise RuntimeError("MSVC compiler missing from the toolset record")
    version_match = re.search(
        r'set\(CMAKE_CXX_COMPILER_VERSION "(\d+\.\d+)', cache,
    )
    if version_match is None:
        raise RuntimeError("MSVC compatibility version missing")
    toolset = Path(compiler.group(1)).parents[3]
    analyzer = toolset.parents[1] / "Llvm/x64/bin/clang-tidy.exe"
    if not analyzer.is_file():
        raise RuntimeError(f"Toolset analyzer unavailable: {analyzer}")
    configuration = root / "wsp/tools/static-analysis/wsp-clang-tidy.yml"
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-")
    output = root / "output/analysis" / (stamp + uuid.uuid4().hex[:8])
    output.mkdir(parents=True)
    version = subprocess.run(
        [str(analyzer), "--version"], capture_output=True, text=True,
        check=True, timeout=15,
    ).stdout
    records = []
    for source in sorted((root / "src").glob("*.cpp")):
        arguments = [
            str(analyzer), str(source), f"--config-file={configuration}",
            "--", "-std=c++14",
            f"-fms-compatibility-version={version_match.group(1)}",
            "-nostdinc++", "-isystem", str(toolset / "include"),
            "-isystem", str(root / "tinycc"), f"-I{root / 'src'}",
            "-D_CRT_SECURE_NO_WARNINGS",
        ]
        began = datetime.datetime.now(datetime.timezone.utc).isoformat()
        result = subprocess.run(
            arguments, cwd=root, capture_output=True, text=True, timeout=90,
        )
        (output / (source.stem + ".txt")).write_text(
            result.stdout + result.stderr, encoding="utf-8",
        )
        records.append({
            "source": source.relative_to(root).as_posix(),
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "argv": arguments, "started": began,
            "finished": datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat(),
            "exit_status": result.returncode,
            "status": "Pass" if result.returncode == 0 else "Fail",
        })
        print(f"{records[-1]['status']}: {source.name}")
    stable = baseline == source_snapshot(root)
    (output / "results.json").write_text(json.dumps({
        "analyzer": str(analyzer), "version": version,
        "configuration_sha256": hashlib.sha256(
            configuration.read_bytes()
        ).hexdigest(),
        "profile": "Windows x64; C++14 vendor-header analysis of owned source",
        "results": records,
        "baseline_stable": stable, "input_sha256": baseline,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"Analysis evidence: {output}")
    return not stable or any(record["exit_status"] for record in records)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, default=Path("output/build"))
    raise SystemExit(bool(analyze(parser.parse_args().build.resolve())))
