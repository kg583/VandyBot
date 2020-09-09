import asyncio
from vandybot import main


DEBUG = False


if __name__ == '__main__':
    if not DEBUG:
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(main())
        except KeyboardInterrupt:
            loop.close()
    else:
        pass
