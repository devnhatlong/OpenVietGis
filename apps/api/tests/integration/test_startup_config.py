from __future__ import annotations

import os
import subprocess
import sys


def test_application_import_fails_fast_when_required_config_is_missing(tmp_path) -> None:
    env = os.environ.copy()
    env.pop("OPENVIETGIS_ENVIRONMENT", None)
    env.pop("OPENVIETGIS_DATABASE_URL", None)
    env.pop("OPENVIETGIS_TEST_DATABASE_URL", None)

    result = subprocess.run(
        [sys.executable, "-c", "import openvietgis_api.main"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    combined = f"{result.stdout}\n{result.stderr}".lower()
    assert result.returncode != 0
    assert "environment" in combined
    assert "database_url" in combined
