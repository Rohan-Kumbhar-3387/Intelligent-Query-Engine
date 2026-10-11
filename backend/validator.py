import sqlglot
from sqlglot import exp


class SQLSecurityError(Exception):
    pass


FORBIDDEN_EXPRESSIONS = (
    exp.Drop,
    exp.Delete,
    exp.Update,
    exp.Insert,
    exp.AlterTable,
    exp.TruncateTable,
    exp.Create,
)


def validate_read_only_sql(sql_query: str) -> str:
    cleaned = sql_query.strip().rstrip(";")
    
    try:
        parsed_expressions = sqlglot.parse(cleaned, read="duckdb")
    except Exception as e:
        raise SQLSecurityError(f"SQL parsing failed: {str(e)}")

    if not parsed_expressions:
        raise SQLSecurityError("Empty SQL command received.")

    # Block chained statements (e.g., SELECT 1; DROP TABLE ...)
    if len(parsed_expressions) > 1:
        raise SQLSecurityError("Multi-statement SQL execution is blocked for security.")

    expression = parsed_expressions[0]

    if not isinstance(expression, exp.Select):
        raise SQLSecurityError("Security Block: Only SELECT queries are permitted.")

    for forbidden in FORBIDDEN_EXPRESSIONS:
        if expression.find(forbidden):
            raise SQLSecurityError(f"Security Block: Dangerous operation detected ({forbidden.__name__}).")

    return expression.sql(dialect="duckdb")


def check_query_needs_review(sql_query: str) -> tuple[bool, str]:
    """Analyzes AST and keywords to detect queries requiring human review."""
    cleaned = sql_query.strip().rstrip(";")
    try:
        parsed = sqlglot.parse(cleaned, read="duckdb")
        if not parsed:
            return False, ""
        expression = parsed[0]

        # 1. Unbounded table scans (SELECT without LIMIT or aggregate function)
        has_limit = expression.find(exp.Limit) is not None
        has_aggregate = expression.find(exp.AggFunc) is not None
        has_group = expression.find(exp.Group) is not None
        if not has_limit and not has_aggregate and not has_group:
            return True, "Unbounded table scan: Query lacks a LIMIT clause and may return a massive result set."

        # 2. Sensitive keyword inspection
        sensitive_terms = ["password", "secret", "salary", "token", "ssn", "credit_card", "revenue_margin"]
        lower_sql = sql_query.lower()
        for term in sensitive_terms:
            if term in lower_sql:
                return True, f"Sensitive attribute: Query accesses potentially sensitive field '{term}'."

    except Exception:
        pass

    return False, ""