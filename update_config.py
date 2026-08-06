import re

with open("app/core/config.py", "r") as f:
    content = f.read()

# Replace the insecure CORS_ORIGINS default
content = content.replace('CORS_ORIGINS = _as_csv_list(os.getenv("CORS_ORIGINS", "*"))', 'CORS_ORIGINS = _as_csv_list(os.getenv("CORS_ORIGINS", ""))')

with open("app/core/config.py", "w") as f:
    f.write(content)

print("Updated config.py")
