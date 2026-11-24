"""Graded API: POST /chat and GET /health. Both open, no login."""
import os
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore
from pydantic import BaseModel
from app.agent import build_agent
from app.context import AdContext
from app.db import get_pool, q

pool = get_pool()
saver, store = PostgresSaver(pool), PostgresStore(pool)
saver.setup(); store.setup()
agent = build_agent(saver, store)

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class Chat(BaseModel):
    user_id: str
    thread_id: str
    message: str

@app.get("/health")
def health():
    return "ok"

def summarize_turn(msgs):
    i = max((k for k, m in enumerate(msgs) if isinstance(m, HumanMessage)), default=-1)
    new = msgs[i + 1:]
    results = {m.tool_call_id: str(m.content)[:300] for m in new if isinstance(m, ToolMessage)}
    calls = [{"name": c["name"], "args": c["args"], "result": results.get(c["id"], "")} for m in new if isinstance(m, AIMessage) for c in m.tool_calls]
    tin = sum((m.usage_metadata or {}).get("input_tokens", 0) for m in new if isinstance(m, AIMessage))
    tout = sum((m.usage_metadata or {}).get("output_tokens", 0) for m in new if isinstance(m, AIMessage))
    reply = next((m.text for m in reversed(new) if isinstance(m, AIMessage) and m.text), "Sorry, I have no reply.")
    return reply, calls, {"in": tin, "out": tout}

@app.post("/chat")
def chat(b: Chat):
    uid = b.user_id.strip()[:64]
    tid = f"{uid}:{b.thread_id.strip()[:64]}"   # namespaced: a thread can never be shared across users
    try:
        out = agent.invoke({"messages": [{"role": "user", "content": b.message[:2000]}]},
                           {"configurable": {"thread_id": tid}}, context=AdContext(user_id=uid))
        reply, calls, tokens = summarize_turn(out["messages"])
    except Exception:
        import traceback; traceback.print_exc()
        return {"reply": "Sorry, something went wrong. Please try again.", "tool_calls": [], "tokens": {"in": 0, "out": 0}}
    try:
        q("insert into chat_log(user_id,thread_id,user_msg,reply,tin,tout) values(%s,%s,%s,%s,%s,%s)", (uid, tid, b.message[:500], reply[:1000], tokens["in"], tokens["out"]))
    except Exception:
        pass
    return {"reply": reply, "tool_calls": calls, "tokens": tokens}

@app.get("/campaigns/{user_id}")
def campaigns(user_id: str):
    cs = q("select * from campaigns where user_id=%s order by id desc limit 50", (user_id,))
    for c in cs:
        c["variants"] = q("select label,headline,body,cta,impressions,clicks,conversions from variants where campaign_id=%s order by label", (c["id"],))
    return cs

@app.get("/admin/overview")
def admin(x_admin_key: str = Header("")):
    if not os.environ.get("ADMIN_KEY") or x_admin_key != os.environ["ADMIN_KEY"]:
        raise HTTPException(401)
    return {"stats": q("select count(distinct user_id) users,count(*) turns,coalesce(sum(tin),0) tin,coalesce(sum(tout),0) tout from chat_log", one=True),
            "campaigns": q("select c.id,c.user_id,c.name,c.platform,c.status,count(v.id) variants,coalesce(sum(v.clicks),0) clicks from campaigns c left join variants v on v.campaign_id=c.id group by c.id order by c.id desc limit 100"),
            "recent": q("select user_id,user_msg,reply,ts from chat_log order by id desc limit 20")}
