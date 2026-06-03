import logging
import sys
import os
import uvicorn

# Add backend directory to sys.path
root_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(root_dir, "backend"))

# On Windows, this is the standard way to enable ANSI colors in CMD/PowerShell
if sys.platform == "win32":
    os.system("")

# Simple, original logging format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

def main():
    # reload=True uses Uvicorn's internal color logic
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True, app_dir="backend")

if __name__ == "__main__":
    main()
