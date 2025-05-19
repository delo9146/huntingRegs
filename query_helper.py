from configManager import ConfigManager
from assistantManager import AssistantManager
import time

def run_query_return(state: str, prompt: str) -> str:
    cfg = ConfigManager()
    am  = AssistantManager(cfg)

    assistant = am.get_or_create_assistant(cfg.assistant_name)
    thread = am.client.beta.threads.create()

    # Set filter by state
    am.client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=f"Please restrict retrieval to documents tagged state={state.upper()}."
    )

    # Add the user's actual question or summary prompt
    am.client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=prompt
    )

    run = am.client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant.id
    )

    # Wait for completion
    while run.status != "completed":
        time.sleep(1)
        run = am.client.beta.threads.runs.retrieve(
            thread_id=thread.id,
            run_id=run.id
        )

    messages = am.client.beta.threads.messages.list(thread_id=thread.id).data
    # Get last assistant message (response)
    for m in reversed(messages):
        if m.role == "assistant":
            # Message content may be a list of blocks; join if so
            if isinstance(m.content, list):
                blocks = []
                for block in m.content:
                    text_val = getattr(block, "text", None)
                    if text_val is not None:
                        blocks.append(text_val)
                    else:
                        blocks.append(str(block))
                return "\n\n".join(str(b) for b in blocks)
            else:
                return str(m.content)
    return "No answer returned."
