"""Allow ``python -m vmlx`` to dispatch to the CLI."""

from __future__ import annotations

from vmlx.cli import main

raise SystemExit(main())
