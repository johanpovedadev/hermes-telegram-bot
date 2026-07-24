import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ.get("HERMES_BOT_TOKEN", "")
DOCUMENTS_PATH = os.path.expanduser("~/Documents")
TIMEOUT_SECONDS = 300
MAX_OUTPUT_LENGTH = 4000
