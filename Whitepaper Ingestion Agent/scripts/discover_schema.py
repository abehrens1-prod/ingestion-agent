"""Discover Whitepaper Contentstack schema through the shared CLI."""

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPOSITORY_ROOT = PROJECT_ROOT.parent
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from ingestion_common import schema_tools
from ingestion_common.console import enable_utf8

enable_utf8()


def main(argv=None) -> int:
    return schema_tools.main(PROJECT_ROOT, argv)


if __name__ == "__main__":
    sys.exit(main())
