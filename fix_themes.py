"""Remove leftover old-theme junk between DEFAULT_THEME = 'dark_indigo' and the old DEFAULT_THEME = 'warm_stone' line."""

path = "local_worker/qt_gui.py"
lines = open(path, encoding="utf-8").readlines()

start = None  # first junk line (index after DEFAULT_THEME = dark_indigo)
end = None  # last junk line (the old DEFAULT_THEME = warm_stone line, inclusive)

for i, l in enumerate(lines):
    if start is None and "dark_indigo" in l and "DEFAULT_THEME" in l:
        start = i + 1  # next line is junk start
    if start is not None and end is None and "warm_stone" in l and "DEFAULT_THEME" in l:
        end = i  # this line (0-indexed) is the last junk line (inclusive)

if start is None or end is None:
    print(f"Could not find markers. start={start} end={end}")
else:
    print(f"Removing lines {start + 1}..{end + 1} (1-indexed), total {end - start + 1} lines")
    cleaned = lines[:start] + lines[end + 1 :]
    open(path, "w", encoding="utf-8").writelines(cleaned)
    print("Done.")
