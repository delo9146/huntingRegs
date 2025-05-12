import os

class FileManager:
    def __init__(self, input_dir, output_dir):
        """
        Manage reading PDFs from input_dir and preparing output paths in output_dir.
        """
        self.input_dir = input_dir
        self.output_dir = output_dir
        # Ensure the output directory exists
        os.makedirs(self.output_dir, exist_ok=True)

    def list_pdfs(self):
        """
        Return a list of all PDF filenames in the input directory.
        """
        return [
            fname for fname in os.listdir(self.input_dir)
            if fname.lower().endswith(".pdf")
        ]

    def get_input_path(self, filename):
        """
        Given a PDF filename, return its full path in input_dir.
        """
        return os.path.join(self.input_dir, filename)

    def get_output_path(self, filename, suffix="_summary.txt"):
        """
        Given the PDF filename, return the full output path.
        By default, replaces `.pdf` with `_summary.txt`.
        """
        base = os.path.splitext(filename)[0]
        return os.path.join(self.output_dir, f"{base}{suffix}")
