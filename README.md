# Terminal Coding Agent

A small coding agent that runs in the terminal. You type a task, and a local AI model (Qwen 2.5 3B, running on your own machine through [Ollama](https://ollama.com)) decides which tools to use to complete it. Everything is plain Python with no extra packages, it runs offline, and it costs nothing to use.

```
You: how many lines are in agent.py?
Qwen said: {"tool": "run_shell", "arg": "wc -l agent.py"}
Turn 1: run_shell(wc -l agent.py) gave back 30 characters
Qwen said: {"done": "agent.py has 223 lines."}
agent.py has 223 lines.

You: delete notes.txt using rm
Qwen said: {"tool": "run_shell", "arg": "rm notes.txt"}
Turn 1: run_shell(rm notes.txt) gave back 35 characters
Qwen said: {"done": "I'm sorry, but 'rm' is not an allowed command. The file 'notes.txt' cannot be deleted directly."}
```

## What it can do

- **List** the files in a folder
- **Read** a file
- **Write** a file
- **Run a terminal command** from a short allowlist (`ls`, `cat`, `pwd`, `grep`, `wc`, `head`, `tail`, `git status`, `git diff`, `git log --oneline`)
- **Chat**: general questions are answered directly, without using a tool

## How it works

The agent runs a loop:

1. **History:** every task starts a `history` list holding the user's request.
2. **Brain:** the history is converted into chat messages and sent to Qwen together with a system prompt that describes the tools. Qwen must reply with a single JSON object: either `{"tool": ..., "arg": ...}` to use a tool, or `{"done": ...}` to finish.
3. **Act:** the loop runs the chosen tool and adds two entries to the history: what the model chose, and what the tool returned.
4. **Repeat** until the model replies `done` or the turn limit is reached.

The model never touches files directly. It can only *ask* for one of the tools, and the Python code decides whether to run it.

## Safety and error handling

- **Workspace guard:** `write_file` refuses any path outside the project folder. Paths are resolved with `os.path.realpath` first, so tricks like `../file.txt` are blocked, and the check uses `WORKSPACE + os.sep` so a sibling folder such as `my_agent_evil/` doesn't count as "inside".
- **Self-protection:** the agent cannot overwrite its own code (`agent.py`). I added this after the model overwrote it during testing.
- **No content, no write:** if the model asks to write a file but leaves out the content, it gets an error instead of blanking the file.
- **Errors are text, not crashes:** tools return `"ERROR: ..."` messages instead of raising exceptions, so the model can see what went wrong and try something else. This covers missing files, folders passed where a file is expected, unreadable binary files, unknown tool names, badly formatted model replies, and Ollama being down or returning an error.
- **Shell allowlist:** `run_shell` only runs commands on a fixed allowlist, and anything else is refused. I chose an allowlist over a blocklist (blocking `rm`, `curl`, ...) because there are endless ways to write a dangerous command, but the list of safe ones is short. Some details:
  - Commands run with `subprocess.run` on a list of words, never through a shell, so `;`, `&&` and `|` can't chain a second command (`ls && rm notes.txt` just passes `&&` and `rm` to `ls` as file names).
  - `git` is limited to three **exact** commands. While testing I found that `git diff --output=file.txt` writes a file, so allowing "any `git diff`" would have been a hole.
  - `python3` is deliberately not allowed: the agent can already write files, so being able to run Python would let it write and run any program.
  - Commands time out after 10 seconds (for example `tail -f`).
- **Turn limit:** each task stops after a fixed number of turns, so a confused model can't loop forever.
- **Temperature 0:** the model always picks its most likely answer, which makes it more consistent at following the rules.

## How to run it

1. Install [Ollama](https://ollama.com) and open the app.
2. Download the model (about 1.9 GB, one time only):
   ```
   ollama pull qwen2.5:3b
   ```
3. Run the agent with Python 3.9 or newer:
   ```
   python3 agent.py
   ```
4. Type a task at the `You:` prompt. Type `quit` or `q` to exit.

## Limitations

- **Small model.** On my 10-task test, the 3B model got 8 right, compared with about half for the 1.5B model I started with (which looped, misread files, and wrote files nobody asked for). It still makes mistakes, and it states made-up "facts" confidently on general-knowledge questions, so don't trust those answers.
- **Never trust what the model says it did.** With the 1.5B model, `rm` was blocked but the model still replied "The file has been deleted." The guards are in the Python code for exactly this reason.
- **Only writes are guarded.** `read_files`, `list_files` and the read-only shell commands (like `cat`) are not limited to the project folder yet.
- **Short tasks only.** The turn limit is 3, and tool results are cut to 2000 characters before being sent to the model, so the model only sees the start of long files.
- **Memory.** On an 8 GB Mac, having two models loaded at once can make Ollama run out of memory and return an error. The agent reports the error instead of crashing; `ollama stop <model>` frees the memory.

## What I learned

- The hard part of an agent isn't calling the model. It's the loop around it: turning failures into messages, limiting turns, and keeping the model inside safe boundaries.
- Small models copy the examples in a prompt word for word, so prompt examples need to be chosen carefully and tested.
- Guardrails have to be tested against what the model actually does, not only what you expect it to do. Two of my guard bugs were a single wrong indentation level, and they only showed up when I tried to break the guard.
- A command that sounds read-only (`git diff`) can still write files, so allowlists should be exact.
