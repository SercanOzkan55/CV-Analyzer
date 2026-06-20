import subprocess
import time

try:
    print("Starting qml_gui.py in subprocess...")
    p = subprocess.Popen([r"..\.venv\Scripts\python.exe", "qml_gui.py"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(2.5)
    print("Terminating subprocess...")
    p.terminate()
    stdout, stderr = p.communicate()
    print("--- STDOUT ---")
    print(stdout.decode("utf-8", errors="ignore"))
    print("--- STDERR ---")
    print(stderr.decode("utf-8", errors="ignore"))
except Exception as e:
    print("Error running subprocess:", e)
