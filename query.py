import argparse
import time
from configManager    import ConfigManager
from assistantManager import AssistantManager

def run_query(state: str, prompt: str):
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
    answer = [m.content for m in messages if m.role == "assistant"][-1]
    print(answer)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--state",
        required=True,
        help="State code to filter by, e.g. MT or WY"
    )
    parser.add_argument(
        "--prompt",
        required=True,
        help="Your question about the regulations"
    )
    args = parser.parse_args()
    run_query(args.state, args.prompt)
