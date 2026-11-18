import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TEST_ENV = {
    "FOUNDER_TEST_GMAIL": "founder@test.dev", "INVESTOR_TEST_GMAIL": "priya@northbeam.vc",
    "SECOND_TEST_EMAIL": "riya@acme.test", "THIRD_TEST_EMAIL": "ramesh@kirana.test",
    "FOURTH_TEST_EMAIL": "karan@angel.test", "COFOUNDER_TEST_EMAIL": "ananya@ownco.test",
    "ACCOUNTANT_TEST_EMAIL": "vikram@joshi.test", "SHIELD_MAIL": "fake", "SHIELD_USER_SECRET": "test-secret",
}
os.environ.update(TEST_ENV)


@pytest.fixture
def shield(tmp_path):
    from app.config import Settings
    from app.mail import FakeMail
    from app.service import Shield
    s = Settings()
    s.runtime_dir = tmp_path / "runtime"
    s.verify_backoff = (0, 0, 0)
    pending = []
    sh = Shield(s, mail=FakeMail(), scheduler=lambda fn: pending.append(fn))
    sh.pending = pending  # tests run scheduled verify loops explicitly
    return sh


def run_pending(sh):
    while sh.pending:
        sh.pending.pop(0)()
