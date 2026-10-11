import io
import time
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sys
import os

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from auth import (
    register_user,
    authenticate_user,
    create_session,
    get_user_from_session,
    destroy_session,
    save_chat_turn,
    get_chat_history,
    clear_chat_history,
)
from database import db_manager
from graph import compiled_draft_agent, compiled_exec_agent
from validator import check_query_needs_review

app = FastAPI(title="QueryPilot Full Multi-Agent Engine", version="4.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request Models ---

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    full_name: Optional[str] = ""


class LoginRequest(BaseModel):
    username_or_email: str
    password: str


class QueryRequest(BaseModel):
    question: str
    thread_id: Optional[str] = None
    history: Optional[List[Dict[str, Any]]] = None


class DraftRequest(BaseModel):
    question: str
    thread_id: Optional[str] = None
    history: Optional[List[Dict[str, Any]]] = None


class ExecuteApprovalRequest(BaseModel):
    thread_id: str
    question: str
    approved_sql: str
    history: Optional[List[Dict[str, str]]] = []
    agent_trail: Optional[List[str]] = []


# --- Session Authentication Dependency ---

def get_current_user(authorization: Optional[str] = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required. Please log in.")
    token = authorization.split(" ", 1)[1].strip()
    user = get_user_from_session(token)
    if not user:
        raise HTTPException(status_code=401, detail="Session expired or invalid. Please log in again.")
    return user


# --- Health & Auth Endpoints ---

@app.get("/")
def root():
    return {"status": "ok", "service": "QueryPilot Engine", "health": "/health", "docs": "/docs"}


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "QueryPilot Engine"}


@app.post("/auth/register")
def register(request: RegisterRequest):
    user, err = register_user(
        username=request.username,
        email=request.email,
        password=request.password,
        full_name=request.full_name or ""
    )
    if err:
        raise HTTPException(status_code=400, detail=err)

    token = create_session(user["id"])
    return {
        "status": "success",
        "message": "User registered successfully.",
        "token": token,
        "user": user
    }


@app.post("/auth/login")
def login(request: LoginRequest):
    user, err = authenticate_user(
        login_identifier=request.username_or_email,
        password=request.password
    )
    if err:
        raise HTTPException(status_code=401, detail=err)

    token = create_session(user["id"])
    return {
        "status": "success",
        "message": "Login successful.",
        "token": token,
        "user": user
    }


@app.get("/auth/me")
def get_current_user_profile(user: dict = Depends(get_current_user)):
    return {"status": "success", "user": user}


@app.post("/auth/logout")
def logout(authorization: Optional[str] = Header(default=None)):
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1].strip()
        destroy_session(token)
    return {"status": "success", "message": "Logged out successfully."}


