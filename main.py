from configManager import ConfigManager
from fileManager    import FileManager
from assistantManager import AssistantManager
import time

def main():
    # Load configuration
    cfg = ConfigManager()
    # Prepare file manager
    fm = FileManager(cfg.input_dir, cfg.output_dir)
    # Prepare the Assistant
    am = AssistantManager(cfg)

    assistant = am.create_assistant()
    vs = am.create_vector_store()


    # Upload & ingest each regulations PDF
    for fname in cfg.pdf_files:
        print(f"Ingesting {fname}…")
        pdf_path = fm.get_input_path(fname)
        am.ingest_file(pdf_path)

    am.update_assistant()

    # Start a thread and ask for the summary
    print("Requesting summary from Assistant…")
    thread = am.client.beta.threads.create()
    am.client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content="Please summarize the uploaded Montana hunting regulations PDF."
    )
    run = am.client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant.id
    )

    # Poll until complete
    while run.status != "completed":
        time.sleep(1)
        run = am.client.beta.threads.runs.retrieve(
            thread_id=thread.id,
            run_id=run.id
        )

    messages = am.client.beta.threads.messages.list(thread_id=thread.id)
    summary_content = None
    for msg in messages.data:
        if msg.role == "assistant":
            summary_content = msg.content
            break

    if isinstance(summary_content, list):
        summary_text = "\n\n".join(block.text.value for block in summary_content)
    else:
        summary_text = summary_content or ""

    out_path = fm.get_output_path(cfg.pdf_files[0])
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(summary_text)

    print(f"✔️ Summary written to {out_path}")





if __name__ == "__main__":
    main()

