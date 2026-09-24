"""Backward-compatible entry point: `python main.py` still works. Prefer `python bot.py`."""
from bot import main

if __name__ == "__main__":
    main()
