import asyncio
import ssl
from vandybot import startup, main


# Strange SSL shenanigans in 3.7; see https://github.com/aio-libs/aiohttp/issues/3535
def ignore_aiohttp_ssl_error(event_loop):
    orig_handler = event_loop.get_exception_handler()

    def ignore_ssl_error(self, context):
        if context.get("message") in {"SSL error in data received", "Fatal error on transport"}:
            exception = context.get("exception")
            protocol = context.get("protocol")
            if isinstance(exception, ssl.SSLError) and \
                    exception.reason == 'KRB5_S_INIT' and isinstance(protocol, asyncio.sslproto.SSLProtocol):
                return
        if orig_handler is not None:
            orig_handler(self, context)
        else:
            self.default_exception_handler(context)

    event_loop.set_exception_handler(ignore_ssl_error)


if __name__ == '__main__':
    startup()
    loop = asyncio.get_event_loop()
    ignore_aiohttp_ssl_error(loop)
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        loop.close()

    print("VandyBot is shutting down...")
