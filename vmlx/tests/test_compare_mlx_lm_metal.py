"""Metal-gated smoke test for the vmlx-vs-mlx-lm benchmark harness.

Boots only the vmlx server (skipping mlx-lm to keep runtime reasonable),
runs a 1-request-per-level sweep, and asserts the markdown report is
well-formed. The full head-to-head run is too slow for CI; this test
covers the subprocess + streaming + markdown pipeline end to end so
regressions in those seams surface before a human runs the real sweep.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vmlx.benchmarks.compare_mlx_lm import main as compare_main

TEST_MODEL = "mlx-community/Qwen2.5-0.5B-Instruct-4bit"


@pytest.mark.metal
def test_compare_mlx_lm_vmlx_only_smoke(tmp_path: Path) -> None:
    """Boot vmlx serve, fire a tiny sweep, and validate the markdown output.

    Skips mlx-lm to cut runtime roughly in half; we're validating the
    harness, not the head-to-head numbers (which are product content,
    not test content).
    """
    output = tmp_path / "report.md"
    json_output = tmp_path / "report.json"
    log_dir = tmp_path / "logs"

    rc = compare_main(
        [
            "--model",
            TEST_MODEL,
            "--concurrency",
            "1,2",
            "--requests-per-level",
            "2",
            "--max-tokens",
            "8",
            "--shared-prefix-chars",
            "500",
            "--output",
            str(output),
            "--json-output",
            str(json_output),
            "--log-dir",
            str(log_dir),
            "--skip-mlx-lm",
        ]
    )
    assert rc == 0
    assert output.exists()
    body = output.read_text(encoding="utf-8")
    # Structural checks — content will vary per hardware / run.
    assert "# vMLX vs mlx-lm benchmark" in body
    assert "## Reproducibility" in body
    assert "## Results" in body
    assert "| vmlx | 1 |" in body
    assert "| vmlx | 2 |" in body
    # No mlx-lm rows because we skipped it.
    assert "| mlx-lm |" not in body

    # JSON side-channel must be valid JSON and expose the level we ran.
    import json

    data = json.loads(json_output.read_text(encoding="utf-8"))
    assert data["model"] == TEST_MODEL
    assert data["concurrency_levels"] == [1, 2]
    # Every result must be from vmlx since we skipped mlx-lm.
    assert all(r["server"] == "vmlx" for r in data["results"])
