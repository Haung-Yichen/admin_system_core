import os
try:
    from dotenv import load_dotenv
    print("Loading .env file...")
    load_dotenv()
except ImportError:
    print("python-dotenv not installed, skipping load_dotenv")

print(f"ADMIN_LINE_LIFF_ID_VERIFY: {os.getenv('ADMIN_LINE_LIFF_ID_VERIFY')}")
print(f"CHATBOT_LIFF_ID: {os.getenv('CHATBOT_LIFF_ID')}")
