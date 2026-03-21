from aiohttp import web
import asyncio
import logging

logging.basicConfig(level=logging.INFO)

async def handle(request):
    return web.Response(text="Bot is running")

async def run_web(app):
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    logging.info("Web server started on port 8080")
    # keep running
    await asyncio.Event().wait()

async def start_web():
    app = web.Application()
    app.router.add_get('/', handle)
    await run_web(app)

if __name__ == "__main__":
    asyncio.run(start_web())