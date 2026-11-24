from langchain.agents import create_agent
from app.context import AdContext, make_model
from app.middleware import build_middleware
from app.tools import TOOLS

def build_agent(checkpointer=None, store=None):
    return create_agent(make_model(), tools=TOOLS, context_schema=AdContext, middleware=build_middleware(),
                        checkpointer=checkpointer, store=store)
