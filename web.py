import os
from aiohttp import web
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
_is_ready = False

async def handle(request):
    return web.Response(text="Bot is running")


async def health(request):
    return web.json_response({"status": "ok"})


async def ready(request):
    status = 200 if _is_ready else 503
    return web.json_response({"ready": _is_ready}, status=status)

async def run_web():
    global _is_ready
    app = web.Application()
    app.router.add_get('/', handle)
    app.router.add_get('/healthz', health)
    app.router.add_get('/readyz', ready)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    _is_ready = True
    logging.info(f"Web server started on port {port}")
    try:
        await asyncio.Event().wait()
    finally:
        _is_ready = False
        await runner.cleanup()

def start_web():
    loop = asyncio.get_running_loop()
        return loop.create_task(run_web())


async def stop_web(web_task):
    if not web_task:
        return
    web_task.cancel()
    try:
        await web_task
    except asyncio.CancelledError:
        pass
