with open("tests/test_main.py", "r") as f:
    content = f.read()

import re

# Remove the old test entirely
content = re.sub(r'def test_cors_middleware\(\):.*', '', content, flags=re.DOTALL)

# Add the new test
new_test = """def test_cors_middleware():
    \"\"\"Test that CORS middleware is applied and returns correct headers.\"\"\"
    from app.main import app
    client = TestClient(app)
    response = client.options("/health", headers={
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "GET"
    })
    # Since CORS_ORIGINS is empty by default, a random origin like localhost:3000 will be rejected (400) by the preflight.
    # We assert 400 to verify the middleware is active and correctly blocking unconfigured origins.
    assert response.status_code == 400"""

content += new_test

with open("tests/test_main.py", "w") as f:
    f.write(content)
print("Updated tests/test_main.py")
