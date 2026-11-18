# proposals/

Features and changes **waiting for the owner's decision**. A finding reports what *is* (a
defect, a limit, a measurement). A proposal says what *could be*, and why. A plan in `plans/`
is how to build something already decided. A decision record in `decisions/` is what was
decided.

| it is | it goes |
|---|---|
| a measured defect or limit | `findings/` |
| a feature or a change of design, not yet decided | `proposals/` |
| the steps to build something decided | `plans/` |
| the decision and its reasons | `decisions/` (an ADR) |

## One proposal, one folder

```
proposals/<name>/
  README.md          the proposal; header below
  <probe>/           optional: the smallest document or render that shows the case
```

The `README.md` opens with:

```md
# <title>

**Area:** the pipeline stage, shell or docs it changes
**Status:** open | accepted | rejected
**Source:** the paths a reader would open first
```

Then: **today** (what exists, with paths and dated measurements), **the proposal**, **what it
costs** (code, teaching, compatibility), and **open questions** for the owner.

Like a finding, a proposal written by an agent is unverified until the owner reads it. Every
measured claim names its date and the command or path that reproduces it.

## When it closes

- **Accepted:** the decision goes to an ADR or the doc it changes, the work to `plans/` or a
  change. Delete the folder in the same change.
- **Rejected:** delete the folder. If it is likely to be proposed again, say *rejected, and
  why* where the next person will look (the ADR, the doc, or the module docstring).

The folder holds what is open; git holds what was.
