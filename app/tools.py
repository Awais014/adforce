"""Every tool reads the user from runtime.context, never from a model argument (user isolation)."""
import json
from hashlib import sha1
from pydantic import BaseModel
from langchain.tools import ToolRuntime, tool
from app.context import AdContext
from app.db import q

def _owns(uid, cid):
    return q("select * from campaigns where id=%s and user_id=%s", (cid, uid), one=True)

class Variant(BaseModel):
    label: str      # "A", "B" or "C"
    headline: str
    body: str
    cta: str

@tool
def create_campaign(name: str, product: str, platform: str, variants: list[Variant], runtime: ToolRuntime[AdContext]) -> str:
    """Save a draft campaign with 2-3 ad variants. Every variant needs label (A/B/C), headline, body and cta."""
    uid = runtime.context.user_id
    c = q("insert into campaigns(user_id,name,product,platform) values(%s,%s,%s,%s) returning id", (uid, name, product, platform), one=True)
    saved = []
    for v in variants[:5]:
        v = v if isinstance(v, dict) else v.model_dump()
        q("insert into variants(campaign_id,label,headline,body,cta) values(%s,%s,%s,%s,%s)",
          (c["id"], v.get("label"), v.get("headline"), v.get("body"), v.get("cta")))
        saved.append(f"{v.get('label')}: {v.get('headline')}")
    return f"Campaign {c['id']} saved as draft with {len(saved)} variants. " + " | ".join(saved)

@tool
def record_results(campaign_id: int, label: str, impressions: int, clicks: int, conversions: int, runtime: ToolRuntime[AdContext]) -> str:
    """Record A/B results (impressions, clicks, conversions) for one variant label of a campaign."""
    if not _owns(runtime.context.user_id, campaign_id):
        return "Campaign not found."
    q("update variants set impressions=%s,clicks=%s,conversions=%s where campaign_id=%s and label=%s",
      (impressions, clicks, conversions, campaign_id, label))
    return f"Recorded results for variant {label}."

@tool
def get_ab_report(campaign_id: int, runtime: ToolRuntime[AdContext]) -> str:
    """Get CTR and conversions per variant plus the winner (needs 100+ impressions)."""
    if not _owns(runtime.context.user_id, campaign_id):
        return "Campaign not found."
    rows = q("select label,headline,impressions,clicks,conversions from variants where campaign_id=%s order by label", (campaign_id,))
    for r in rows:
        r["ctr_pct"] = round(100 * r["clicks"] / r["impressions"], 2) if r["impressions"] else 0
    ok = [r for r in rows if r["impressions"] >= 100]
    return json.dumps({"variants": rows, "winner": max(ok, key=lambda r: r["ctr_pct"])["label"] if ok else "none yet"})

@tool
def list_campaigns(runtime: ToolRuntime[AdContext]) -> str:
    """List this user's campaigns."""
    rows = q("select id,name,platform,status from campaigns where user_id=%s order by id desc limit 20", (runtime.context.user_id,))
    return json.dumps(rows) if rows else "No campaigns yet."

@tool
def publish_campaign(campaign_id: int, runtime: ToolRuntime[AdContext]) -> str:
    """Publish a campaign (risky). First call only requests confirmation; call again after the user explicitly says yes."""
    c = _owns(runtime.context.user_id, campaign_id)
    if not c:
        return "Campaign not found."
    if c["status"] == "pending_publish":
        q("update campaigns set status='published' where id=%s", (campaign_id,))
        return f"Campaign {campaign_id} published."
    q("update campaigns set status='pending_publish' where id=%s", (campaign_id,))
    return "NOT published yet. Ask the user to confirm explicitly (yes) before calling again."

@tool
def remember(fact: str, runtime: ToolRuntime[AdContext]) -> str:
    """Save a lasting fact about the user's brand (tone, audience, product, platform preference)."""
    runtime.store.put(("memories", runtime.context.user_id), sha1(fact.encode()).hexdigest()[:16], {"fact": fact[:300]})
    return f"Remembered: {fact}"

TOOLS = [create_campaign, record_results, get_ab_report, list_campaigns, publish_campaign, remember]