from __future__ import annotations

from ui_backend.app import create_app
from ui_backend.main import main

app = create_app()


if __name__ == "__main__":
    main()
