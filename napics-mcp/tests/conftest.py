"""让 tests 能 import server / models / clients（napics-mcp 是独立工程，不装包）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
