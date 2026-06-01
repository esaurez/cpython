#!/bin/bash
# i686-nanvix-gcc / i686-nanvix-g++ cc-wrapper.
#
# Detects whether the invocation is producing an executable or a shared
# library, and routes to the real compiler driver with the correct linker
# flags for each case.
#
# Why this exists:
#
#   The Nanvix build of CPython sets a single `LDFLAGS` env var on
#   `./configure` that contains executable-specific flags (the linker
#   script `user.ld`, `-no-pie`, `-Wl,--no-dynamic-linker`,
#   `-Wl,--export-dynamic`).  cpython's build system propagates that same
#   `LDFLAGS` to BOTH the main `python.elf` link and to every extension
#   module `.so` link.  For `.so` outputs those exe-only flags are wrong:
#
#     - `-T user.ld`            tells `ld` to use an executable layout.
#                               When applied to a `-shared` link, `ld`
#                               treats the output as an exe and rejects
#                               any undefined symbol -- even those that
#                               should resolve at dlopen() time against
#                               the main exe's `.dynsym` (the C API
#                               symbols every Python extension references).
#     - `-no-pie`               PIE-disable.  Shared libraries must be PIC.
#     - `-Wl,--no-dynamic-linker`  meaningless for `.so`.
#     - `-Wl,--export-dynamic`  exe-only.
#
#   This wrapper makes the build system's single `LDFLAGS` value
#   "do the right thing" for both modes, without forcing each Makefile
#   that consumes the toolchain to know the difference.
#
# Behaviour:
#
#   - If the invocation is compile-only (any of `-c` / `-S` / `-E`):
#         forward unchanged to the real compiler.
#   - If the invocation does NOT contain `-shared`:
#         executable link (or pure compile in the rare case
#         of no `-c`/`-S`/`-E` and no `-shared`).  Forward unchanged.
#   - If the invocation contains `-shared`:
#         shared-library link.  Strip the exe-only flags listed above
#         and ensure `-fPIC` is present.  Forward.
#
# The wrapper is invoked by symlink: i686-nanvix-gcc -> cc-wrapper.sh
# and i686-nanvix-g++ -> cc-wrapper.sh.  The wrapper picks the right
# real binary based on its own argv[0] (i.e. how it was invoked).
#
# Each real binary is preserved as `.real` alongside the wrapper:
#   i686-nanvix-gcc.real, i686-nanvix-g++.real.
#
# See nanvix-todo/c-extension-compiler-wrapper.md for the design note.

set -e

# Find the real binary by appending `.real` to argv[0]'s basename.
self_dir="$(dirname "$0")"
self_name="$(basename "$0")"
real_bin="${self_dir}/${self_name}.real"

if [ ! -x "$real_bin" ]; then
    echo "cc-wrapper: real binary not found at $real_bin" >&2
    exit 1
fi

# Detect mode: compile-only, exe link, or shared link.
shared=0
compile_only=0
for arg in "$@"; do
    case "$arg" in
        -shared)        shared=1 ;;
        -c|-S|-E)       compile_only=1 ;;
    esac
done

if [ "$compile_only" = "1" ] || [ "$shared" = "0" ]; then
    # Compile-only or exe link: forward unchanged.
    exec "$real_bin" "$@"
fi

# Shared-library link: strip exe-only flags and ensure -fPIC.
filtered=()
skip_next=0
have_fpic=0
for arg in "$@"; do
    if [ "$skip_next" = "1" ]; then
        skip_next=0
        continue
    fi
    case "$arg" in
        -T)                                 skip_next=1 ;;
        -T*)                                ;;
        -no-pie)                            ;;
        -Wl,--no-dynamic-linker)            ;;
        -Wl,--export-dynamic)               ;;
        -Wl,-T,*)                           ;;
        *.ld)                               ;;
        -fPIC)
                                            have_fpic=1
                                            filtered+=("$arg")
                                            ;;
        *)                                  filtered+=("$arg") ;;
    esac
done

if [ "$have_fpic" = "0" ]; then
    filtered=(-fPIC "${filtered[@]}")
fi

exec "$real_bin" "${filtered[@]}"
