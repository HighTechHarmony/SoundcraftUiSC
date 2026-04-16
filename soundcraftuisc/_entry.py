#!/usr/bin/env python3
# PyInstaller entry-point shim — avoids the relative-import restriction that
# applies when PyInstaller executes __main__.py as a top-level script.
import sys
from soundcraftuisc.cli import main

if __name__ == '__main__':
    sys.exit(main())
