from datetime import datetime
from pathlib import Path

LOG_PATH = Path(__file__).parent / "webgif.log"


def log(message: str) -> None:
    line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {message}"
    print(line, flush=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")
