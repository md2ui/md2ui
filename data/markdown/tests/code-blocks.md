# Code blocks

## Python

```python
from dataclasses import dataclass

@dataclass
class Account:
    owner: str
    balance: float = 0.0

def deposit(account: Account, amount: float) -> float:
    # The source remains literal Markdown-safe code.
    account.balance += amount
    return account.balance
```

## JSON

```json
{
  "status": "ready",
  "retries": 3,
  "enabled": true
}
```

## Plain indented code

    no language is guessed
    unknown tokens keep the Code Block text color
