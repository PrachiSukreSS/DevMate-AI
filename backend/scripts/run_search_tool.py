"""Invoke DevMate's bounded document search tool without an LLM."""

import argparse
import os
from uuid import UUID

from app.agents.tools import create_project_search_tool

parser = argparse.ArgumentParser(
    description="Search one DevMate project's indexed documentation."
)
parser.add_argument("query", help="A question or phrase to search for")
arguments = parser.parse_args()
project_id_value = os.getenv("DEVMATE_PROJECT_ID")
if not project_id_value:
    raise SystemExit("Set DEVMATE_PROJECT_ID to the UUID of an existing project.")

tool = create_project_search_tool(UUID(project_id_value))
print(tool.invoke({"query": arguments.query}))
