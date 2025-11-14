#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
from pathlib import Path
from xfsettings_ng.main import main
project_dir = Path(__file__).parent
sys.path.insert(0, str(project_dir))


if __name__ == "__main__":
    sys.exit(main())
