import os
from openai import OpenAI
from dotenv import load_dotenv

# Load your .env file containing OPENAI_API_KEY
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

# Initialize OpenAI client
client = OpenAI(api_key=api_key)

# Set your vector store ID
VECTOR_STORE_ID = "vs_687047f0b154819184c77779388a2129" 

# List files in the vector store
files = client.vector_stores.files.list(vector_store_id=VECTOR_STORE_ID).data

print(f"🧠 Found {len(files)} files in vector store {VECTOR_STORE_ID}\n")

# Retrieve and print detailed metadata for each file
for i, file_ref in enumerate(files, 1):
    file_id = file_ref.id
    file_obj = client.vector_stores.files.retrieve(vector_store_id=VECTOR_STORE_ID, file_id=file_id)
    
    print(f"🔹 File {i}:")
    print(f"  ID: {file_obj.id}")
    print(f"  Filename: {getattr(file_obj, 'filename', 'N/A')}")
    print(f"  Created at: {file_obj.created_at}")
    print(f"  Status: {file_obj.status}")
    print(f"  Usage (bytes): {file_obj.usage_bytes}")
    print(f"  Last error: {file_obj.last_error}")
    print(f"  Attributes (metadata): {file_obj.attributes}")
    print(f"  Chunking Strategy: {file_obj.chunking_strategy}")
    print("-" * 60)
