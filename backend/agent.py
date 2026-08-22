from typing import Literal, TypedDict

from ddgs import DDGS
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from pydantic import BaseModel

from ingest import search
from tools import ToolPick, log_tool, select_tool


class Grade(BaseModel):
    relevant: bool
    reason: str


class AgentState(TypedDict):
    query: str
    retrieved_docs: list
    grade: dict
    final_answer: str
    tool_used: str
    path_taken: str
    web_context: str


def format_docs(docs):
    if not docs:
        return "(no docs)"
    lines = []
    for i, d in enumerate(docs, 1):
        lines.append(
            f"[{i}] repo={d.get('repo')} type={d.get('event_type')} "
            f"ts={d.get('timestamp')} score={d.get('score', 0):.3f}\n{d.get('text', '')}"
        )
    return "\n\n".join(lines)


def retrieve(state: AgentState) -> dict:
    docs = search(state["query"], k=5)
    return {"retrieved_docs": docs}


def grade(state: AgentState) -> dict:
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    prompt = PromptTemplate.from_template(
        """Judge whether these retrieved GitHub event logs help answer the incident query.
relevant=true only if the docs contain concrete signal about the repos/events asked.
If docs are empty, off-topic, or too weak, relevant=false.

Query: {query}

Docs:
{docs}

Return relevant and reason."""
    )
    chain = prompt | llm.with_structured_output(Grade)
    g = chain.invoke({"query": state["query"], "docs": format_docs(state["retrieved_docs"])})
    return {"grade": {"relevant": g.relevant, "reason": g.reason}}


def route_grade(state: AgentState) -> Literal["answer", "fallback"]:
    if state.get("grade", {}).get("relevant"):
        return "answer"
    return "fallback"


def answer(state: AgentState) -> dict:
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
    prompt = PromptTemplate.from_template(
        """You are an incident response analyst using live GitHub public event logs.
Answer using ONLY the docs below. Be specific about repos, event types, actors, times.
If recommending an ops action, say "recommend" — never claim you executed anything.
Keep it concise.

Query: {query}

Docs:
{docs}

Answer:"""
    )
    chain = prompt | llm | StrOutputParser()
    text = chain.invoke({"query": state["query"], "docs": format_docs(state["retrieved_docs"])})
    return {"final_answer": text, "path_taken": "direct"}


def fallback(state: AgentState) -> dict:
    q = state["query"]
    snippets = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(q + " github ci failure", max_results=5):
                snippets.append(f"{r.get('title', '')}: {r.get('body', '')}")
    except Exception as e:
        snippets.append(f"web search failed: {e}")

    web = "\n".join(snippets) if snippets else "(no web results)"
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
    prompt = PromptTemplate.from_template(
        """Local GitHub event logs did not explain this incident well.
Use the web search context plus any local docs to answer.
Say clearly that local retrieval was weak and you used external context.
Recommend actions only — never claim execution.

Query: {query}

Local docs:
{docs}

Web context:
{web}

Answer:"""
    )
    chain = prompt | llm | StrOutputParser()
    text = chain.invoke(
        {
            "query": q,
            "docs": format_docs(state.get("retrieved_docs") or []),
            "web": web,
        }
    )
    return {"final_answer": text, "path_taken": "fallback", "web_context": web}


def pick_tool(state: AgentState) -> dict:
    pick: ToolPick = select_tool(state["final_answer"])
    name = log_tool(pick)
    return {"tool_used": name}


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("retrieve", retrieve)
    g.add_node("grade", grade)
    g.add_node("answer", answer)
    g.add_node("fallback", fallback)
    g.add_node("pick_tool", pick_tool)

    g.set_entry_point("retrieve")
    g.add_edge("retrieve", "grade")
    g.add_conditional_edges("grade", route_grade, {"answer": "answer", "fallback": "fallback"})
    g.add_edge("answer", "pick_tool")
    g.add_edge("fallback", "pick_tool")
    g.add_edge("pick_tool", END)
    return g.compile()


graph = build_graph()


def run_agent(q: str) -> dict:
    init: AgentState = {
        "query": q,
        "retrieved_docs": [],
        "grade": {},
        "final_answer": "",
        "tool_used": "none",
        "path_taken": "direct",
        "web_context": "",
    }
    out = graph.invoke(init)
    return {
        "answer": out.get("final_answer", ""),
        "path_taken": out.get("path_taken", "direct"),
        "tool_used": out.get("tool_used", "none"),
        "grade_reason": (out.get("grade") or {}).get("reason", ""),
        "retrieved_docs": out.get("retrieved_docs") or [],
        "grade_relevant": (out.get("grade") or {}).get("relevant", False),
        "web_context": out.get("web_context", ""),
    }
