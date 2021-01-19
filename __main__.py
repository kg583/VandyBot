import asyncio
from vandybot import startup, main


if __name__ == '__main__':
    startup()
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        loop.close()

    print("VandyBot is shutting down...")
