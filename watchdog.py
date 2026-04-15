# watchdog.py — DEPRECATED STUB
#
# This file exists only to display a helpful error message.
#
# The original draft was named watchdog.py, which would shadow the *installed*
# watchdog package whenever Python resolved 'import watchdog' — causing:
#   ModuleNotFoundError: No module named 'watchdog.observers'; 'watchdog' is not a package
#
# The watcher has been moved to watcher.py, which includes a sys.path workaround
# so that both files can coexist safely.  Use watcher.py going forward.
#
# To silence this permanently, you can safely delete this file.

import sys

print(
    "\nERROR: watchdog.py is a deprecated stub.\n"
    "\n"
    "Please use the new watcher instead:\n"
    "    python watcher.py\n"
    "\n"
    "If you are seeing this from an import error, ensure the watchdog\n"
    "package is installed:\n"
    "    pip install watchdog\n",
    file=sys.stderr,
)
sys.exit(1)
