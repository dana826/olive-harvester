"""Simulated hardware layer.

Every class in this package stands in for a real Raspberry Pi peripheral
(Camera Module 3, load-cell/vibration/current sensors, the vibration
actuator driver) and exposes the same call shape a real, hardware-backed
implementation will use later (capture(), read(), start()/stop()/
is_running). Nothing outside this package — app/core/, app/api/ — knows
or cares whether it's talking to simulated or real hardware.
"""
