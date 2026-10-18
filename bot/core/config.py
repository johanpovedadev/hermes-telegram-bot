import os
from dotenv import load_dotenv

# El .env se lee SIEMPRE desde la carpeta del proyecto (no desde el directorio de trabajo): así funciona igual cuando
# notify.py o el bot se lanzan desde otro proyecto (hooks de Claude Code, PM2).
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(BASE_DIR, ".env"))

BOT_TOKEN = os.environ.get("HERMES_BOT_TOKEN", "")
DOCUMENTS_PATH = os.path.expanduser(os.environ.get("HERMES_DOCUMENTS_PATH", "~/Documents"))
TIMEOUT_SECONDS = int(os.environ.get("HERMES_TIMEOUT_SECONDS", "300"))
MAX_OUTPUT_LENGTH = 4000

# IA opcional para /chat (DeepSeek por NVIDIA NIM u otro proveedor compatible con OpenAI). Sin configurar = apagada.
AI_PROVIDER = os.environ.get("AI_PROVIDER", "none").strip().lower()
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "")
