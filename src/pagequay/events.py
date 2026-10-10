import asyncio
import time
from collections import defaultdict


class Events:
    def __init__(self):
        self.subscribers = defaultdict(set)

    def subscribe(self, project_id):
        queue = asyncio.Queue(maxsize=100)
        self.subscribers[project_id].add(queue)
        return queue

    def unsubscribe(self, project_id, queue):
        self.subscribers[project_id].discard(queue)
        if not self.subscribers[project_id]:
            self.subscribers.pop(project_id, None)

    def emit(self, project, event, **fields):
        value = {"event": event, "project": project["slug"], "at": time.time(), **fields}
        for queue in self.subscribers.get(project["id"], ()):
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(value)