@app.get("/history")
def get_user_history(
    thread_id: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    active_thread = thread_id or f"user_{user['id']}_default"
    history = get_chat_history(user["id"], active_thread)
    return {"status": "success", "thread_id": active_thread, "history": history}


@app.delete("/history")
def clear_user_history(
    thread_id: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    active_thread = thread_id or f"user_{user['id']}_default"
    clear_chat_history(user["id"], active_thread)
    return {"status": "success", "message": "History cleared successfully."}


# --- Data & Query Endpoints (Protected) ---

@app.post("/upload")
async def upload_csv(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user)
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")
    
    contents = await file.read()
    try:
        summary = db_manager.load_csv(io.BytesIO(contents))
        return {"status": "success", "dataset_info": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process CSV: {str(e)}")


@app.post("/query")
def run_direct_query(
    request: QueryRequest,
    user: dict = Depends(get_current_user)
):
    start_time = time.time()
    schema_str = db_manager.get_schema_str()

    if not schema_str.strip():
        raise HTTPException(status_code=400, detail="No dataset loaded. Upload a CSV first.")

    active_thread = request.thread_id or f"user_{user['id']}_default"

    # Load persistent conversational memory across sessions if not passed explicitly
    if request.history is not None:
        conversation_history = request.history
    else:
        conversation_history = get_chat_history(user["id"], active_thread)

    # Step 1: Draft and validate
    draft_state = {
        "question": request.question,
        "schema_str": schema_str,
        "history": conversation_history,
        "route": "",
        "sql": "",
        "approved_sql": None,
        "awaiting_approval": False,
        "error": None,
        "rows": [],
        "columns": [],
        "chart_config": {},
        "summary": "",
        "retry_count": 0,
        "max_retries": 3,
        "success": False,
        "agent_trail": []
    }

    config = {"configurable": {"thread_id": active_thread}}
    draft_res = compiled_draft_agent.invoke(draft_state, config=config)

    if draft_res.get("error"):
        raise HTTPException(status_code=422, detail=draft_res["error"])

    # Human-in-the-Loop check: Detect queries requiring additional review
    needs_review, reason = check_query_needs_review(draft_res["sql"])
    if needs_review:
        return {
            "status": "awaiting_approval",
            "requires_review": True,
            "review_reason": reason,
            "sql": draft_res["sql"],
            "agent_trail": draft_res.get("agent_trail", []) + [f"Review Guard ({reason})"],
            "thread_id": active_thread,
            "question": request.question
        }

    # Step 2: Execute, chart, and audit
    exec_state = {
        "question": request.question,
        "schema_str": schema_str,
        "history": conversation_history,
        "route": draft_res.get("route", ""),
        "sql": draft_res["sql"],
        "approved_sql": draft_res["sql"],
        "awaiting_approval": False,
        "error": None,
        "rows": [],
        "columns": [],
        "chart_config": {},
        "summary": "",
        "retry_count": 0,
        "max_retries": 3,
        "success": False,
        "agent_trail": draft_res.get("agent_trail", [])
    }

    final_res = compiled_exec_agent.invoke(exec_state, config=config)
    latency = round(time.time() - start_time, 3)

    if not final_res.get("success"):
        raise HTTPException(
            status_code=422,
            detail=f"Execution halted. Error: {final_res.get('error')}"
        )

    # Persist turns into SQLite conversation memory
    save_chat_turn(user["id"], active_thread, "user", request.question)
    save_chat_turn(user["id"], active_thread, "assistant", final_res["summary"], sql=final_res["sql"])

    return {
        "status": "success",
        "sql": final_res["sql"],
        "summary": final_res["summary"],
        "columns": final_res["columns"],
        "rows": final_res["rows"],
        "row_count": len(final_res["rows"]),
        "chart_config": final_res["chart_config"],
        "agent_trail": final_res["agent_trail"],
        "attempts_needed": final_res.get("retry_count", 0) + 1,
        "latency_seconds": latency,
        "thread_id": active_thread,
        "history": final_res.get("history", [])
    }


@app.post("/draft_query")
def draft_query(
    request: DraftRequest,
    user: dict = Depends(get_current_user)
):
    schema_str = db_manager.get_schema_str()
    if not schema_str.strip():
        raise HTTPException(status_code=400, detail="No dataset loaded. Upload a CSV first.")

    active_thread = request.thread_id or f"user_{user['id']}_default"
    history = request.history if request.history is not None else get_chat_history(user["id"], active_thread)

    initial_state = {
        "question": request.question,
        "schema_str": schema_str,
        "history": history,
        "route": "",
        "sql": "",
        "approved_sql": None,
        "awaiting_approval": False,
        "error": None,
        "rows": [],
        "columns": [],
        "chart_config": {},
        "summary": "",
        "retry_count": 0,
        "max_retries": 3,
        "success": False,
        "agent_trail": []
    }

    config = {"configurable": {"thread_id": active_thread}}
    final_state = compiled_draft_agent.invoke(initial_state, config=config)

    if final_state.get("error"):
        raise HTTPException(status_code=422, detail=final_state["error"])

    return {
        "status": "awaiting_approval",
        "sql": final_state["sql"],
        "agent_trail": final_state.get("agent_trail", []),
        "thread_id": active_thread
    }


@app.post("/execute_approved")
def execute_approved(
    request: ExecuteApprovalRequest,
    user: dict = Depends(get_current_user)
):
    start_time = time.time()
    schema_str = db_manager.get_schema_str()

    execution_state = {
        "question": request.question,
        "schema_str": schema_str,
        "history": request.history or [],
        "route": "",
        "sql": request.approved_sql,
        "approved_sql": request.approved_sql,
        "awaiting_approval": False,
        "error": None,
        "rows": [],
        "columns": [],
        "chart_config": {},
        "summary": "",
        "retry_count": 0,
        "max_retries": 3,
        "success": False,
        "agent_trail": request.agent_trail or []
    }

    config = {"configurable": {"thread_id": request.thread_id}}
    final_state = compiled_exec_agent.invoke(execution_state, config=config)
    latency = round(time.time() - start_time, 3)

    if not final_state.get("success"):
        raise HTTPException(
            status_code=422,
            detail=f"Execution halted. Error: {final_state.get('error')}"
        )

    save_chat_turn(user["id"], request.thread_id, "user", request.question)
    save_chat_turn(user["id"], request.thread_id, "assistant", final_state["summary"], sql=final_state["sql"])

    return {
        "status": "completed",
        "sql": final_state["sql"],
        "summary": final_state["summary"],
        "columns": final_state["columns"],
        "rows": final_state["rows"],
        "row_count": len(final_state["rows"]),
        "chart_config": final_state["chart_config"],
        "agent_trail": final_state["agent_trail"],
        "history": final_state["history"],
        "latency_seconds": latency
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)