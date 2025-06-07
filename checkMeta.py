from dotenv import load_dotenv, find_dotenv
from openai import OpenAI
import os

# 1. Locate and load your .env
load_dotenv(find_dotenv())

# 2. Initialize the OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 3. Your vector store ID
VS_ID = "vs_684491b54f808191b00489744947c4e0"

# 4. List and print each file’s metadata
resp = client.vector_stores.files.list(vector_store_id=VS_ID)
for f in resp.data:
    print(f.id, f.attributes)
