---
name: offer
description: One suggestion the user did not ask for, with the action that takes it up and a way to dismiss it; use for a tip, an upgrade or a setting worth turning on.
---
# Offer

**Use for:** one suggestion beside the answer, never in place of it. **Not for:** the answer itself, or several suggestions (`feed`).

```markdown
### Back up your phone every night ... [`Hide`](agent:dismiss-tip?id=backup)

Your last backup was 41 days ago. Nightly backups run on Wi-Fi while it charges.

[Turn on backups](agent:enable-backup)
```

**Why each marker**
- The title is the suggestion itself; the sentence under it is the reason, from the user's own data.
- Turning it on is the main action, at the section's foot.
- ` ... ` puts the dismiss at the title's far edge, a minor action. The spellings are the theme's: `guide("theme")`.
