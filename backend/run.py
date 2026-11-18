"""Compatibility wrapper: prefer `python -m app` (see README)."""
from app.__main__ import cli

if __name__ == "__main__":
    cli()
