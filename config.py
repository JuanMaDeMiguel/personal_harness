import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY")
ENDPOINT = "https://api.francestudent.org/v1/responses"
MODEL = "gpt-5.5"

SESSIONS_FILE = Path(".harness_sessions.json")
MAX_SESSIONS = 50

# Mutated at runtime by /model and /effort commands
active_model: str = MODEL
reasoning_effort: str = "medium"   # low | medium | high | xhigh

# Mutated by main() after arg parsing
debug: bool = False
