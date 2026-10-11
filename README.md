# ⚡ Intelligent Query Engine (QueryPilot)

[![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110.0-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Multi--Agent-orange)](https://github.com/langchain-ai/langgraph)
[![DuckDB](https://img.shields.io/badge/DuckDB-In--Memory%20Analytics-FFF000?logo=duckdb&logoColor=black)](https://duckdb.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.32.2-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

An enterprise-grade, multi-agent analytics engine that translates natural language business questions into safe, executable DuckDB SQL. Powered by **LangGraph**, it autonomously plans, drafts, self-heals, validates, visualizes, and fact-checks analytical queries with persistent conversational memory and **Human-in-the-Loop (HITL)** approval.

---

## 🌟 Key Features

- **🤖 Multi-Agent Orchestration**: Built with **LangGraph** state graphs dividing responsibilities across specialized agents:
  - **Supervisor**: Intelligently classifies user intent into standard SQL or deep statistical exploration.
  - **Data Engineer**: Drafts dialect-specific DuckDB SQL and executes self-healing retries on syntax errors.
  - **Quantitative Analyst**: Formulates wide statistical distributions and multi-dimensional comparisons.
  - **BI Visualizer**: Selects optimal chart representations (bar, line, scatter, pie) and coordinates axis mapping.
  - **Critic & Fact-Checker**: Audits generated summaries against actual raw result rows to eliminate numerical hallucinations.
- **🛡️ AST Security Guardrails**: Enforces Abstract Syntax Tree validation via `SQLGlot` to guarantee strictly read-only statements, blocking destructive DDL/DML (`DROP`, `DELETE`, `UPDATE`, `ALTER`) and multi-statement injection attacks.
- **🤝 Human-in-the-Loop (HITL)**: Automatically detects unbounded full table scans or sensitive attribute queries, pausing execution for human inspection, live SQL modification, and approval.
- **🧠 Persistent Conversational Memory**: Thread-based LangGraph checkpointing backed by SQLite persistence remembers context across sessions, effortlessly resolving multi-turn follow-up queries (e.g., *"What was its total profit?"*).
- **🔒 Secure Authentication & Session Management**: Built-in user registration and login with salted PBKDF2 (SHA-256) password hashing and secure token sessions.
- **📊 Modern Interactive UI**: Responsive Streamlit dashboard styled with custom CSS/HTML, KPI metric cards, execution pipeline breadcrumbs, and interactive Plotly charts.

---

## 🏗️ Architecture

```mermaid
flowchart TD
    User([User Prompt]) --> Auth[Session Auth & Memory Gate]
    Auth --> Sup[Supervisor Agent]
    
    Sup -->|Standard Query| DE[Data Engineer Agent]
    Sup -->|Deep Analysis| QA[Analyst Agent]
    
    DE --> Val{AST Security Guard}
    QA --> Val
    
    Val -->|Dangerous Query| Block[Blocked]
    Val -->|Policy Review Needed| HITL[Human-in-the-Loop Approval]
    HITL -->|Approved / Edited| Exec[DuckDB Execution Engine]
    HITL -->|Rejected| Cancel[Cancelled]
    
    Val -->|Safe Query| Exec
    Exec -->|Syntax Error (Max 3)| DE
    Exec -->|Success| BI[BI Visualizer Agent]
    BI --> Critic[Critic & Fact-Checker Agent]
    Critic --> Memory[(Persistent Memory DB)]
    Critic --> UI([Streamlit Dashboard & Plotly Charts])
```

---

## 📁 Project Structure

```text
Intelligent-Query-Engine/
├── backend/
│   ├── auth.py            # SQLite user authentication & session management
│   ├── database.py        # Embedded DuckDB database manager
│   ├── graph.py           # LangGraph StateGraph, nodes, edges & MemorySaver
│   ├── llm_service.py     # Groq LLM agent implementations
│   ├── main.py            # FastAPI REST API endpoints & route protection
│   └── validator.py       # SQLGlot AST security guardrails & policy inspector
├── frontend/
│   └── app.py             # Streamlit dashboard with custom CSS & interactive UI
├── sample_data/
│   └── sales_sample.csv   # Pre-packaged sample sales dataset
├── .env.example           # Environment configuration template
├── .gitignore             # Standard git ignore rules
├── requirements.txt       # Production dependencies
└── README.md              # Project documentation
```

---

## 🚀 Quickstart & Local Setup

### 1. Clone Repository
```bash
git clone https://github.com/Rohan-Kumbhar-3387/Intelligent-Query-Engine.git
cd Intelligent-Query-Engine
```

### 2. Set Up Virtual Environment
```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env` and supply your **Groq API Key**:
```bash
cp .env.example .env
```
Edit `.env`:
```env
GROQ_API_KEY=your_groq_api_key_here
BACKEND_URL=http://127.0.0.1:8000
```
> Get a free API key at [console.groq.com](https://console.groq.com).

### 5. Launch the Application

**Terminal 1 — Backend (FastAPI)**:
```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

**Terminal 2 — Frontend (Streamlit)**:
```bash
streamlit run frontend/app.py
```

Open **http://localhost:8501** in your browser.

---

## 🌐 Deployment Guide

### Option 1: Deploy on Render / Railway
1. **Backend Service**:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
   - Set Environment Variable: `GROQ_API_KEY`
2. **Frontend Service**:
   - Start Command: `streamlit run frontend/app.py --server.port $PORT --server.address 0.0.0.0`
   - Set Environment Variable: `BACKEND_URL` pointing to your deployed backend URL.

### Option 2: Docker
Create a `Dockerfile`:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000 8501
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port 8000 & streamlit run frontend/app.py --server.port 8501 --server.address 0.0.0.0"]
```

---

## 📡 API Endpoints Overview

| Method | Endpoint | Description | Protected |
| :--- | :--- | :--- | :---: |
| `GET` | `/health` | Service health status | No |
| `POST` | `/auth/register` | Create user account & issue session token | No |
| `POST` | `/auth/login` | Authenticate credentials & return session token | No |
| `GET` | `/auth/me` | Fetch active user profile | Yes |
| `POST` | `/auth/logout` | Revoke active session token | Yes |
| `POST` | `/upload` | Upload & index CSV dataset into DuckDB | Yes |
| `POST` | `/query` | Execute end-to-end multi-agent query pipeline | Yes |
| `POST` | `/draft_query` | Draft and pause SQL for Human-in-the-Loop review | Yes |
| `POST` | `/execute_approved`| Execute user-approved/modified SQL query | Yes |
| `GET` | `/history` | Fetch persistent conversational memory | Yes |
| `DELETE`| `/history` | Clear conversational memory thread | Yes |

---

## 📄 License
This project is licensed under the [MIT License](LICENSE).
