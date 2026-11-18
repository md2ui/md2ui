# ADR-613: The state frame carries words for the client's chrome

**Status:** active (prototype)
**Domain:** CLI tools and shells
**Read when:** you add a key to the state frame `s`; change what the prompt bar's placeholder
or the working animation says; or change the demo plugin's hooks.

Amends [ADR-601](ADR-601-the-wire-carries-markdown-and-references.md), which says the agent
never writes the state. The frames and their caps are `protocol/README.md`; the code is
`mcp_demo.py` (`ask`, `_Demo.activity`), `mcp_demo_activity.py` (the hook's route),
`wire_client.StateWords` and `app_prompt.PromptBar`.

## Decision

**A state frame may carry words for the client's chrome, never for the document.** Each holds
until the next state frame, and a frame without it clears it:

- **`ph`, with `l`: the question the agent is waiting on.** The agent passes `ask` to `show` or
  `mark`; the server says it on every listen until the agent's next `show` or `mark`, and the
  window shows it as the empty field's placeholder. The page asks for nothing: there is still no
  text field in the document, and the answer is an ordinary prompt `p`.
- **`n`, with `w`: the step the agent is on**, a short label ("Edit app.py", "Run the gate"),
  drawn as a pill under the working animation. In Claude Code a `PreToolUse` hook in the
  md2ui-demo plugin posts it; elsewhere nothing does, and the window shows the animation alone.
  A step that arrives in any other state is dropped, and each one re-arms `w`'s deadline, since
  the agent is plainly still working.

**A label is a value, not narration, and never content.** A Bash call's own `description`, else
the tool and a file's basename, else the tool; never a command, a path, a pattern or a URL. On
by default; the plugin has a setting to turn it off.

**The hook finds its server by the Claude Code session id.** Claude Code puts
`CLAUDE_CODE_SESSION_ID` in its MCP servers' environment, and the same id is a hook's
`session_id`. The server writes a file named by that id, holding the URL to post to and its
secret, readable by the user alone, and removes it on close.

## Why

- **The question removes the guess, not the turn.** A prompt already says which page it was
  typed at (`typed_on`); `ph` says which question on it, because the agent named the one it is
  waiting on.
- **Chrome is the frontend's.** Both are words about the conversation, not the answer, so they
  ride the state frame, which every frontend reads, and a frontend that ignores them loses
  nothing.

## Considered and rejected

- **A page that asks for its answer itself**: a document requesting text, which md2ui keeps
  out.
- **Finding the server by the parent process**: `uv run` stands between Claude Code and the
  server.

## Constraint created

- The `ask` teaching in `show`'s description is kept on evals (ADR-502): a change to it is
  measured again.

## Reconsider when

- Claude Code changes how a server learns its session (a `/clear` that keeps the server but
  changes the hook's id would silence the line; unprobed).
- A host other than Claude Code can report steps.
