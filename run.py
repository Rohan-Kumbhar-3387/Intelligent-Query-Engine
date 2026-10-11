import os
import sys

# Ensure project root is in sys.path
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    print(f"Starting QueryPilot Backend on port {port}...")
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port)
