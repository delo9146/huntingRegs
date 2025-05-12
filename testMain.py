from configManager import ConfigManager

cfg = ConfigManager()
print("Input dir:", cfg.input_dir)
print("PDF files:", cfg.pdf_files)
print("Prompt template:", cfg.summary_template.strip().split("\n")[0], "…")
