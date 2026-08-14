import os

# The suite exercises the diagnostic logs through assertLogs (which raises the
# level of the logger it watches), so the app's own output stays out of the way.
os.environ.setdefault("LOG_LEVEL", "CRITICAL")
