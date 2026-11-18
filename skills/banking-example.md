---
name: md2ui-banking-example
description: A worked account overview — account sections, a named premium card, transaction rows with muted dates, and a summary band.
---

# Worked example: an account overview

Start here when an answer needs account figures, card details, transaction rows and summary
cards together.

## What this example delivers

The account sections sit side by side at 1600 and stack at 767. The summary's repeated
sections grid four across at 1600 and two across at 767. Transaction dates stay muted beneath
their names; the expiry stays text beneath its label. The premium card has a named
gradient style, while the other cards share one heading style.

This composition uses account sections and a responsive summary grid. Preserve
the information when adapting it; render again when nesting rows in a narrower card.

## content.md

```md
# Account overview

## Balance
_Total Balance_
___$24,582.50___

_Income_ : `+$8,450.00` ... _Expenses_ : `-$2,340.50`

## Premium Card {#premium-1}
___$12,458.75___

`**** **** **** 9012`

_Card Holder:_ SARAH ANDERSON
_Expires:_ 12\/26

## Recent Transactions

- *🛍️* - **Online Order** : _Yesterday, 3:45 PM_ ... `-$189.99` : _Shopping_
- *⚡* - **Electricity Bill** : _Nov 17, 2:15 PM_ ... `-$85.00` : _Utilities_

# Summary

## Active Loans
___$8,500___
_2 active loans_

## Investments
___$15,240___
_+8.2% this month_

## Savings Goal
___68%___
_$13,600 of $20,000_

## Rewards Points
___8,450___
_Redeem for $84.50_
```

The `# Summary` starts a new band at the same level as `# Account overview`, so the
summaries belong to their own band. Each summary has the same
heading/value/caption shape. The expiry's slash is escaped; dates inside transactions
are prose. The separated, wrapped emoji selects the Secondary badge variant.

## The look

The premium card's gradient, the amounts' colours and the badge colours are the theme's.
`{#premium-1}` in the Markdown selects a named card style the theme defines.
