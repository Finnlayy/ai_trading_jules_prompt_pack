import subprocess

def run_tests():
    # Only tests/test_main.py + tests/api/test_cors_security.py
    print("Testing test_main.py")
    subprocess.run("DATABASE_URL='sqlite:///./app/data/trading.db' python -m pytest tests/test_main.py", shell=True)
    print("Testing test_cors_security.py")
    subprocess.run("DATABASE_URL='sqlite:///./app/data/trading.db' python -m pytest tests/api/test_cors_security.py", shell=True)

run_tests()
