from pathlib import Path

from db import now_jst

LOG_PATH = Path(__file__).parent / "webgif.log"


def log(message: str) -> None:
    line = f"{now_jst()} {message}"
    print(line, flush=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")
