import time
import numpy as np

items = [{"predictable": False}] * 1000 + [{"predictable": True}]
vr = {f"k{i}": item for i, item in enumerate(items)}

t0 = time.time()
for _ in range(1000):
    b1 = bool(any(v.get("predictable", False) for v in vr.values()))
t1 = time.time()

t2 = time.time()
for _ in range(1000):
    b2 = False
    for v in vr.values():
        if v.get("predictable", False):
            b2 = True
            break
t3 = time.time()

print(f"Old: {t1-t0:.4f}")
print(f"New: {t3-t2:.4f}")
print(f"Match: {b1 == b2}")
