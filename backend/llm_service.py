import os
import re
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
# Using the active model verified on your account
MODEL_NAME = "qwen/qwen3.8-27b"


def extract_json(raw_text: str) -> dict:
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass
    return {}


def supervisor_agent(question: str, schema_str: str, history_context: str = "") -> str:
    """Classifies user intent to determine whether standard SQL or deeper analysis is required."""
    prompt = (
        f"You are a Lead Data Supervisor.\n"
        f"Schema:\n{schema_str}\n\n"
    )
    if history_context:
        prompt += f"Prior Conversation History:\n{history_context}\n\n"
    prompt += (
        f"Current Question: {question}\n\n"
        "Categorize the plan into exactly ONE route:\n"
        "- 'sql_query': Standard aggregation, filtering, ranking, counts, or sums.\n"
        "- 'statistical_analysis': Multi-dimensional comparisons, anomaly exploration, correlation, or statistical summaries.\n"
        "Return ONLY the word 'sql_query' or 'statistical_analysis'."
    )
    res = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0
    )
    decision = res.choices[0].message.content.strip().lower()
    return "statistical_analysis" if "statistical" in decision else "sql_query"


def data_engineer_agent(question: str, schema_str: str, error_context: str = None, history_context: str = "") -> str:
    """Drafts and self-heals DuckDB SQL taking conversational history into account for follow-ups."""
    prompt = (
        "You are a Staff Data Engineer specializing in DuckDB SQL.\n"
        "Draft a single, valid, read-only SELECT statement against the table 'uploaded_data'.\n"
        "Rules:\n"
        "1. Table name is strictly 'uploaded_data'.\n"
        "2. Do not use markdown fences. Return ONLY the raw SQL string.\n"
        f"Schema:\n{schema_str}\n\n"
    )
    if history_context:
        prompt += (
            "Prior Conversation Context (use this to resolve follow-up questions, pronouns like 'it'/'them', or previous filters/metrics):\n"
            f"{history_context}\n\n"
        )
    prompt += f"Question to answer with SQL: {question}"
    if error_context:
        prompt += f"\n\nPrevious attempt failed with error:\n{error_context}\nPlease fix the query."

    res = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0
    )
    raw = res.choices[0].message.content.strip()
    match = re.search(r"```(?:sql)?(.*?)```", raw, re.DOTALL | re.IGNORECASE)
    sql = match.group(1).strip() if match else raw
    return sql.rstrip(";")


def analyst_agent(question: str, schema_str: str, history_context: str = "") -> str:
    """Produces wide aggregate SQL for statistical comparisons."""
    prompt = (
        f"You are a Senior Quantitative Analyst.\n"
        f"Schema:\n{schema_str}\n\n"
    )
    if history_context:
        prompt += f"Prior Conversation History:\n{history_context}\n\n"
    prompt += (
        f"Question: {question}\n"
        "Write a DuckDB SQL SELECT query that pulls comprehensive descriptive statistics, "
        "groupings, or distributions to deeply answer this analytical question from 'uploaded_data'.\n"
        "Return ONLY the raw SQL statement."
    )
    res = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0
    )
    raw = res.choices[0].message.content.strip()
    match = re.search(r"```(?:sql)?(.*?)```", raw, re.DOTALL | re.IGNORECASE)
    sql = match.group(1).strip() if match else raw
    return sql.rstrip(";")


def bi_visualizer_agent(question: str, columns: list, rows: list) -> dict:
    """Decides the optimal Plotly chart layout."""
    if not rows or len(columns) < 2:
        return {"chart_type": "none"}

    preview = rows[:3]
    prompt = (
        "You are an expert BI Visualization Architect.\n"
        f"User Question: {question}\n"
        f"Columns: {columns}\n"
        f"Sample Data: {preview}\n\n"
        "Select the best visualization (bar, line, scatter, pie) and axis mappings.\n"
        "Respond ONLY with a valid JSON object formatted as:\n"
        '{"chart_type": "bar|line|scatter|pie", "x": "column_name", "y": "column_name", "title": "Chart Title"}'
    )
    res = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0
    )
    return extract_json(res.choices[0].message.content)


def critic_auditor_agent(question: str, sql: str, rows: list) -> str:
    """Verifies that numbers in the final executive summary match query results."""
    preview = rows[:10]
    prompt = (
        "You are an AI Compliance Auditor and Fact-Checker.\n"
        f"Question: {question}\n"
        f"Executed SQL: {sql}\n"
        f"Query Output Data: {preview}\n\n"
        "Instructions:\n"
        "1. Write an accurate, concise 2-3 sentence executive answer.\n"
        "2. AUDIT CHECK: Every number you state MUST match the output data precisely.\n"
        "3. Explicitly state whether the data fully satisfies the user request."
    )
    res = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )
    return res.choices[0].message.content.strip()