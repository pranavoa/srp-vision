"""Mirador — SRP Phase 1 Simulator.

Mirador (Spanish for "lookout") is the OnArrival hotel SRP tuning dashboard.
You go there to see clearly: how the Phase 1 ranking formula behaves on
live Elastic data, what each knob does, where the SRP composition shifts.

The Streamlit entry point lives at the project root (``app.py``).
This package houses pure logic and helpers used by the UI:

- ``config``       — environment variables, defaults, presets, constants
- ``elastic``      — Elasticsearch query builders and helpers
- ``scoring``      — Bayesian rating, affinity lookup, distance decay, sort
- ``persistence``  — load/save of user-tuned defaults to JSON
- ``theme``        — light / dark CSS strings
- ``competitors``  — pluggable competitor data source (feature-flagged off)
"""

__version__ = "0.1.0"
__product__ = "Mirador"
