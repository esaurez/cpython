# Copyright(c) The Maintainers of Nanvix.
# Licensed under the MIT License.

"""Single source of truth for Modules/Setup.local on Nanvix builds.

The host-build path (generate_setup_local, below) and the Docker-build
path (.nanvix/docker.py::_generate_setup_local_cmd) both consume
SETUP_LOCAL_ENTRIES and render the same file body via
render_setup_local().

Module ordering matters: makesetup applies "first rule wins" semantics
when the same module is declared both here and in the upstream
Modules/Setup.stdlib. *static* entries must precede *shared* entries
within a section; declaring a *shared* duplicate before the upstream
*static* default is how each migrated stdlib module switches link mode
to a runtime-loaded .so.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Iterable, NamedTuple, Sequence


class Linkage(Enum):
    STATIC = "*static*"
    SHARED = "*shared*"


class SetupEntry(NamedTuple):
    """One line of Modules/Setup.local plus optional surrounding comments.

    The rendered line is::

        <name> <token> <token> ...

    Tokens may contain the literal substring ``{sysroot}``; the renderer
    substitutes it for the actual sysroot path. No other formatting is
    applied.

    ``comment`` (if set) is emitted as a single ``# ...`` line directly
    above the entry. ``section_header`` (if set) is emitted as a block
    of ``# ...`` lines immediately above the section's linkage marker
    the FIRST time an entry contributes to a new section grouping; it
    is intended as a separator between groups of related modules.
    """

    name: str
    linkage: Linkage
    tokens: Sequence[str] = ()
    comment: str = ""
    section_header: str = ""


# ---------------------------------------------------------------------------
# The table
# ---------------------------------------------------------------------------
#
# Section order (enforced by the renderer based on Linkage transitions):
#
#   *static*  -- the _nanvix OS-interface module (only).
#
#   *shared*  -- every extension module built as a runtime-loaded .so.
#                For modules with bundled-in-cpython C deps (_decimal,
#                pyexpat, _elementtree, _sha2), each .so bundles its own
#                vendored .a -- same behavior as upstream cpython's
#                default ./configure run. mpdec / expat / HACL hashing
#                are stateless C APIs with at most one consumer each
#                (pyexpat exposes a PyCapsule that _elementtree calls
#                through, so libexpat lives in pyexpat.so only); there
#                is no need to hoist their code into python.elf for
#                cross-module sharing.

SETUP_LOCAL_ENTRIES: tuple[SetupEntry, ...] = (
    # ---------------- *static* -----------------------------------------
    SetupEntry(
        name="_nanvix",
        linkage=Linkage.STATIC,
        tokens=("_nanvixmodule.c",),
        comment="Nanvix OS interface module (snapshot, host-mount).",
    ),
    # ---------------- *shared* -----------------------------------------
    SetupEntry(
        name="array",
        linkage=Linkage.SHARED,
        tokens=("arraymodule.c",),
        section_header=(
            "`array` as the proof-of-concept shared module. Listed "
            "BEFORE Setup.stdlib's static declaration so makesetup's "
            '"first rule wins" semantics make this shared variant '
            "take precedence."
        ),
    ),
    # ---------------- Data primitives (no external deps) ----------------
    *(
        SetupEntry(
            name=name,
            linkage=Linkage.SHARED,
            tokens=(src,),
            section_header=(header if i == 0 else ""),
        )
        for i, (name, src) in enumerate(
            (
                ("_bisect", "_bisectmodule.c"),
                ("_heapq", "_heapqmodule.c"),
                ("_struct", "_struct.c"),
                ("_random", "_randommodule.c"),
                ("_opcode", "_opcode.c"),
                ("_queue", "_queuemodule.c"),
                ("_csv", "_csv.c"),
                ("binascii", "binascii.c"),
                ("_json", "_json.c"),
                ("_pickle", "_pickle.c"),
                ("_zoneinfo", "_zoneinfo.c"),
            )
        )
        for header in ("Data primitives (pure C, no external deps).",)
    ),
    # ---------------- Math + memory (libm via python.elf) --------------
    *(
        SetupEntry(
            name=name,
            linkage=Linkage.SHARED,
            tokens=(src,),
            section_header=(header if i == 0 else ""),
        )
        for i, (name, src) in enumerate(
            (
                ("math", "mathmodule.c"),
                ("cmath", "cmathmodule.c"),
                ("_statistics", "_statisticsmodule.c"),
                ("mmap", "mmapmodule.c"),
                ("_contextvars", "_contextvarsmodule.c"),
            )
        )
        for header in (
            "Math and memory modules (libm symbols pulled from python.elf via --whole-archive).",
        )
    ),
    # ---------------- Text codecs (no external deps) -------------------
    *(
        SetupEntry(
            name=name,
            linkage=Linkage.SHARED,
            tokens=(src,),
            section_header=(header if i == 0 else ""),
        )
        for i, (name, src) in enumerate(
            (
                ("unicodedata", "unicodedata.c"),
                ("_multibytecodec", "cjkcodecs/multibytecodec.c"),
                ("_codecs_cn", "cjkcodecs/_codecs_cn.c"),
                ("_codecs_hk", "cjkcodecs/_codecs_hk.c"),
                ("_codecs_iso2022", "cjkcodecs/_codecs_iso2022.c"),
                ("_codecs_jp", "cjkcodecs/_codecs_jp.c"),
                ("_codecs_kr", "cjkcodecs/_codecs_kr.c"),
                ("_codecs_tw", "cjkcodecs/_codecs_tw.c"),
            )
        )
        for header in ("Text codecs (pure C, no external deps).",)
    ),
    # ---------------- Modules with bundled-in-cpython C deps -----------
    #
    # Each .so module bundles its own copy of the vendored .a -- the
    # exact same behavior as upstream cpython's default ./configure
    # run on Linux without --with-system-*. cpython's configure sets
    # MODULE__DECIMAL_LDFLAGS=-lm $(LIBMPDEC_A) and
    # MODULE_PYEXPAT_LDFLAGS=-lm $(LIBEXPAT_A) automatically, so the
    # bare `_decimal _decimal/_decimal.c` and `pyexpat pyexpat.c`
    # entries below pick up libmpdec / libexpat via cpython's normal
    # MODULE_*_LDFLAGS machinery. _sha2 hardcodes the libHacl_Hash_SHA2.a
    # path explicitly, matching upstream Modules/Setup.stdlib.in (HACL
    # has no LIBHACL_LDFLAGS configure knob since there is no system-mode
    # equivalent for vendored verified-crypto code).
    #
    # The other HACL hashes (_md5, _sha1, _sha3, _blake2) inline-compile
    # their own _hacl translation units rather than linking a shared
    # libHacl_Hash_*.a -- same shape as upstream.
    SetupEntry(
        name="_asyncio",
        linkage=Linkage.SHARED,
        tokens=("_asynciomodule.c",),
        section_header=(
            "Modules with bundled-in-cpython C deps. Each .so bundles "
            "its own vendored .a, matching upstream cpython's default "
            "./configure behavior."
        ),
    ),
    SetupEntry(name="_datetime", linkage=Linkage.SHARED, tokens=("_datetimemodule.c",)),
    SetupEntry(
        name="_decimal", linkage=Linkage.SHARED, tokens=("_decimal/_decimal.c",)
    ),
    SetupEntry(name="pyexpat", linkage=Linkage.SHARED, tokens=("pyexpat.c",)),
    SetupEntry(name="_elementtree", linkage=Linkage.SHARED, tokens=("_elementtree.c",)),
    SetupEntry(
        name="_md5",
        linkage=Linkage.SHARED,
        tokens=(
            "md5module.c",
            "-I$(srcdir)/Modules/_hacl/include",
            "_hacl/Hacl_Hash_MD5.c",
            "-D_BSD_SOURCE",
            "-D_DEFAULT_SOURCE",
        ),
    ),
    SetupEntry(
        name="_sha1",
        linkage=Linkage.SHARED,
        tokens=(
            "sha1module.c",
            "-I$(srcdir)/Modules/_hacl/include",
            "_hacl/Hacl_Hash_SHA1.c",
            "-D_BSD_SOURCE",
            "-D_DEFAULT_SOURCE",
        ),
    ),
    SetupEntry(
        name="_sha2",
        linkage=Linkage.SHARED,
        tokens=(
            "sha2module.c",
            "-I$(srcdir)/Modules/_hacl/include",
            "Modules/_hacl/libHacl_Hash_SHA2.a",
        ),
    ),
    SetupEntry(
        name="_sha3",
        linkage=Linkage.SHARED,
        tokens=(
            "sha3module.c",
            "-I$(srcdir)/Modules/_hacl/include",
            "_hacl/Hacl_Hash_SHA3.c",
            "-D_BSD_SOURCE",
            "-D_DEFAULT_SOURCE",
        ),
    ),
    SetupEntry(
        name="_blake2",
        linkage=Linkage.SHARED,
        tokens=(
            "_blake2/blake2module.c",
            "_blake2/blake2b_impl.c",
            "_blake2/blake2s_impl.c",
        ),
    ),
    SetupEntry(name="select", linkage=Linkage.SHARED, tokens=("selectmodule.c",)),
    SetupEntry(name="_socket", linkage=Linkage.SHARED, tokens=("socketmodule.c",)),
    SetupEntry(
        name="_posixsubprocess", linkage=Linkage.SHARED, tokens=("_posixsubprocess.c",)
    ),
    SetupEntry(name="fcntl", linkage=Linkage.SHARED, tokens=("fcntlmodule.c",)),
    SetupEntry(name="termios", linkage=Linkage.SHARED, tokens=("termios.c",)),
)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _wrap_comment(text: str, *, width: int = 78) -> list[str]:
    """Wrap a comment body to ``width`` columns, returning '# '-prefixed
    lines suitable for direct emission into Setup.local. Empty input
    yields an empty list."""
    if not text:
        return []
    import textwrap

    wrapped = textwrap.wrap(text, width=width - 2)  # account for '# '
    return [f"# {line}" for line in wrapped]


def render_setup_local(
    entries: Iterable[SetupEntry] = SETUP_LOCAL_ENTRIES,
    *,
    sysroot: str,
    header_comment: str,
) -> str:
    """Render the entries to a complete Modules/Setup.local file body.

    ``header_comment`` becomes the first line so the file self-identifies
    its generator (host vs Docker). ``sysroot`` substitutes every literal
    ``{sysroot}`` token in any entry.
    """
    lines: list[str] = []
    lines.append(f"# {header_comment}")
    lines.append("")

    current_linkage: Linkage | None = None
    for entry in entries:
        new_section = entry.linkage is not current_linkage
        if new_section:
            if current_linkage is not None:
                lines.append("")
            if entry.section_header:
                lines.extend(_wrap_comment(entry.section_header))
            else:
                # No header for the very first section -- emit a minimal
                # marker comment so the file remains self-documenting.
                if current_linkage is None and entry.linkage is Linkage.STATIC:
                    lines.append(
                        "# Statically-linked extension modules for Nanvix builds."
                    )
            lines.append(entry.linkage.value)
            current_linkage = entry.linkage
        elif entry.section_header:
            # Mid-section group separator (e.g. moving from one shared
            # group to the next without changing linkage). Emit as a
            # blank-line-separated comment block before the entry.
            lines.append("")
            lines.extend(_wrap_comment(entry.section_header))

        if entry.comment:
            lines.extend(_wrap_comment(entry.comment))
        tokens = " ".join(entry.tokens).replace("{sysroot}", sysroot)
        if tokens:
            lines.append(f"{entry.name} {tokens}")
        else:
            lines.append(entry.name)

    lines.append("")  # trailing newline
    return "\n".join(lines)


def generate_setup_local(repo_root: Path, sysroot: Path) -> None:
    """Generate Modules/Setup.local from SETUP_LOCAL_ENTRIES.

    Single source of truth shared with the Docker build path
    (.nanvix/docker.py::_generate_setup_local_cmd). The {sysroot}
    placeholder in entry tokens is substituted with the host build's
    sysroot path here.
    """
    setup_local = repo_root / "Modules" / "Setup.local"
    content = render_setup_local(
        sysroot=str(sysroot),
        header_comment="Auto-generated by .nanvix/setup_local.py -- do not edit manually.",
    )
    setup_local.write_text(content, encoding="utf-8")
    print(f"[setup_local] Generated {setup_local}")
