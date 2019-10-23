import asyncio
import sys

__version__ = "3.2.2"


# Avoid issue #132 on Windows & Python 3.8.
if sys.platform == "win32" and sys.version_info >= (3, 8, 0):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
