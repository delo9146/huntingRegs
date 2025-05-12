import os
from dotenv import load_dotenv
from openai import OpenAI
from configManager import ConfigManager

class AssistantManager:
    def __init__(self, config: ConfigManager):
        """
        Initializes the OpenAI client and holds placeholders
        for the Assistant and Vector Store.
        """
        load_dotenv()
        api_key = os.getenv(config.api_key_env)
        if not api_key:
            raise ValueError(f"No API key found in env var {config.api_key_env}")
        self.client = OpenAI(api_key=api_key)
        self.config = config
        self.assistant = None
        self.vector_store = None


    def create_assistant(self, name: str = "RegulationsSummarizer"):
        """
        Create a new Assistant (or overwrite) configured with the File Search tool.
        """
        # 1. Define the assistant
        assistant = self.client.beta.assistants.create(
            name=name,
            instructions=(
                "You have access to uploaded hunting regulations PDFs. "
                "When asked, read the files via File Search and provide concise summaries."
            ),
            model=self.config.model_name,
            tools=[{"type": "file_search"}],
        )
        # 2. Keep a reference
        self.assistant = assistant
        return assistant
    
    def create_vector_store(self, name: str = "regs-store"):
        """
        Creates a new vector store for your regulations files.
        """
        vs = self.client.vector_stores.create(name=name)
        self.vector_store = vs
        return vs
    
    def ingest_file(self, pdf_path: str):
        """
        Uploads the PDF at pdf_path and ingests it into the vector store.
        """
        # 1. Upload the file for assistant use
        file = self.client.files.create(
            file=open(pdf_path, "rb"),
            purpose="assistants"
        )
        # 2. Ensure we have a vector store
        vs = self.vector_store or self.create_vector_store()
        # 3. Ingest the file into that store (this polls until done)
        ingest = self.client.vector_stores.files.create_and_poll(
            vector_store_id=vs.id,
            file_id=file.id
        )
        return ingest

    def update_assistant(self):
        """
        Points your Assistant’s File Search tool at the created vector store.
        """
        if not self.assistant or not self.vector_store:
            raise ValueError("Assistant or vector store not initialized.")
        self.client.beta.assistants.update(
            self.assistant.id,
            tool_resources={
                "file_search": {"vector_store_ids": [self.vector_store.id]}
            }
        )

