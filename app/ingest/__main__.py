"""Allow `python -m app.ingest.cli` to work."""
from app.ingest.cli import main

raise SystemExit(main())
