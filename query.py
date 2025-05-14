import argparse
import time
from configManager    import ConfigManager
from assistantManager import AssistantManager

def run_query(state: str, prompt: str):
    # 1) Load shared config & managers
    cfg = ConfigManager()
    am  = AssistantManager(cfg)

    # 2) Load (or create) your Assistant
    assistant = am.get_or_create_assistant(cfg.assistant_name)

    # 3) Create a new thread via the OpenAI client
    thread = am.client.beta.threads.create()

    # 4) Instruct it to restrict retrieval to the given state
    am.client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=f"Please restrict retrieval to documents tagged state={state.upper()}."
    )

    # 5) Send the actual user prompt
    am.client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=prompt
    )

    # 6) Start the assistant run
    run = am.client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant.id
    )

    # 7) Poll until the run is complete
    while run.status != "completed":
        time.sleep(1)
        run = am.client.beta.threads.runs.retrieve(
            thread_id=thread.id,
            run_id=run.id
        )

    # 8) Retrieve all messages and print the assistant’s final reply
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
