from configManager import ConfigManager
from assistantManager import AssistantManager
import time

def run_query_return(state: str, prompt: str):
    from openai import OpenAI
    cfg = ConfigManager()
    am  = AssistantManager(cfg)

    assistant = am.get_or_create_assistant(cfg.assistant_name)
    thread = am.client.beta.threads.create()

    am.client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=f"Please restrict retrieval to documents tagged state={state.upper()}."
    )

    am.client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=prompt
    )

    run = am.client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant.id
    )

    while run.status != "completed":
        time.sleep(1)
        run = am.client.beta.threads.runs.retrieve(
            thread_id=thread.id,
            run_id=run.id
        )

    messages = am.client.beta.threads.messages.list(thread_id=thread.id).data
    for m in reversed(messages):
        print("Message role:", m.role)
        print("Raw content:", m.content)
        if m.role == "assistant" and isinstance(m.content, list) and hasattr(m.content[0], "text"):
            content_obj = m.content[0]
            text = getattr(content_obj.text, "value", str(content_obj.text))
            annotations = getattr(content_obj, "annotations", [])
            for annotation in annotations:
                if hasattr(annotation, "text") and hasattr(annotation, "file_citation"):
                    placeholder = annotation.text
                    fc = annotation.file_citation

                    # Defensive check: if the file ID starts with "file-", it’s valid
                    if hasattr(fc, "file_id") and fc.file_id.startswith("file-"):
                        citation_id = f"[{annotation.start_index}:{annotation.end_index}†{fc.file_id}]"
                    else:
                        # Fall back to placeholder with warning
                        citation_id = f"[{annotation.start_index}:{annotation.end_index}†invalid-file-id]"
                    text = text.replace(placeholder, citation_id)

            return {"text": text, "annotations": annotations}
        elif m.role == "assistant":
            return {"text": str(m.content), "annotations": []}
    return {"text": "No answer returned.", "annotations": []}



