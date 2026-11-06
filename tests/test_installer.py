"""Guard the installer against the source-build trap.

The newest cryptography dropped wheels for 32-bit Windows and Intel macOS;
without --prefer-binary pip builds its sdist and dies on machines with no Rust
toolchain, which reads to the user as a broken install rather than a missing
wheel.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_requirements_prefers_prebuilt_wheels():
    lines = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
    options = [ln.strip() for ln in lines
               if ln.strip() and not ln.strip().startswith("#")]
    assert "--prefer-binary" in options
