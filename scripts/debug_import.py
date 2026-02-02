import sys
import os

# Adds the current directory to sys.path
sys.path.append(os.getcwd())

try:
    from modules.administrative import administrative_module
    print("Import successful")
except Exception as e:
    import traceback
    traceback.print_exc()
