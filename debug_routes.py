
import sys
import os
from fastapi import FastAPI
from core.server import create_base_app
from core.app_context import AppContext
from core.registry import ModuleRegistry

# Mock config
sys.path.append(os.getcwd())
os.environ["BASE_URL"] = "https://example.com"

context = AppContext()
registry = ModuleRegistry()
registry.set_context(context)

app = create_base_app(context, registry)

print("Routes:")
for route in app.routes:
    if hasattr(route, "path"):
        print(f"{route.methods} {route.path}")
    else:
        print(route)
