# examples/a2a_live_roundtrip.py — needs: pip install hebom-buffer "a2a-sdk[http-server]" httpx uvicorn
"""Live A2A server round trip: the same messageId sent twice over JSON-RPC.
Counts how many times the (expensive) agent actually ran."""
import asyncio, threading, uuid, json, time
import uvicorn, httpx
from starlette.applications import Starlette
import a2a.types as T
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.server.routes.jsonrpc_routes import create_jsonrpc_routes
from a2a.server.routes.agent_card_routes import create_agent_card_routes
from a2a_guarded_executor import GuardedExecutor

class CountingAgent(AgentExecutor):
    """Stands in for the model call. Every run here would be a real LLM bill."""
    runs = 0
    async def execute(self, ctx: RequestContext, q: EventQueue) -> None:
        CountingAgent.runs += 1
        await q.enqueue_event(T.Message(message_id=str(uuid.uuid4()), role=T.Role.ROLE_AGENT,
                                        parts=[T.Part(text=f"agent ran (#{CountingAgent.runs})")]))
    async def cancel(self, ctx, q): pass

def build(guarded: bool, port: int):
    card = T.AgentCard(name="demo", description="hebom guard demo", version="0.0.1",
                       capabilities=T.AgentCapabilities(streaming=False),
                       default_input_modes=["text/plain"], default_output_modes=["text/plain"],
                       skills=[T.AgentSkill(id="echo", name="echo", description="echo", tags=["demo"])],
                       supported_interfaces=[T.AgentInterface(url=f"http://127.0.0.1:{port}/", protocol_binding="JSONRPC", protocol_version="1.0")])
    ex = GuardedExecutor(CountingAgent()) if guarded else CountingAgent()
    h = DefaultRequestHandler(agent_executor=ex, task_store=InMemoryTaskStore(), agent_card=card)
    app = Starlette(routes=create_agent_card_routes(card) + create_jsonrpc_routes(h, "/"))
    return app, ex

def serve(app, port):
    cfg = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    srv = uvicorn.Server(cfg); threading.Thread(target=srv.run, daemon=True).start(); time.sleep(1.0); return srv

def send(port, mid):
    body = {"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": "SendMessage",
            "params": {"message": {"messageId": mid, "role": "ROLE_USER", "parts": [{"text": "charge the card"}]}}}
    r = httpx.post(f"http://127.0.0.1:{port}/", json=body, timeout=10, headers={"A2A-Version": "1.0"})
    j = r.json()
    res = j.get("result", j)
    txt = None
    try:
        m = res.get("message") or res.get("task", {}).get("status", {}).get("message") or {}
        txt = (m.get("parts") or [{}])[0].get("text")
    except Exception: pass
    return r.status_code, txt, json.dumps(j)[:160]

if __name__ == "__main__":
    for guarded, port in ((False, 41001), (True, 41002)):
        CountingAgent.runs = 0
        app, ex = build(guarded, port); serve(app, port)
        card = httpx.get(f"http://127.0.0.1:{port}/.well-known/agent-card.json").json()
        mid = "msg-" + uuid.uuid4().hex[:8]
        print("=" * 78)
        print(f"  {'WITH hebom guard' if guarded else 'plain a2a-sdk'}   agent card: {card.get('name')} v{card.get('version')}   port {port}")
        print("=" * 78)
        for i in (1, 2):
            code, txt, raw = send(port, mid)
            print(f"  send #{i}  messageId={mid}  HTTP {code}  ->  {txt or raw}")
        print(f"  agent (model call) ran: {CountingAgent.runs}x" + (f"   refused by guard: {ex.refused}" if guarded else ""))
        print()
