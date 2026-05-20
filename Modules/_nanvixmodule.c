/* _nanvix - Low-level Nanvix OS interface for CPython
 *
 * Copyright(c) The Maintainers of Nanvix.
 * Licensed under the MIT License.
 *
 * Provides Python-callable bindings to Nanvix kernel calls and syscalls:
 *   - snapshot(): trigger a VM snapshot (warm-start checkpoint)
 *   - mount(source, target, fstype, flags): mount a filesystem (e.g. hostfs)
 *   - umount(target): unmount a filesystem
 *
 * These functions are available to any Python application running on Nanvix,
 * enabling warm-start patterns and host filesystem access.
 */

#include "Python.h"
#include <errno.h>

/* --------------------------------------------------------------------
 * C declarations for mount/umount from libposix.a
 *
 * These are extern "C" functions provided by Nanvix's syscall library,
 * statically linked into the python binary.
 * -------------------------------------------------------------------- */

extern int mount(const char *source, const char *target,
                 const char *fstype, unsigned long flags);
extern int umount(const char *target);

extern int __kcall_snapshot(void);

/* --------------------------------------------------------------------
 * Python module functions
 * -------------------------------------------------------------------- */

PyDoc_STRVAR(nanvix_snapshot_doc,
"snapshot()\n"
"\n"
"Trigger a Nanvix VM snapshot.\n"
"\n"
"Captures the current guest VM state (memory, CPU registers, RAMFS)\n"
"to disk. On subsequent VM launches with the same snapshot, execution\n"
"resumes immediately after this call, skipping kernel boot and daemon\n"
"initialization.\n"
"\n"
"Raises OSError if the snapshot fails (e.g. kernel was not booted with\n"
"the 'snapshot' argument, or snapshot already taken this boot).\n"
"\n"
"This function is the foundation of warm-start patterns: call it once\n"
"after expensive initialization, then all future restores skip that\n"
"initialization entirely.");

static PyObject *
nanvix_snapshot_impl(PyObject *self, PyObject *Py_UNUSED(args))
{
    int result = __kcall_snapshot();
    if (result != 0) {
        errno = (-result);
        return PyErr_SetFromErrno(PyExc_OSError);
    }
    Py_RETURN_NONE;
}

PyDoc_STRVAR(nanvix_mount_doc,
"mount(source, target, fstype, flags=0)\n"
"\n"
"Mount a filesystem in the Nanvix guest.\n"
"\n"
"For host-mounted filesystems, use:\n"
"    _nanvix.mount('', '/mnt', 'hostfs', 0)\n"
"\n"
"This makes the host directory (specified via nanvixd -mount) available\n"
"at the given mount point inside the guest.\n"
"\n"
"Parameters:\n"
"    source: Source device or empty string for hostfs\n"
"    target: Mount point path (e.g. '/mnt')\n"
"    fstype: Filesystem type ('hostfs' for host-mounted directories)\n"
"    flags:  Mount flags (currently unused, pass 0)\n"
"\n"
"Raises OSError on failure.");

static PyObject *
nanvix_mount_impl(PyObject *self, PyObject *args, PyObject *kwargs)
{
    static char *kwlist[] = {"source", "target", "fstype", "flags", NULL};
    const char *source, *target, *fstype;
    unsigned long flags = 0;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "sss|k:mount",
                                     kwlist, &source, &target, &fstype, &flags))
        return NULL;

    int ret = mount(source, target, fstype, flags);
    if (ret != 0) {
        return PyErr_SetFromErrno(PyExc_OSError);
    }
    Py_RETURN_NONE;
}

PyDoc_STRVAR(nanvix_umount_doc,
"umount(target)\n"
"\n"
"Unmount a filesystem from the given mount point.\n"
"\n"
"Parameters:\n"
"    target: Mount point path to unmount (e.g. '/mnt')\n"
"\n"
"Raises OSError on failure.");

static PyObject *
nanvix_umount_impl(PyObject *self, PyObject *args)
{
    const char *target;

    if (!PyArg_ParseTuple(args, "s:umount", &target))
        return NULL;

    int ret = umount(target);
    if (ret != 0) {
        return PyErr_SetFromErrno(PyExc_OSError);
    }
    Py_RETURN_NONE;
}

/* --------------------------------------------------------------------
 * Module definition
 * -------------------------------------------------------------------- */

static PyMethodDef nanvix_methods[] = {
    {"snapshot", nanvix_snapshot_impl, METH_NOARGS, nanvix_snapshot_doc},
    {"mount", (PyCFunction)nanvix_mount_impl, METH_VARARGS | METH_KEYWORDS,
     nanvix_mount_doc},
    {"umount", nanvix_umount_impl, METH_VARARGS, nanvix_umount_doc},
    {NULL, NULL, 0, NULL}
};

PyDoc_STRVAR(nanvix_module_doc,
"Low-level Nanvix OS interface.\n"
"\n"
"Provides direct access to Nanvix kernel calls and syscalls for:\n"
"  - VM snapshotting (warm-start checkpoints)\n"
"  - Host filesystem mounting (live host directory access)\n"
"\n"
"For a higher-level API, use the 'nanvix' package instead.");

static struct PyModuleDef _nanvixmodule = {
    PyModuleDef_HEAD_INIT,
    "_nanvix",
    nanvix_module_doc,
    -1,
    nanvix_methods,
    NULL,
    NULL,
    NULL,
    NULL
};

PyMODINIT_FUNC
PyInit__nanvix(void)
{
    return PyModule_Create(&_nanvixmodule);
}
