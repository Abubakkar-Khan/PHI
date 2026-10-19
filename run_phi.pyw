"""Double-click launcher (no console window). Use --background to start in the tray only."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from phi.app import main  # noqa: E402

sys.exit(main())
