"""Offline scoring criteria for the Local Worker.

Each sibling module implements one scoring criterion as a small, pure
Python/regex function with zero network or database dependency (the
Local Worker runs fully offline). ``criteria.py`` is the single source
of truth registry tying the modules together (weights, categories,
presets) for both ``worker.py`` (CLI) and ``qml_gui.py`` (GUI).
"""
