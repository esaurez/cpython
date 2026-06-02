# Copyright(c) The Maintainers of Nanvix.
# Licensed under the MIT License.

# toolchain-python — Nanvix GCC toolchain + host Python 3 for CPython
# cross-compilation.  Published as ghcr.io/nanvix/toolchain-python.

FROM ghcr.io/nanvix/toolchain-gcc:sha-34a3641

# Install the host Python plus the build helpers required by extension
# modules that ship a meson or Cython build step (numpy, scipy, pandas,
# ...):
#
#   - ninja  — meson's default backend; missing it makes every meson-based
#              extension build fail immediately.
#   - Cython — required by numpy 1.26.4's `numpy/_build_utils/tempita.py`
#              .pyx.in code generation. Pinned `<3` for numpy 1.26.x
#              compatibility; lift the pin when bumping numpy.
#
# We deliberately purge `/usr/include/python3.12` after the install. The
# `python3-pip` / `ninja-build` apt packages transitively pull in
# `libpython3.12-dev`, whose headers under `/usr/include/python3.12` would
# otherwise be picked up by meson's regen step ahead of the Nanvix cross
# sysroot headers and silently corrupt the cross-build.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        python3-dev \
        python3-pip \
        ninja-build \
    && pip3 install --break-system-packages --no-cache-dir 'Cython<3' \
    && rm -rf /usr/include/python3.12 \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3 /opt/nanvix/bin/python3

# Install the cc-wrapper.  This wrapper sits in front of the real
# `i686-nanvix-gcc` / `i686-nanvix-g++` driver binaries and detects
# whether the invocation is producing an executable or a shared library.
# For shared-library links (-shared) it strips exe-only LDFLAGS that
# would otherwise be inherited from cpython's single `LDFLAGS` env var
# and cause `.so` builds to fail when the linker treats the output as
# an executable.  See cc-wrapper.sh's header for the full rationale.
#
# Install pattern: rename the real driver to `<name>.real`, install the
# wrapper script at `<name>`, and symlink for both gcc and g++.
COPY cc-wrapper.sh /opt/nanvix/bin/i686-nanvix-cc-wrapper.sh
RUN sed -i 's/\r$//' /opt/nanvix/bin/i686-nanvix-cc-wrapper.sh \
    && chmod +x /opt/nanvix/bin/i686-nanvix-cc-wrapper.sh \
    && for tool in i686-nanvix-gcc i686-nanvix-g++; do \
         if [ -L "/opt/nanvix/bin/$tool" ]; then \
             # Pre-existing wrapper symlink: require the matching .real to
             # already exist (set up by a prior wrapper install) before we
             # replace the symlink, so we never strand the toolchain.
             if [ ! -f "/opt/nanvix/bin/$tool.real" ]; then \
                 echo "cc-wrapper install: $tool is a symlink but $tool.real is missing; aborting" >&2; \
                 exit 1; \
             fi; \
             rm /opt/nanvix/bin/$tool; \
         elif [ ! -f "/opt/nanvix/bin/$tool.real" ]; then \
             mv /opt/nanvix/bin/$tool /opt/nanvix/bin/$tool.real; \
         fi; \
         ln -sf i686-nanvix-cc-wrapper.sh /opt/nanvix/bin/$tool; \
       done
