"""Synthetic example: k=1..3 group delay of a periodic input/output pair."""
import numpy as np

from ppg_transfer.harmonics import periodic_transfer

period = 0.8
t = np.arange(400) / 500
x = sum(np.cos(2*np.pi*k*t/period)/k for k in range(1, 6))
y = sum(0.9**k*np.cos(2*np.pi*k*(t-0.004)/period)/k for k in range(1, 6))
result = periodic_transfer(t, x, y, period, (1., 1., 1.))
print(result["group_delay_k1_3_s"], result["h2_over_h1"])
