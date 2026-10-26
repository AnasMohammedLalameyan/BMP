"""The fixed workflow graph: route -> one workflow -> validate. This is NOT an autonomous agent: the router has no tools
and only picks one of the known workflows; the workflow is deterministic code plus at most a bounded number of model
calls; the validation step checks the result's shape before it is returned."""
from __future__ import annotations

from typing import Any, Callable, TypedDict

from langgraph.graph import END, StateGraph

from .llm import invoke_structured
from .masking import mask
from .schemas import Route
from .settings import AiSettings
from .suggest import prompt

WORKFLOWS = ("suggest", "intake", "notice", "ask")
REQUIRED = {"suggest": {"fields", "agenda"}, "intake": {"register", "fields", "missing"},
            "notice": {"subject", "notice", "recipients"}, "ask": {"declined", "answer"}, "other": {"redirect"}}


class State(TypedDict, total=False):
    settings: AiSettings
    intent: str | None
    text: str
    handlers: dict[str, Callable[[], dict]]
    result: dict
    error: str | None


def _route(state: State) -> State:
    if state.get("intent") in WORKFLOWS:
        return {}
    masked, _ = mask((state.get("text") or "")[:1000])
    out = invoke_structured(state["settings"], "fast", prompt("route_v1.txt"), masked, Route)
    return {"intent": out.intent}


def _pick(state: State) -> str:
    return state["intent"] if state.get("intent") in WORKFLOWS else "other"


def _node(name: str):
    def run(state: State) -> State:
        return {"result": state["handlers"][name]()}
    return run


def _other(state: State) -> State:
    return {"result": {"redirect": "ask" if state.get("intent") == "ask" else None}}


def _validate(state: State) -> State:
    intent = state.get("intent") if state.get("intent") in WORKFLOWS else "other"
    missing = REQUIRED[intent] - set(state.get("result") or {})
    return {"error": f"incomplete result: {sorted(missing)}" if missing else None}


def _build():
    g = StateGraph(State)
    g.add_node("route", _route)
    for name in WORKFLOWS:
        g.add_node(name, _node(name))
    g.add_node("other", _other)
    g.add_node("validate", _validate)
    g.set_entry_point("route")
    g.add_conditional_edges("route", _pick, {**{n: n for n in WORKFLOWS}, "other": "other"})
    for name in (*WORKFLOWS, "other"):
        g.add_edge(name, "validate")
    g.add_edge("validate", END)
    return g.compile()


_graph = None


def run(settings: AiSettings, intent: str | None, handlers: dict[str, Callable[[], dict]], text: str = "") -> dict[str, Any]:
    global _graph
    if _graph is None:
        _graph = _build()
    final = _graph.invoke({"settings": settings, "intent": intent, "text": text, "handlers": handlers})
    if final.get("error"):
        raise RuntimeError(final["error"])
    return {"intent": final.get("intent"), "result": final["result"]}
