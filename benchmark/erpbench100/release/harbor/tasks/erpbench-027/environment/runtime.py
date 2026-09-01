"""Standalone world runtime for the Harbor service container.

Re-exports the ERPBench world surface from the vendored ``erpbench100`` package that sits next
to this file, so ``from runtime import ErpWorld, grouped_tool_definitions`` works without the
benchmark source tree.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from erpbench100.world import *  # noqa: E402,F401,F403
from erpbench100.world import (  # noqa: E402,F401
    SERVER_BY_PREFIX,
    SERVERS,
    TABLES,
    ErpWorld,
    grouped_tool_definitions,
    tool_definitions,
)
