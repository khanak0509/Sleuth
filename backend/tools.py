from typing import Literal

from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
load_dotenv()

from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field


def restart_pod(namespace: str = "default", pod: str = "") -> str:
    return f"[mock] would restart pod={pod} ns={namespace}"


def block_ip(ip: str = "", reason: str = "") -> str:
    return f"[mock] would block ip={ip} reason={reason}"


def rollback_deploy(service: str = "", version: str = "prev") -> str:
    return f"[mock] would rollback service={service} to={version}"


def scale_replica(service: str = "", replicas: int = 2) -> str:
    return f"[mock] would scale service={service} replicas={replicas}"


def page_oncall(severity: str = "sev2", summary: str = "") -> str:
    return f"[mock] would page oncall sev={severity} summary={summary}"


TOOLS = {
    "restart_pod": restart_pod,
    "block_ip": block_ip,
    "rollback_deploy": rollback_deploy,
    "scale_replica": scale_replica,
    "page_oncall": page_oncall,
}

TOOL_DESC = {
    "restart_pod": "Restart a crashed or stuck kubernetes pod",
    "block_ip": "Block a suspicious source IP",
    "rollback_deploy": "Roll back a bad deployment to a prior version",
    "scale_replica": "Scale a service up or down under load",
    "page_oncall": "Page the on-call engineer for human escalation",
    "none": "No infra action needed; investigation only",
}


class ToolPick(BaseModel):
    tool_name: Literal[
        "restart_pod",
        "block_ip",
        "rollback_deploy",
        "scale_replica",
        "page_oncall",
        "none",
    ]
    params: dict = Field(default_factory=dict)
    reason: str = ""


def select_tool(incident: str) -> ToolPick:
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    prompt = PromptTemplate.from_template(
        """You pick ONE mock ops tool for this incident investigation summary.
Tools:
- restart_pod: crashed/stuck pods, OOM restarts, unhealthy containers. params: namespace, pod
- block_ip: abuse, scraping, suspicious IPs. params: ip, reason
- rollback_deploy: bad release, failing after deploy. params: service, version
- scale_replica: traffic spike, overload. params: service, replicas
- page_oncall: needs a human, unclear root cause, sev1/sev2. params: severity, summary
- none: answer-only, no action

Incident:
{incident}

Pick the best tool. Prefer none unless action clearly helps.
If two tools both seem plausible, pick the more defensible primary action
(the one that addresses the stated priority / least blast radius), not both.
Return tool_name, params, reason."""
    )
    # function_calling: OpenAI json_schema rejects open-ended dict params
    chain = prompt | llm.with_structured_output(ToolPick, method="function_calling")
    return chain.invoke({"incident": incident})


def log_tool(pick: ToolPick) -> str:
    if pick.tool_name == "none":
        return "none"
    fn = TOOLS.get(pick.tool_name)
    if not fn:
        return "none"
    try:
        msg = fn(**{k: v for k, v in pick.params.items() if k in fn.__code__.co_varnames})
    except TypeError:
        msg = fn()
    print(f"tool={pick.tool_name} params={pick.params} -> {msg}")
    return pick.tool_name
