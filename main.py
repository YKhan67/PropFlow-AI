import logging
import sys
import os
import uvicorn

# Add backend directory to sys.path to allow imports from 'app'
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def main():
    # To run the FastAPI server, we point to the app.main module inside the backend directory
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True, app_dir="backend")

if __name__ == "__main__":
    main()
