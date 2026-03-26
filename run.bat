if not exist ".venv" (
    .\init_py.bat
)

start "" .venv\Scripts\pythonw program.py
