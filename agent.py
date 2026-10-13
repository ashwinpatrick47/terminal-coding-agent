import json
import os
import urllib.request
import urllib.error


# ============================================================
# SAFETY: the agent may only touch files inside this folder
# ============================================================

WORKSPACE = os.path.dirname(os.path.realpath(__file__))


def is_inside_workspace(path):
    full_path = os.path.realpath(os.path.join(WORKSPACE, path))
    return full_path == WORKSPACE or full_path.startswith(WORKSPACE + os.sep)


# ============================================================
# TOOLS: the things the agent can do
# ============================================================

def list_files(path):
    try:
        names = os.listdir(path)
        return "\n".join(names)
    except OSError as e:
        return f"ERROR: {e}"


def read_files(path):
    try:
        with open(path) as file:
            return file.read()
    except (OSError, UnicodeDecodeError) as e:
        return f"ERROR: {e}"


def write_file(path, content):
    if not is_inside_workspace(path):
        return f"ERROR: {path} is outside and cannot be modified."
    if os.path.basename(path) == "agent.py":
        return "ERROR: Cannot modify this code."
    
    try:
        with open(os.path.join(WORKSPACE, path), "w") as file:
            file.write(content)
    except OSError as e:
        return f"ERROR: {e}"

    return f"Wrote {len(content)} characters to {path}"


TOOLS = {
    "list_files": list_files,
    "read_files": read_files,
}


# ============================================================
# MODEL: talking to Qwen through Ollama
# ============================================================

SYSTEM_PROMPT = """You are a coding agent that reads and writes files within this folder.

If the user is just chatting or asks a general question, do NOT use a tool. Answer directly:
User: hi
{"done": "Hi! I can list, read and write files in this folder. What would you like to do?"}
User: what is 2+2?
{"done": "2 + 2 is 4."}

If the task is about a file, you MUST use a tool first. Never guess what a file says. Tools:
list_files: lists the files in a folder. arg is the folder, like "."
read_files: reads a file. arg is the name of the file to read
write_file: writes a file. arg is the file name and content is the text to write

Always reply with one JSON object. To use a tool:
{"tool": "read_files", "arg": "notes.txt"}
{"tool": "write_file", "arg": "hello.txt", "content": "hi"}
After you get the tool result, give your final answer in "done", based only on the tool result.
"""


def history_to_messages(history):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    for msg in history:
        if msg['role'] == "user":
            text = msg["content"]
            messages.append({"role": "user", "content": text})

        elif msg['role'] == 'assistant':
            choice = {"tool": msg["tool"], "arg": msg["arg"]}
            text = json.dumps(choice)
            messages.append({"role": "assistant", "content": text})

        else:
            text = "Tool result:\n" + msg["content"][:2000]
            messages.append({"role": "user", "content": text})

    return messages

            

def ask_model(messages):
    data = {
        "model": "qwen2.5:1.5b",
        "messages": messages,
        "stream": False,
        "format": "json",
    }
    request = urllib.request.Request(
        "http://localhost:11434/api/chat",
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request) as response:
            reply = json.loads(response.read())
    except urllib.error.URLError as e:
        return json.dumps({"done": f"ERROR: could not get an answer from Qwen ({e})"})
    return reply["message"]["content"]


# ============================================================
# BRAIN: decides what to do next
# (Task 4: write the new brain here)
# ============================================================
def brain(history):
    messages = history_to_messages(history)    
    reply = ask_model(messages)
    print(f"Qwen said: {reply}")

    try:
        decision = json.loads(reply)
    except json.JSONDecodeError:
        decision = {}

    if "done" in decision:
        return decision

    else:
        if "tool" in decision and "arg" in decision:
            return decision

    return {"tool": "bad_reply", "arg": "Qwen's reply was not in the right format"}


# ============================================================
# LOOP: ask the brain, run the tool, remember, repeat
# ============================================================

def run_agent(task, max_turns):
    history = [{"role": "user", "content": task}]

    for turn in range(1, max_turns + 1):
        decision = brain(history)

        if "done" in decision:
            print(decision["done"])
            return

        name = decision["tool"]
        arg = decision["arg"]

        if name == "write_file":
            if "content" in decision:

                result = write_file(arg, decision.get("content", " "))
            else:
                result = "ERROR write_file needs content"
        elif name in TOOLS:
            result = TOOLS[name](arg)
        else:
            result = f"ERROR: there is no tool called {name}"

        history.append({"role": "assistant", "tool": name, "arg": arg})
        history.append({"role": "tool", "tool": name, "content": result})

        print(f"Turn {turn}: {name}({arg}) gave back {len(result)} characters")

    print(f"Stopped: hit the turn limit ({max_turns})")


while True:
    task = input("You: ")
    if (task.lower() == "quit" or task.lower() == "q"):
        break
    else:
        run_agent(task, max_turns=3)

