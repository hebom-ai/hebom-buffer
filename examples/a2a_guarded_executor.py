"""hebom-buffer × a2a-sdk — guard an A2A AgentExecutor against duplicate messageId.

One wrapper. The inner executor runs once per messageId; the second delivery
of the same messageId is refused before any model call happens.
A2A §3.3.1 says agents MAY use messageId for this. This is one implementation of that MAY.
"""
import uuid
from hebom import Room
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
import a2a.types as T


class GuardedExecutor(AgentExecutor):
    def __init__(self, inner: AgentExecutor, room: Room | None = None):
        self.inner = inner
        self.room = room or Room()
        self.refused = 0

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        mid = context.message.message_id if context.message else None
        verdict = self.room.pass_({"seen": True}, event_id=mid or str(uuid.uuid4()))
        self.room.take()  # the buffer's memory of the id is what we use; drain the slot
        if verdict["code"] == "DUPLICATE":
            self.refused += 1
            await event_queue.enqueue_event(T.Message(
                message_id=str(uuid.uuid4()), role=T.Role.ROLE_AGENT,
                parts=[T.Part(text=f"REFUSED: duplicate messageId {mid} — executor did not run")]))
            return
        await self.inner.execute(context, event_queue)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        await self.inner.cancel(context, event_queue)
