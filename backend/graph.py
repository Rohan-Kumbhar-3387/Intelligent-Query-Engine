from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from database import db_manager
from validator import validate_read_only_sql, SQLSecurityError
from llm_service import (
    supervisor_agent,
    data_engineer_agent,
    analyst_agent,
    bi_visualizer_agent,
    critic_auditor_agent
)


# 1. SHARED STATE (WITH THREAD MEMORY & HITL APPROVAL)
class MultiAgentState(TypedDict):
    question: str
    schema_str: str
    history: List[Dict[str, str]]    # Conversational memory: user & assistant turns
    route: str
    sql: str
    approved_sql: Optional[str]      # Injected or edited by Human-in-the-Loop
    awaiting_approval: bool          # Flags Streamlit to request human review
    error: Optional[str]
    rows: List[Dict[str, Any]]
    columns: List[str]
    chart_config: Dict[str, Any]
    summary: str
    retry_count: int
    max_retries: int
    success: bool
    agent_trail: List[str]


def format_history_context(history: List[Dict[str, Any]]) -> str:
    if not history:
        return ""
    lines = []
    for turn in history[-6:]:
        role = turn.get("role", "user").capitalize()
        content = turn.get("content", "")
        sql = turn.get("sql")
        if sql:
            lines.append(f"{role}: {content} (SQL: {sql})")
        else:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


# 2. AGENT NODES
def supervisor_node(state: MultiAgentState) -> Dict[str, Any]:
    history_context = format_history_context(state.get("history", []))
    route = supervisor_agent(state["question"], state["schema_str"], history_context=history_context)
    trail = state.get("agent_trail", []) + [f"Supervisor -> {route}"]
    return {"route": route, "agent_trail": trail}


def data_engineer_node(state: MultiAgentState) -> Dict[str, Any]:
    history_context = format_history_context(state.get("history", []))
    sql = data_engineer_agent(
        question=state["question"],
        schema_str=state["schema_str"],
        error_context=state.get("error"),
        history_context=history_context
    )
    trail = state.get("agent_trail", []) + ["Data Engineer (SQL Drafter)"]
    return {"sql": sql, "agent_trail": trail}


def analyst_node(state: MultiAgentState) -> Dict[str, Any]:
    history_context = format_history_context(state.get("history", []))
    sql = analyst_agent(
        question=state["question"],
        schema_str=state["schema_str"],
        history_context=history_context
    )
    trail = state.get("agent_trail", []) + ["Data Analyst (Statistical Aggregation)"]
    return {"sql": sql, "agent_trail": trail}


def validate_node(state: MultiAgentState) -> Dict[str, Any]:
    try:
        safe_sql = validate_read_only_sql(state["sql"])
        # Halts workflow and sets awaiting_approval flag for human review
        return {
            "sql": safe_sql,
            "error": None,
            "awaiting_approval": True,
            "agent_trail": state.get("agent_trail", []) + ["AST Security Guard (Passed)"]
        }
    except SQLSecurityError as sec_err:
        return {"error": f"Security violation: {str(sec_err)}", "awaiting_approval": False}
    except Exception as e:
        return {"error": f"SQL syntax error: {str(e)}", "awaiting_approval": False}


def execute_node(state: MultiAgentState) -> Dict[str, Any]:
    # Executes user-approved SQL if edited during human review
    final_sql_to_run = state.get("approved_sql") or state["sql"]
    try:
        safe_sql = validate_read_only_sql(final_sql_to_run)
        rows, columns = db_manager.execute_query(safe_sql)
        trail = state.get("agent_trail", []) + ["Execution Engine (DuckDB)"]
        return {
            "sql": safe_sql,
            "rows": rows,
            "columns": columns,
            "error": None,
            "awaiting_approval": False,
            "agent_trail": trail
        }
    except Exception as exec_err:
        return {
            "error": str(exec_err),
            "retry_count": state["retry_count"] + 1,
            "awaiting_approval": False
        }


def bi_visualizer_node(state: MultiAgentState) -> Dict[str, Any]:
    chart_cfg = bi_visualizer_agent(state["question"], state["columns"], state["rows"])
    trail = state.get("agent_trail", []) + ["BI Visualizer Agent"]
    return {"chart_config": chart_cfg, "agent_trail": trail}


def critic_auditor_node(state: MultiAgentState) -> Dict[str, Any]:
    summary = critic_auditor_agent(state["question"], state["sql"], state["rows"])
    trail = state.get("agent_trail", []) + ["Critic & Fact-Checker"]
    
    # Update memory history with question, summary, and executed SQL
    updated_history = state.get("history", []) + [
        {"role": "user", "content": state["question"]},
        {"role": "assistant", "content": summary, "sql": state.get("sql")}
    ]
    return {
        "summary": summary,
        "success": True,
        "history": updated_history,
        "agent_trail": trail
    }


# 3. CONDITIONAL ROUTING EDGES
def route_supervisor(state: MultiAgentState) -> str:
    return "analyst" if state.get("route") == "statistical_analysis" else "data_engineer"


def route_after_validate(state: MultiAgentState) -> str:
    # If error encountered during generation/validation, trigger retry loop
    if state.get("error"):
        if state["retry_count"] < state["max_retries"]:
            return "data_engineer"
        return END
    # If valid, exit stage 1 so human can review before execution
    return END


def route_after_execute(state: MultiAgentState) -> str:
    if state.get("error"):
        if state["retry_count"] < state["max_retries"]:
            return "data_engineer"
        return END
    return "bi_visualizer"


# 4. COMPILE STATEGRAPH WITH CHECKPOINTER (MEMORY)
memory = MemorySaver()

# Subgraph A: Plan & Draft SQL (Pauses for Human Approval)
draft_graph = StateGraph(MultiAgentState)
draft_graph.add_node("supervisor", supervisor_node)
draft_graph.add_node("data_engineer", data_engineer_node)
draft_graph.add_node("analyst", analyst_node)
draft_graph.add_node("validate", validate_node)

draft_graph.set_entry_point("supervisor")
draft_graph.add_conditional_edges("supervisor", route_supervisor, {"data_engineer": "data_engineer", "analyst": "analyst"})
draft_graph.add_edge("data_engineer", "validate")
draft_graph.add_edge("analyst", "validate")
draft_graph.add_conditional_edges("validate", route_after_validate, {"data_engineer": "data_engineer", END: END})

compiled_draft_agent = draft_graph.compile(checkpointer=memory)

# Subgraph B: Execute Approved SQL, Chart & Fact-Check
exec_graph = StateGraph(MultiAgentState)
exec_graph.add_node("execute", execute_node)
exec_graph.add_node("data_engineer", data_engineer_node)
exec_graph.add_node("bi_visualizer", bi_visualizer_node)
exec_graph.add_node("critic", critic_auditor_node)

exec_graph.set_entry_point("execute")
exec_graph.add_conditional_edges("execute", route_after_execute, {"data_engineer": "data_engineer", "bi_visualizer": "bi_visualizer", END: END})
exec_graph.add_edge("data_engineer", "execute")
exec_graph.add_edge("bi_visualizer", "critic")
exec_graph.add_edge("critic", END)

compiled_exec_agent = exec_graph.compile(checkpointer=memory)