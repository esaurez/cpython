/*
 * lxml_elementpath_builtin.c - Shim that loads lxml._elementpath at
 *                              runtime via dlopen.
 *
 * Registers the Cython _elementpath extension under the flat name
 * "_lxml_elementpath" so it matches the Modules/Setup.local entry.
 * Pairs with lxml_etree_builtin.c — see that file for the rationale
 * behind the runtime-dlopen layout.
 */

#include "Python.h"

#include <dlfcn.h>

#define LXML_ELEMENTPATH_SO "lib/liblxml_elementpath.so"

typedef PyObject *(*lxml_elementpath_init_fn)(void);

PyMODINIT_FUNC
PyInit__lxml_elementpath(void)
{
    void *handle = dlopen(LXML_ELEMENTPATH_SO, RTLD_NOW | RTLD_GLOBAL);
    if (handle == NULL) {
        PyErr_Format(PyExc_ImportError,
                     "dlopen(\"%s\") failed: %s",
                     LXML_ELEMENTPATH_SO, dlerror());
        return NULL;
    }

    lxml_elementpath_init_fn init =
        (lxml_elementpath_init_fn)dlsym(handle, "PyInit__elementpath");
    if (init == NULL) {
        const char *err = dlerror();
        PyErr_Format(PyExc_ImportError,
                     "dlsym(\"PyInit__elementpath\") in %s failed: %s",
                     LXML_ELEMENTPATH_SO, err ? err : "symbol not found");
        /* Release the handle on this error path. The success path
         * leaks it on purpose (see lxml_etree_builtin.c header). */
        dlclose(handle);
        return NULL;
    }

    return init();
}
