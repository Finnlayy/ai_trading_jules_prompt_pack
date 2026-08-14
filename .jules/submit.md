# 🧹 Remove commented lines in RiskEngine initialization

## 🎯 What
Removed unused comments in the `RiskEngine` initialization method.

## 💡 Why
The comments `# state for simulation tests` and `# for correlation risk checks` were stating the obvious or adding unnecessary clutter, and removing them improves the code readability and cleanliness.

## ✅ Verification
1. I ran `python -m pytest tests/services/test_risk_engine.py` to ensure the risk engine tests still pass.
2. The core risk engine logic remains untouched.

## ✨ Result
Improved code health by removing unnecessary dead comments.
