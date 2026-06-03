/*
 * lxml_etree_builtin.c - Shim that loads the lxml.etree Cython extension
 *                       at runtime via dlopen.
 *
 * makesetup does not support dotted module names, so the Cython extension
 * is registered under the flat name "_lxml_etree". A pure-Python shim at
 * lxml/etree.py re-exports everything via `from _lxml_etree import *`.
 *
 * On Nanvix the Cython-generated code lives in `liblxml_etree.so`, which
 * declares DT_NEEDED entries for libxslt.so, libexslt.so, and libxml2.so.
 * Loading it via dlopen lets the Nanvix dynamic loader walk that chain
 * (see esaurez/nanvix#27) so each library lives at one address in
 * memory and python.elf does not have to embed multiple megabytes of
 * libxml2/libxslt code statically.
 *
 * The dlopen handle is intentionally leaked: lxml.etree owns process-
 * lifetime parser state, so unloading the library would invalidate
 * still-live `xmlNodePtr` values in the Python heap.
 */

#include "Python.h"

#include <dlfcn.h>

/* Path of the lxml shared library inside the Nanvix ramfs. The loader
 * only searches `lib/` by default, so the explicit prefix removes any
 * ambiguity at dlopen time. */
#define LXML_ETREE_SO "lib/liblxml_etree.so"

typedef PyObject *(*lxml_etree_init_fn)(void);

PyMODINIT_FUNC
PyInit__lxml_etree(void)
{
    /* RTLD_GLOBAL so subsequently loaded extensions that link back into
     * libxml2/libxslt (e.g., xmlsec, future siblings) can resolve their
     * undefined references against the symbols we just published. */
    void *handle = dlopen(LXML_ETREE_SO, RTLD_NOW | RTLD_GLOBAL);
    if (handle == NULL) {
        PyErr_Format(PyExc_ImportError,
                     "dlopen(\"%s\") failed: %s", LXML_ETREE_SO, dlerror());
        return NULL;
    }

    lxml_etree_init_fn init =
        (lxml_etree_init_fn)dlsym(handle, "PyInit_etree");
    if (init == NULL) {
        const char *err = dlerror();
        PyErr_Format(PyExc_ImportError,
                     "dlsym(\"PyInit_etree\") in %s failed: %s",
                     LXML_ETREE_SO, err ? err : "symbol not found");
        /* Release the handle on this error path. The success path
         * intentionally leaks the handle so lxml's process-lifetime
         * state stays valid (see file header). */
        dlclose(handle);
        return NULL;
    }

    return init();
}
