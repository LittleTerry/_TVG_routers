import os
import asyncio

from aiohttp import web
import folder_paths
import server

import logging

logger = logging.getLogger(__name__)

# 直接获取路由实例
routes = server.PromptServer.instance.routes
prompt_queue = server.PromptServer.instance.prompt_queue

def _select_prompt_ids(queue: list) -> list[str]:
    """
    Select prompt_id (index 1) from queue item tuples.
    """
    return [
        item[1]
        for item in queue
        if len(item) > 1 and item[1] is not None
    ]

@routes.get("/queue/prompt_ids")
async def get_queue_prompt_ids(request):
    queue_info = {}
    current_queue = prompt_queue.get_current_queue_volatile()
    queue_info['queue_running'] = _select_prompt_ids(current_queue[0])
    queue_info['queue_pending'] = _select_prompt_ids(current_queue[1])
    return web.json_response(queue_info)
