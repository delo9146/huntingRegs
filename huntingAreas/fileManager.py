import os

class fileManager:
    @staticmethod
    def get_input_images(input_dir=None):
        # Get base path relative to the project root
        if input_dir is None:
            base_path = os.path.dirname(os.path.dirname(__file__))  # Up from /hunting
            input_dir = os.path.join(base_path, "data", "input")

        valid_extensions = (".png", ".jpg", ".jpeg")

        if not os.path.exists(input_dir):
            return []

        files = [
            os.path.join(input_dir, f)
            for f in os.listdir(input_dir)
            if f.lower().endswith(valid_extensions)
        ]

        return files
