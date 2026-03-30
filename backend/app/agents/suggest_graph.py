"""
LangGraph tool calling 기반 문장 제안 그래프.

흐름:
  analysis_node (LLM에 3개 툴 바인딩)
    → ToolNode (선택된 툴 실행)
    → aggregate_node (툴 결과 수집 후 최종 출력)

LLM 동작:
  1. 입력 문장의 어조 감지 (formal / neutral / informal)
  2. report_analysis 호출 (어조 + 문법 교정)
  3. 추천 convert 툴 호출:
     - formal  → convert_informal 1개
     - informal → convert_formal 1개
     - neutral  → convert_formal + convert_informal 2개
  사용자에게 추천하는 어조는 formal/informal 두 가지만.
  neutral은 어조 판단 기준으로만 사용.
"""

from __future__ import annotations

import json
from typing import Annotated, Any
from typing_extensions import TypedDict

from langchain_core.messages import AIMessage, ToolMessage, SystemMessage, HumanMessage
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


TOOLS = [report_analysis, convert_formal, convert_informal]

# ─── LLM ────────────────────────────────────────────────────────────────────

def _make_llm():
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
    return llm.bind_tools(TOOLS)


SYSTEM_PROMPT = """You are an English language coach. Given a target sentence, you must:

1. Detect the tone: one of 'formal', 'neutral', or 'informal'.
   - formal:   appropriate for official, professional, or public contexts. Polite and structured.
               Does NOT require complex vocabulary — simple words used formally count (e.g. "I would like to" vs "I want to").
   - informal: casual, conversational, for friends or familiar settings.
   - neutral:  neither clearly formal nor clearly informal. Sits between the two.

2. Check for grammar errors and correct them.

3. Call report_analysis with: tone, corrected text, whether there were grammar errors, and a list of changes.

4. Call convert tools based on the detected tone:
   - formal   → call convert_informal only
   - informal → call convert_formal only
   - neutral  → call convert_formal AND convert_informal

   neutral is used only for classification — do NOT produce a neutral variant as output.

You MUST call report_analysis in every response.
Use the corrected text (not the original) as the input for the convert tools.

Conversion guidelines — the two variants MUST sound clearly different from each other and from the original:

formal:
  - Polite, structured, appropriate for official or professional situations
  - No contractions ("I am" not "I'm", "do not" not "don't")
  - Measured phrasing: "I would like to", "Could you please", "I appreciate"
  - Avoid slang, filler words, and abrupt phrasing
  - Vocabulary can be simple — formality is about tone and structure, not complexity

informal:
  - Casual, warm, natural for conversation with friends or familiar people
  - Contractions and colloquial expressions encouraged
  - Shorter, spoken-rhythm sentences ("Hey, can you help me out?", "Sounds good!")
  - Filler words like "kind of", "basically", "honestly" are fine
  - Slang is acceptable if natural"""


# ─── Nodes ──────────────────────────────────────────────────────────────────

def analysis_node(state: SuggestState) -> dict:
    llm = _make_llm()
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
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


# ─── Routing ────────────────────────────────────────────────────────────────

def should_use_tools(state: SuggestState) -> str:
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return "aggregate"


# ─── Graph ──────────────────────────────────────────────────────────────────

def build_suggest_graph():
    tool_node = ToolNode(TOOLS)

    graph = StateGraph(SuggestState)
    graph.add_node("analysis", analysis_node)
    graph.add_node("tools", tool_node)
    graph.add_node("aggregate", aggregate_node)

    graph.set_entry_point("analysis")
    graph.add_conditional_edges("analysis", should_use_tools, {
        "tools": "tools",
        "aggregate": "aggregate",
    })
    graph.add_edge("tools", "aggregate")
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
