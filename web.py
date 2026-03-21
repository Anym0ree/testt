import os
from aiohttp import web
import asyncio
import logging

logging.basicConfig(level=logging.INFO)

async def handle(request):
    return web.Response(text="Bot is running")

async def run_web():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logging.info(f"Web server started on port {port}")
    # Бесконечно ждём
    await asyncio.Event().wait()

def start_web():
    loop = asyncio.get_event_loop()
    loop.create_task(run_web())
