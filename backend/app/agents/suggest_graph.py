"""
LangGraph tool calling 기반 문장 제안 그래프.

흐름:
  analysis_node (LLM — report_analysis만 바인딩)
    → report_tools (report_analysis 실행)
    → dispatch_node (tone 읽어서 convert 툴 결정 — 코드로)
    → convert_tools (convert_formal / convert_informal 실행)
    → aggregate_node (툴 결과 수집 후 최종 출력)

LLM 동작:
  1. 입력 문장의 어조 감지 (formal / neutral / informal)
  2. report_analysis 호출 (어조 + 문법 교정)

dispatch_node 동작 (코드):
  - formal   → convert_informal 호출
  - informal → convert_formal 호출
  - neutral  → convert_formal + convert_informal 호출
"""

from __future__ import annotations

import json
from typing import Annotated, Any
from typing_extensions import TypedDict

from langchain_core.messages import ToolMessage, SystemMessage, HumanMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode


# ─── State ──────────────────────────────────────────────────────────────────

class SuggestState(TypedDict):
    messages: Annotated[list, lambda x, y: x + y]
    tool_results: dict[str, Any]


# ─── Tools ──────────────────────────────────────────────────────────────────

@tool
def report_analysis(
    tone: str,
    corrected_text: str,
    has_grammar_error: bool,
    changes: list[str],
) -> str:
    """
    Report the tone classification and grammar correction result.

    Args:
        tone: Detected tone — one of 'formal', 'neutral', 'informal'
        corrected_text: Grammar-corrected version of the input (same as input if no errors)
        has_grammar_error: True if grammar errors were found and corrected
        changes: List of short descriptions of grammar changes made (empty list if none)
    """
    return json.dumps({
        "tone": tone,
        "corrected_text": corrected_text,
        "has_grammar_error": has_grammar_error,
        "changes": changes,
    }, ensure_ascii=False)


@tool
def convert_formal(text: str, changes: list[str]) -> str:
    """
    Convert the input sentence to a formal register suitable for official or public contexts.

    Args:
        text: The converted formal version of the sentence
        changes: List of short descriptions of what was changed to make it formal
    """
    return json.dumps({
        "converted": text,
        "changes": changes,
    }, ensure_ascii=False)


@tool
def convert_informal(text: str, changes: list[str]) -> str:
    """
    Convert the input sentence to an informal/casual register for friendly or familiar contexts.

    Args:
        text: The converted informal version of the sentence
        changes: List of short descriptions of what was changed to make it informal
    """
    return json.dumps({
        "converted": text,
        "changes": changes,
    }, ensure_ascii=False)


REPORT_TOOLS = [report_analysis]
CONVERT_TOOLS = [convert_formal, convert_informal]

# ─── LLM ────────────────────────────────────────────────────────────────────

def _make_analysis_llm():
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
    return llm.bind_tools(REPORT_TOOLS)


def _make_convert_llm():
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
    return llm.bind_tools(CONVERT_TOOLS)


ANALYSIS_PROMPT = """You are an English language coach. Given a target sentence, you must:

1. Detect the tone: one of 'formal', 'neutral', or 'informal'.
   - formal:   appropriate for official, professional, or public contexts. Polite and structured.
               Does NOT require complex vocabulary — simple words used formally count (e.g. "I would like to" vs "I want to").
               e.g. "I would like to request...", "Please be advised...", "I appreciate your assistance."
   - informal: casual, conversational, for friends or familiar settings.
               e.g. "Hey, can you help me out?", "I was thinking maybe we could...", "That sounds good!"
   - neutral:  neither clearly formal nor clearly informal.
               Polite but not stiff. Natural but not casual.
               e.g. "I could say...", "What if we tried...", "That might work."
               Everyday professional or semi-social contexts.

2. Check for grammar errors and correct them.
   Fix only structural errors: subject-verb agreement, tense, articles, prepositions, missing/extra words.
   Do NOT change word choice, phrasing, or style — preserve the user's original expression as much as possible.
   The goal is grammatical correctness, not naturalness.

3. Call report_analysis with: tone, corrected text, whether there were grammar errors, and a list of changes."""

