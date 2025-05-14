# assistantManager.py
import os
from dotenv import load_dotenv
from openai import OpenAI
from configManager import ConfigManager

class AssistantManager:
    def __init__(self, config: ConfigManager):
        load_dotenv()
        api_key = os.getenv(config.api_key_env)
        if not api_key:
            raise ValueError(f"No API key found in env var {config.api_key_env}")
        self.client = OpenAI(api_key=api_key)
        self.config = config
        self.assistant = None
        self.vector_store = None

    def get_or_create_assistant(self, name: str = "RegulationsSummarizer"):
        for a in self.client.beta.assistants.list().data:
            if a.name == name:
                self.assistant = a
                return a
        return self.create_assistant(name)

    def create_assistant(self, name: str = "RegulationsSummarizer"):
        assistant = self.client.beta.assistants.create(
            name=name,
            instructions=(
                "You have access to uploaded hunting regulations PDFs. "
                "When asked, read the files via File Search and provide concise summaries."
            ),
            model=self.config.model_name,
            tools=[{"type": "file_search"}],
        )
        self.assistant = assistant
        return assistant

    def get_or_create_vector_store(self, name: str = "regs-store"):
        for vs in self.client.vector_stores.list().data:
            if vs.name == name:
                self.vector_store = vs
                return vs
        return self.create_vector_store(name)

    def create_vector_store(self, name: str = "regs-store"):
        vs = self.client.vector_stores.create(name=name)
        self.vector_store = vs
        return vs

    def _find_uploaded_file(self, filename: str):
        for f in self.client.files.list().data:
            if getattr(f, "filename", "") == filename and f.purpose == "assistants":
                return f
        return None

    def _file_already_ingested(self, file_id: str):
        ingested = self.client.vector_stores.files.list(
            vector_store_id=self.vector_store.id
        ).data
        return any(item.id == file_id for item in ingested)


    def ingest_file(self, pdf_path: str):
        filename = os.path.basename(pdf_path)
        existing = self._find_uploaded_file(filename)
        if existing:
            file_id = existing.id
        else:
            up = self.client.files.create(
                file=open(pdf_path, "rb"),
                purpose="assistants"
            )
            file_id = up.id

        vs = self.vector_store or self.get_or_create_vector_store()

        if not self._file_already_ingested(file_id):
            return self.client.vector_stores.files.create_and_poll(
                vector_store_id=vs.id,
                file_id=file_id
            )
        return None  

    def update_assistant(self):
        if not self.assistant or not self.vector_store:
            raise ValueError("Assistant or vector store not initialized.")
        self.client.beta.assistants.update(
            self.assistant.id,
            tool_resources={
                "file_search": {"vector_store_ids": [self.vector_store.id]}
            }
        )
