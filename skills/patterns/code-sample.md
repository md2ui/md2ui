---
name: code-sample
description: A snippet to copy under its title, with the languages it comes in and the actions on it; use for an API call, a config file or a command in documentation or a how-to.
---
# Code sample

**Use for:** source the user will copy and run, named by what it does. **Not for:** a status or a short label, which is a chip (`text.md`).

```markdown
### Send a test event ... [`Explain`](agent:explain?block=test-event)
[`Python`](agent:show-code?lang=python) *[`Node`](agent:show-code?lang=node)* *[`curl`](agent:show-code?lang=curl)*
~~~python
import os
import tidewire

hooks = tidewire.Webhooks(api_key=os.environ["TIDEWIRE_KEY"])
hooks.send_test(endpoint_id="ep_42", event="order.paid")
~~~
```

| Write | Means |
|---|---|
| `` *[`Label`](/x)* `` | a language not shown, beside the one that is |

**Why each marker**
- The heading is glued to the fence, so the section is the panel and its heading the title strip; every block has its own copy button — `code-blocks.md`.
- The fence names its language, which selects the syntax colour — `code-blocks.md`.
- The languages are a tab strip: the one shown is the main action and the rest quieter, in the spellings for their place; a pick comes back and you send the sample in that language — `elements.md`.
- An action on the sample is a minor action at the title's edge — `elements.md`.
- Write the source as it is; a long line scrolls and a long listing fades — `code-blocks.md`.
