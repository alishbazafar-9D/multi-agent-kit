import sys
from pathlib import Path

_root = Path(__file__).resolve().parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

if __name__ == "__main__":
    if "--api" in sys.argv:
        import uvicorn
        uvicorn.run("src.api:app", host="0.0.0.0", port=8000, reload=False)
    else:
        from dev.main import main
        main()
