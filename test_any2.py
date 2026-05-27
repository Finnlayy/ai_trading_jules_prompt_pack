import time
import numpy as np

combined = ["FOO", "BAR", "BAZ"] * 100 + ["UNCONFIRMED_BAR"] + ["HELLO"] * 100

t0 = time.time()
for _ in range(1000):
    b1 = any("UNCONFIRMED_BAR" in item for item in combined)
t1 = time.time()

t2 = time.time()
for _ in range(1000):
    b2 = False
    for item in combined:
        if "UNCONFIRMED_BAR" in item:
            b2 = True
            break
t3 = time.time()

print(f"Old: {t1-t0:.4f}")
print(f"New: {t3-t2:.4f}")
print(f"Match: {b1 == b2}")
