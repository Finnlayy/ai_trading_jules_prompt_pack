with open('app/services/ai_mock.py', 'r') as f:
    content = f.read()

# Fix the condition back if needed or let it be. Wait, the test uses payload.crisis_score = 25.0 and expects REJECT.
