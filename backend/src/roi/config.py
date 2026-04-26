import os
from dotenv import load_dotenv

load_dotenv()

PEEC_API_KEY: str = os.getenv("PEEC_API_KEY", "")
TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
PIONEER_API_KEY: str = os.getenv("PIONEER_API_KEY", "")

PEEC_BASE_URL = "https://api.peec.ai/customer/v1"
GEMINI_MODEL = "gemini-2.5-flash-lite"
PIONEER_API_URL = "https://api.pioneer.ai/v1/chat/completions"
PIONEER_JOB_ID = "9615aff8-fd49-42a3-823a-636cab755183"  # Fastino model
