import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()  # So .env values are available

# Get API key from your env var (change if you use a different var name)
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY not found in environment!")

client = OpenAI(api_key=api_key)

# Set your vector store ID here (copy from the dashboard)
VECTOR_STORE_ID = "vs_68278c6a883c8191a0da6e4afc22f6bd"  # <-- update if needed

# Fetch files in the vector store
files = client.vector_stores.files.list(vector_store_id=VECTOR_STORE_ID).data

print(f"Found {len(files)} files in vector store {VECTOR_STORE_ID}:")
for f in files:
    print(f"\nFile: {getattr(f, 'filename', f.id)}")
    # Try both 'attributes' and 'metadata', depending on SDK
    attrs = getattr(f, "attributes", None) or getattr(f, "metadata", None)
    print("  Attributes:", attrs)
    print("  Status:", getattr(f, "status", "unknown"))
