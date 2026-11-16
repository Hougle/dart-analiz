"""Make sure the app never runs a mix of new and old project modules.

After a push, Streamlit Cloud reruns the new app.py, but it can keep an older
copy of an imported module in memory (seen as a TypeError: new app.py calling
an old coaching_page.render_coaching_page). drop_stale_modules() runs before
the project imports in app.py and drops every project module from sys.modules,
so they are all imported fresh, together:

- once, the first time it runs in a server process (covers modules that were
  loaded before this check existed or before the latest pull), and
- whenever a project file changed after its module was loaded.
"""
import os
import sys

_STATE = "_dartanaliz_freshness"


def _project_modules(root):
    out = {}
    for name, mod in list(sys.modules.items()):
        path = getattr(mod, "__file__", None)
        if name == "__main__" or not path:
            continue
        path = os.path.abspath(path)
        if os.path.dirname(path) == root and path.endswith(".py"):
            out[name] = (mod, path)
    return out


def _mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def drop_stale_modules(root=None):
    """Drop all project modules if this is the process's first check or any file changed.
    Returns the names dropped."""
    root = os.path.abspath(root or os.path.dirname(os.path.abspath(__file__)))
    state = sys.__dict__.setdefault(_STATE, {})
    seen = state.setdefault(root, {})          # name -> (id(module), file mtime when first seen)
    first_check = not state.get(root + ":checked")
    state[root + ":checked"] = True

    mods = _project_modules(root)
    stale = first_check and bool(mods)
    for name, (mod, path) in mods.items():
        mtime = _mtime(path)
        known = seen.get(name)
        if known and known[0] == id(mod):
            if mtime is not None and known[1] is not None and mtime > known[1]:
                stale = True
        else:
            seen[name] = (id(mod), mtime)
    if not stale:
        return []
    for name in mods:
        sys.modules.pop(name, None)
        seen.pop(name, None)
    return sorted(mods)
