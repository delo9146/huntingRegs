from dotenv import load_dotenv, find_dotenv
from openai import OpenAI
import os

load_dotenv(find_dotenv())

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

VS_ID = "vs_684491b54f808191b00489744947c4e0"

resp = client.vector_stores.files.list(vector_store_id=VS_ID)
for f in resp.data:
    print(f.id, f.attributes)
