from configManager import ConfigManager
from fileManager    import FileManager
from pdfAnalysisManager import PdfAnalysisManager

def main():
    # Load configuration
    cfg = ConfigManager()
    # Prepare file manager
    fm = FileManager(cfg.input_dir, cfg.output_dir)
    # Prepare PDF analysis manager
    pdf_manager = PdfAnalysisManager(cfg)

    # Process each PDF listed in the config
    for fname in cfg.pdf_files:
        print(f"Processing {fname}...")
        pdf_path = fm.get_input_path(fname)
        # Call ChatGPT to summarize
        summary = pdf_manager.summarize_pdf(pdf_path)
        # Determine output file
        out_path = fm.get_output_path(fname)
        # Write the summary
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(summary)
        print(f"✔️  Summary written to {out_path}\n")

if __name__ == "__main__":
    main()

