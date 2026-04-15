# query.py — DEPRECATED: superseded by search.py
#
# This stub transparently forwards all arguments to search.py so that any
# existing habits or scripts that invoke "python query.py" continue to work.

import subprocess
import sys
import os

print(
    "NOTE: query.py has been replaced by search.py.\n"
    "Forwarding to search.py…\n",
    file=sys.stderr,
)

result = subprocess.run(
    [sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "search.py")]
    + sys.argv[1:]
)
sys.exit(result.returncode)
