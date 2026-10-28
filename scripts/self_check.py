"""Local smoke checks that do not print secrets."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from app.config import settings
    from app.api import create_app

    app = create_app()
    paths = sorted(app.openapi().get("paths", {}))
    print(f"environment={settings.ENVIRONMENT.name}")
    print(f"supabase_url={settings.SUPABASE_URL}")
    print(f"jwt_secret_configured={bool(settings.SUPABASE_JWT_SECRET)}")
    print(f"jwks_mode={settings.SUPABASE_JWT_USE_JWKS}")
    print(f"openapi_path_count={len(paths)}")
    for path in paths:
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
