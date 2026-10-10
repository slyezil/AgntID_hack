from __future__ import annotations

import os

import uvicorn

from counteroffer_api.agent.turn_executor import configured_executor_or_none
from counteroffer_api.app import ApiSettings, create_app
from counteroffer_api.local_config import load_app_environment
from counteroffer_api.turn_store import TurnStore

load_app_environment()
SETTINGS = ApiSettings.from_environment()
STORE = TurnStore(SETTINGS.application_db_path, SETTINGS.schema_path)
EXECUTOR = configured_executor_or_none(SETTINGS, STORE)
app = create_app(SETTINGS, store=STORE, turn_executor=EXECUTOR)


def main() -> None:
    # The public API stays on loopback. A separate, verified tunnel is a later gate.
    uvicorn.run(
        "counteroffer_api.main:app",
        host="127.0.0.1",
        port=int(os.environ.get("APP_PORT", "8000")),
        reload=False,
        access_log=False,
    )


if __name__ == "__main__":
    main()
