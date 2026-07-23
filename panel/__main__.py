"""Entry point: ``python -m panel``.

Importing ``panel`` puts ``engine/`` on sys.path, so the bootstrap helpers are
importable here — and they run before ``.app`` is touched, because that module
imports Flask at the top and a missing Flask is exactly what this catches.
"""

from bootstrap import ensure_utf8_stdio, require_modules   # from engine/

ensure_utf8_stdio()
require_modules("flask", "requests", "cryptography")

from .app import main   # noqa: E402  (must follow the dependency check)

if __name__ == "__main__":
    main()