CONVERT_PROMPT = """You are an English language coach converting a sentence to a different register.

Conversion guidelines:
- Keep the original meaning intact — only change tone and structure, not the intent or content
- The converted sentence MUST be clearly different from the input sentence
- For convert_formal: polite, structured, no contractions, measured phrasing ("I would like to", "Could you please")
- For convert_informal: casual, warm, contractions encouraged, spoken-rhythm sentences, colloquial expressions fine"""


# ─── Nodes ──────────────────────────────────────────────────────────────────

def analysis_node(state: SuggestState) -> dict:
    llm = _make_analysis_llm()
    messages = [SystemMessage(content=ANALYSIS_PROMPT)] + state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response]}


def dispatch_node(state: SuggestState) -> dict:
    """tone에 따라 호출할 convert 툴을 코드로 결정."""
    # report_analysis 결과에서 tone과 corrected_text 추출
    tone = "neutral"
    corrected_text = ""
    for msg in state["messages"]:
        if isinstance(msg, ToolMessage) and msg.name == "report_analysis":
            try:
                data = json.loads(msg.content)
                tone = data.get("tone", "neutral")
                corrected_text = data.get("corrected_text", "")
            except (json.JSONDecodeError, TypeError):
                pass

    # tone에 따라 convert 툴 결정
    if tone == "formal":
        tools_to_call = ["convert_informal"]
    elif tone == "informal":
        tools_to_call = ["convert_formal"]
    else:  # neutral
        tools_to_call = ["convert_formal", "convert_informal"]

    llm = _make_convert_llm()
    prompt = f"Convert the following sentence as instructed.\n\nSentence: {corrected_text}"
    tool_names = " and ".join(tools_to_call)
    prompt += f"\n\nCall: {tool_names}"

    messages = [SystemMessage(content=CONVERT_PROMPT), HumanMessage(content=prompt)]
    response = llm.invoke(messages)
    return {"messages": [response]}


def aggregate_node(state: SuggestState) -> dict:
    """Collect ToolMessage results into tool_results dict keyed by tool name."""
    tool_results: dict[str, Any] = {}
    for msg in state["messages"]:
        if isinstance(msg, ToolMessage):
            try:
                tool_results[msg.name] = json.loads(msg.content)
            except (json.JSONDecodeError, TypeError):
                tool_results[msg.name] = msg.content
    return {"tool_results": tool_results}



# ─── Graph ──────────────────────────────────────────────────────────────────

def build_suggest_graph():
    report_tool_node = ToolNode(REPORT_TOOLS)
    convert_tool_node = ToolNode(CONVERT_TOOLS)

    graph = StateGraph(SuggestState)
    graph.add_node("analysis", analysis_node)
    graph.add_node("report_tools", report_tool_node)
    graph.add_node("dispatch", dispatch_node)
    graph.add_node("convert_tools", convert_tool_node)
    graph.add_node("aggregate", aggregate_node)

    graph.set_entry_point("analysis")
    graph.add_edge("analysis", "report_tools")
    graph.add_edge("report_tools", "dispatch")
    graph.add_edge("dispatch", "convert_tools")
    graph.add_edge("convert_tools", "aggregate")
    graph.add_edge("aggregate", END)

    return graph.compile()


# ─── Public API ─────────────────────────────────────────────────────────────

def run_suggest(target_text: str) -> dict:
    """
    Run the suggestion graph and return structured result:
    {
      "tone": "formal"|"neutral"|"informal",
      "corrected_text": str,
      "has_grammar_error": bool,
      "grammar_changes": [...],
      "suggestions": {
        "formal":   {"converted": str, "changes": [...]} | None,
        "informal": {"converted": str, "changes": [...]} | None,
      }
    }
    """
    graph = build_suggest_graph()
    initial_state: SuggestState = {
        "messages": [HumanMessage(content=target_text)],
        "tool_results": {},
    }
    final_state = graph.invoke(initial_state)

    results = final_state.get("tool_results", {})

    analysis = results.get("report_analysis", {})
    tone = analysis.get("tone", "neutral")
    corrected_text = analysis.get("corrected_text", target_text)
    has_grammar_error = analysis.get("has_grammar_error", False)
    grammar_changes = analysis.get("changes", [])

    suggestions = {
        "formal":   results.get("convert_formal"),
        "informal": results.get("convert_informal"),
    }

    return {
        "tone": tone,
        "corrected_text": corrected_text,
        "has_grammar_error": has_grammar_error,
        "grammar_changes": grammar_changes,
        "suggestions": suggestions,
    }
