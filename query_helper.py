from configManager import ConfigManager
from assistantManager import AssistantManager
import time

def run_query_return(state: str, prompt: str) -> str:
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
        if m.role == "assistant":
            if isinstance(m.content, list):
                blocks = []
                for block in m.content:
                    value_val = None
                    if hasattr(block, "value"):
                        value_val = block.value
                    elif hasattr(block, "text") and hasattr(block.text, "value"):
                        value_val = block.text.value
                    else:
                        value_val = str(block)
                    blocks.append(value_val)
                return "\n\n".join(str(b) for b in blocks)
            else:
                return str(m.content)
    return "No answer returned."

