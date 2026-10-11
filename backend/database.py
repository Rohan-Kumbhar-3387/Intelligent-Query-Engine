import duckdb
import pandas as pd


class DatabaseManager:
    def __init__(self):
        # In-memory session connection
        self.conn = duckdb.connect(database=":memory:")
        self.active_table = "uploaded_data"

    def load_csv(self, file_path_or_buffer) -> dict:
        df = pd.read_csv(file_path_or_buffer)

        # Standardize column names (strip whitespace and convert spaces to underscores)
        df.columns = [col.strip().replace(" ", "_").lower() for col in df.columns]

        self.conn.register("temp_df", df)
        self.conn.execute(f"CREATE OR REPLACE TABLE {self.active_table} AS SELECT * FROM temp_df")

        row_count = self.conn.execute(f"SELECT COUNT(*) FROM {self.active_table}").fetchone()[0]
        schema_info = self.get_schema_str()

        return {
            "table_name": self.active_table,
            "row_count": row_count,
            "columns": list(df.columns),
            "schema_summary": schema_info
        }

    def get_schema_str(self) -> str:
        try:
            schema_rows = self.conn.execute(f"DESCRIBE {self.active_table}").fetchall()
            lines = [f"- {row[0]} ({row[1]})" for row in schema_rows]
            return "\n".join(lines)
        except Exception:
            # Returns an empty string if the table has not been uploaded yet
            return ""

    def execute_query(self, sql_query: str) -> tuple[list[dict], list[str]]:
        cursor = self.conn.execute(sql_query)
        col_names = [desc[0] for desc in cursor.description]
        records = cursor.fetchall()

        results = [dict(zip(col_names, row)) for row in records]
        return results, col_names


# Shared instance across backend modules
db_manager = DatabaseManager()