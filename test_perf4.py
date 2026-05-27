import time
import numpy as np

def old_ema(values, period):
    if not values:
        return []
    alpha = 2.0 / (period + 1.0)
    out = [values[0]]
    for x in values[1:]:
        out.append(out[-1] * (1.0 - alpha) + x * alpha)
    return out

def new_ema(values, period):
    if not values:
        return []
    alpha = 2.0 / (period + 1.0)

    # We can compile this using numba but we can't add dependencies.
    # What about numpy?

    # For a very large sequence, pure python might still be reasonable or we can try something else.
    # Let's test the overhead.
    out = [values[0]]
    for x in values[1:]:
        out.append(out[-1] * (1.0 - alpha) + x * alpha)
    return out

values = [1.0] * 100000

t0 = time.time()
old_ema(values, 14)
t1 = time.time()
print(f"Old: {t1-t0:.4f}")
