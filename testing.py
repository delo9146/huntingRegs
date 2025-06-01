# testing.py

from openai import OpenAI
import os
from dotenv import load_dotenv
import pandas as pd
from configManager import ConfigManager

# 1) Load environment variables from .env
load_dotenv()

# 2) Use ConfigManager to find the correct env‐var name
cfg = ConfigManager()
api_key = os.getenv(cfg.api_key_env)
if not api_key:
    raise RuntimeError(f"No API key found in env var {cfg.api_key_env}")

client = OpenAI(api_key=api_key)

# 3) Paste in the file_id that you want to inspect.
file_id = "file-DkiwRM89JgKtHhbEZZbN5H"  # e.g. from a ChatGPT citation

# 4) Call the vector_stores.files.content endpoint to retrieve all chunks
vector_store_id = "vs_68278c6a883c8191a0da6e4afc22f6bd"  # your VS ID
resp = client.vector_stores.files.content(
    vector_store_id=vector_store_id,
    file_id=file_id
)

# 5) `resp.data` is a list of objects with attributes .type and .text
chunks = resp.data

# 1) Print the length (number of characters) of chunk 0:
chunk_text = chunks[0].text
print("Length of chunk 0 (in characters):", len(chunk_text))

# 2) If you want to dump the entire chunk to the console:
print("\n=== FULL TEXT OF CHUNK 0 ===\n")
print(chunk_text)

# 6) Create a quick pandas DataFrame so you can easily scroll through them.
df = pd.DataFrame([
    {
        "chunk_index": idx,
        "type": chunk.type,
        "text_snippet": chunk.text[:200].replace("\n", " ") + "…"
    }
    for idx, chunk in enumerate(chunks)
])

print(f"Total chunks for {file_id}: {len(chunks)}\n")
print(df)

# If you want to see the full text of a specific chunk (e.g. chunk 18), uncomment:
# print("\nFull text of chunk 18:\n", chunks[18].text)
