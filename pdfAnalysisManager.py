import os
from dotenv import load_dotenv
from openai import OpenAI
from configManager import ConfigManager

class PdfAnalysisManager:
    def __init__(self, config: ConfigManager):
        # Load environment variables (API key)
        load_dotenv()
        api_key = os.getenv(config.api_key_env)
        if not api_key:
            raise ValueError(f"No API key found in env var {config.api_key_env}")
        # Initialize OpenAI client
        self.client = OpenAI(api_key=api_key)
        # Store model and prompt template
        self.model = config.model_name
        self.prompt = config.summary_template

    def summarize_pdf(self, pdf_path: str) -> str:
        """
        Reads the PDF at pdf_path and returns ChatGPT's summary.
        """
        # Load the PDF bytes
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        # Call the ChatGPT API with the PDF as an attachment
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": self.prompt}],
            files=[("file", pdf_bytes)]
        )

        # Extract and return the summary text
        return response.choices[0].message.content
