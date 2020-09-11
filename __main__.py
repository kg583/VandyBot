import asyncio
from vandybot import main

# Debug flag
DEBUG = False


async def debug():
    # Left as pass while not being uses
    pass


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    if not DEBUG:
        try:
            loop.run_until_complete(main())
        except KeyboardInterrupt:
            loop.close()
    else:
        try:
            loop.run_until_complete(debug())
        except KeyboardInterrupt:
            loop.close()
