"""Detectors and labels (LLD §4.2). Safeguards under I2; also used by CONTENT (I5) and exposure counting."""
import pytest

from app import labels


def kinds(text):
    return [s.detector for s in labels.detect(text)]


@pytest.mark.parametrize("text,kind", [
    ("PAN ABCPE1234F on file", "pan"),
    ("pan: AAAPL1234C", "pan"),
    ("GSTIN 29ABCPE1234F1Z5", "gstin"),
    ("gst 07AAACB2894G1ZQ", "gstin"),
    ("IFSC HDFC0001234", "ifsc"),
    ("ifsc SBIN0000001", "ifsc"),
    ("pay vikram.joshi@okhdfcbank", "upi"),
    ("upi ravi@ybl", "upi"),
    ("card 4111 1111 1111 1111", "card"),
    ("card 5500-0000-0000-0004", "card"),
    ("aadhaar 2345 6789 0124", "aadhaar"),
    ("key sk-demoX9fK2mQ7rT4vB8nL3pZ6wY1cH5jD0aEe", "api_key"),
    ("aws AKIAIOSFODNN7EXAMPLE", "api_key"),
    ("mail priya@northbeam.vc", "email"),
    ("call +91 9876543210", "phone"),
    ("valuation INR 40 Cr", "money"),
    ("raise $2.5M", "money"),
])
def test_positive(text, kind):
    assert kind in kinds(text)


@pytest.mark.parametrize("text,kind", [
    ("ABCDE1234F", "pan"),                    # 4th char D is not a valid holder type
    ("99ABCPE1234F1Z5", "gstin"),             # state code 99 out of range
    ("HDFC1001234", "ifsc"),                  # 5th char must be 0
    ("priya@northbeam.vc", "upi"),            # an email, not a UPI handle
    ("4111 1111 1111 1112", "card"),          # fails Luhn
    ("2345 6789 0123", "aadhaar"),            # fails Verhoeff
    ("sk-short", "api_key"),
    ("no address here", "email"),
    ("order 12345", "phone"),
    ("40 people attended", "money"),
])
def test_negative(text, kind):
    assert kind not in kinds(text)


def test_upi_is_not_also_an_email():
    assert kinds("vikram.joshi@okhdfcbank") == ["upi"]


def test_overlap_keeps_longest_span():
    # the PAN inside a GSTIN must not be reported separately
    assert kinds("29ABCPE1234F1Z5") == ["gstin"]


def test_checksums():
    assert labels.luhn_ok("4111111111111111") and not labels.luhn_ok("4111111111111112")
    assert labels.verhoeff_ok("234567890124") and not labels.verhoeff_ok("234567890123")


@pytest.mark.parametrize("text,label", [
    ("Updated cap table attached", "financial"),
    ("Term sheet draft", "legal"),
    ("Term sheet draft", "deal"),
    ("Q1 layoff plan", "hr"),
    ("Doctor's note: diagnosis", "health"),
    ("PAN ABCPE1234F", "identity_ids"),
    ("sk-demoX9fK2mQ7rT4vB8nL3pZ6wY1cH5jD0aEe", "secrets"),
])
def test_labels(text, label):
    assert label in labels.labels_for(text)


def test_benign_has_no_labels():
    assert labels.labels_for("Does the annual plan include onboarding support?") == set()
