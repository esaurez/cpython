# Copyright(c) The Maintainers of Nanvix.
# Licensed under the MIT License.

"""Runtime .so staging for Nanvix CPython.

Single source of truth for the list of shared libraries that must be
present under sysroot/lib/ at run time so the corresponding C extension
.so files (ctypes, ssl, hashlib) can dlopen them.

Consumers:
- .nanvix/test.py::stage     -- staged into the test sysroot
- .nanvix/package.py::package -- staged into the release ramfs
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterable

# Names of .so files that must exist under .nanvix/buildroot/lib/ after
# `./z setup` and must be staged into the test or release sysroot at
# sysroot/lib/<name>. Failure to find any of these is fatal: the
# corresponding C extension (ctypes, ssl, hashlib) would fail at first
# import.
#
# The .so files form a DT_NEEDED chain that the Nanvix dynamic loader
# walks at dlopen time:
#
#   _ctypes.cpython-312.so           -> libffi.so
#   _ssl.cpython-312.so              -> libssl.so + libcrypto.so
#     libssl.so                      -> libcrypto.so
#   _hashlib.cpython-312.so          -> libcrypto.so
REQUIRED_RUNTIME_SOS: tuple[str, ...] = (
    "libffi.so",
    "libcrypto.so",
    "libssl.so",
)


def stage_runtime_sos(
    buildroot_lib: Path,
    sysroot_lib: Path,
    *,
    target_label: str,
    required: Iterable[str] = REQUIRED_RUNTIME_SOS,
) -> None:
    """Copy every entry in ``required`` from ``buildroot_lib`` to
    ``sysroot_lib`` (creating the destination if needed).

    Raises FileNotFoundError if any required .so is missing from
    ``buildroot_lib``. ``target_label`` is interpolated into the error
    message so the caller's context (test stage vs. release package) is
    visible in the traceback.
    """
    sysroot_lib.mkdir(parents=True, exist_ok=True)
    required = tuple(required)
    missing = [name for name in required if not (buildroot_lib / name).is_file()]
    if missing:
        raise FileNotFoundError(
            f"Cannot stage {target_label}: required shared libraries "
            f"missing from {buildroot_lib}: {', '.join(missing)}. Run "
            "`./z setup` to populate the buildroot, or rebuild the upstream "
            "port libraries."
        )
    for so_name in required:
        shutil.copy2(buildroot_lib / so_name, sysroot_lib / so_name)
        print(f"  Staged {so_name} -> sysroot/lib/")
