import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TEST_ENV = {
    "FOUNDER_FIRST_NAME": "Sneha", "COMPANY": "Axon Labs", "FOUNDER_PHONE_E164": "+919876543210",
    "FOUNDER_PIN": "4321", "FOUNDER_TEST_GMAIL": "founder@test.dev", "INVESTOR_TEST_GMAIL": "priya@northbeam.vc",
    "SECOND_TEST_EMAIL": "riya@acme.test", "THIRD_TEST_EMAIL": "ramesh@kirana.test",
    "FOURTH_TEST_EMAIL": "karan@angel.test",
}
os.environ.update(TEST_ENV)
