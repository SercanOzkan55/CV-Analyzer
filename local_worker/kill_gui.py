import subprocess

try:
    # Run wmic to get process IDs of python processes containing qml_gui.py
    output = subprocess.check_output('wmic process where "CommandLine like \'%qml_gui.py%\'" get ProcessID', shell=True)
    lines = output.decode("utf-8", errors="ignore").strip().split("\n")
    killed_any = False
    for line in lines:
        line = line.strip()
        if line and line.isdigit():
            pid = int(line)
            print("Terminating process:", pid)
            subprocess.call(f"taskkill /F /PID {pid}", shell=True)
            killed_any = True
    if not killed_any:
        print("No running GUI processes found.")
except Exception as e:
    print(f"Error: {e}")
