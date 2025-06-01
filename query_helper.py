from configManager import ConfigManager
from assistantManager import AssistantManager
import re
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
            text = content_obj.text.value
            annotations = getattr(content_obj.text, "annotations", [])
            for annotation in annotations:
                if hasattr(annotation, "text") and hasattr(annotation, "file_citation"):
                    raw_text = annotation.text  # e.g. '【5:0†source】'
                    fc = annotation.file_citation
                    # extract numbers inside raw_text
                    m2 = re.match(r"【(\d+):(\d+)†source】", raw_text)
                    if m2:
                        msg_idx, chunk_idx = m2.groups()
                        citation_id = f"[{msg_idx}:{chunk_idx}†{fc.file_id}]"
                    else:
                        # fallback using file_id with chunk 0
                        citation_id = f"[0:0†{fc.file_id}]"
                    text = text.replace(raw_text, citation_id)
            return {"text": text, "annotations": annotations}
        elif m.role == "assistant":
            return {"text": str(m.content), "annotations": []}
    return {"text": "No answer returned.", "annotations": []}
