import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from src.config import load_playbook_cfg, load_scoring, load_settings  # noqa: E402
from src.pipeline import build_frame  # noqa: E402


@pytest.fixture(scope="session")
def cfgs():
    return load_settings(), load_scoring(), load_playbook_cfg()


@pytest.fixture(scope="session")
def built(cfgs):
    src, feats, df = build_frame(*cfgs)
    return src, feats, df
