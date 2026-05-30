from backend import chatbot
import os
from dotenv import load_dotenv

load_dotenv()
print("GROQ_API_KEY:", os.getenv("GROQ_API_KEY")[:15] if os.getenv("GROQ_API_KEY") else "None")

try:
    params, explanation = chatbot.translate_to_params("find 16GB DDR4 RAM under 5000 taka")
    print("\nSUCCESS!")
    print("Params:", params)
    print("Explanation:", explanation)
except Exception as e:
    print("\nFAILED:", e)
