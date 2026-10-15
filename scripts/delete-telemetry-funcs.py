#!/usr/bin/env python3
"""Delete telemetry functions from FenixApplication.kt. Simple and robust."""
import sys

path = sys.argv[1]

with open(path) as f:
    lines = f.readlines()

# Find setStartupMetrics.
start_idx = None
for i, line in enumerate(lines):
    if "internal suspend fun setStartupMetrics(" in line:
        start_idx = i
        break

if start_idx is None:
    print("setStartupMetrics not found")
    sys.exit(0)

# Walk back to include annotations and KDoc.
func_start = start_idx
while func_start > 0:
    prev = lines[func_start - 1].strip()
    if prev == "" or prev.startswith("@") or prev.startswith("*") or prev.startswith("/**") or prev.startswith("*/"):
        func_start -= 1
    else:
        break

# Find the end by brace counting.
depth = 0
end_idx = None
for i in range(start_idx, len(lines)):
    for ch in lines[i]:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end_idx = i
                break
    if end_idx is not None:
        break

if end_idx is None:
    print("Could not find end of function")
    sys.exit(1)

print(f"Deleting lines {func_start+1} to {end_idx+1} ({end_idx - func_start + 1} lines)")
del lines[func_start:end_idx+1]

# Delete the call site.
for i, line in enumerate(lines):
    if "setStartupMetrics(store, components.settings)" in line:
        print(f"Deleting call site at line {i+1}")
        del lines[i]
        break

# Delete setTermsOfUseStartUpMetrics.
start_idx = None
for i, line in enumerate(lines):
    if "private fun setTermsOfUseStartUpMetrics(" in line:
        start_idx = i
        break

if start_idx is not None:
    func_start = start_idx
    while func_start > 0:
        prev = lines[func_start - 1].strip()
        if prev == "" or prev.startswith("@"):
            func_start -= 1
        else:
            break
    depth = 0
    end_idx = None
    for i in range(start_idx, len(lines)):
        for ch in lines[i]:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end_idx = i
                    break
        if end_idx is not None:
            break
    if end_idx is not None:
        print(f"Deleting setTermsOfUseStartUpMetrics lines {func_start+1} to {end_idx+1}")
        del lines[func_start:end_idx+1]

with open(path, "w") as f:
    f.writelines(lines)

print("Done")
