"""Build pinned TinyCC support sources outside the dependency checkout.

Arguments are controlled build paths. Native tool failures propagate; source
notices remain in the pinned dependency. This creates local feasibility
artifacts, not a redistributable package or license-compliance verdict.
"""

import argparse
import shutil
import subprocess
from pathlib import Path


def build_runtime(backend, root, output):
    """Compile x64 support and CRT entry objects; raise on any tool failure."""
    source = root / "tinycc"
    library = output / "lib"
    library.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        source / "win32/include", output / "include", dirs_exist_ok=True,
    )
    shutil.copytree(source / "include", output / "include", dirs_exist_ok=True)
    arguments = [
        str(backend), f"-B{output}", f"-I{source / 'include'}",
        f"-I{source / 'win32/include'}",
        f"-I{source / 'win32/include/winapi'}",
    ]
    inputs = [
        "lib/libtcc1.c", "win32/lib/crt1.c", "win32/lib/crt1w.c",
        "win32/lib/wincrt1.c", "win32/lib/wincrt1w.c",
        "win32/lib/dllcrt1.c", "win32/lib/dllmain.c", "win32/lib/winex.c",
        "win32/lib/chkstk.S", "lib/alloca.S", "lib/alloca-bt.S",
        "lib/stdatomic.c", "lib/atomic.S", "lib/builtin.c",
        "lib/complex-arith.c", "lib/tcc-complex.c",
    ]
    objects = []
    for name in inputs:
        obj = output / (Path(name).stem + ".o")
        subprocess.run(
            arguments + ["-c", str(source / name), "-o", str(obj)],
            check=True, timeout=30,
        )
        objects.append(str(obj))
    archive = library / "libtcc1.a"
    # Recreate instead of retaining members from a previous source manifest.
    archive.unlink(missing_ok=True)
    subprocess.run(
        [str(backend), "-ar", str(archive)] + objects,
        check=True, timeout=30,
    )
    for definition in (source / "win32/lib").glob("*.def"):
        shutil.copy2(definition, library / definition.name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    options = parser.parse_args()
    build_runtime(options.backend, options.root, options.output)
