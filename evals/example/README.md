# example

The public example suite: four requests about money that adds up, or does not. Three answers
have a total made of parts (a cart, a receipt, a refund); one is a control, a few prices with no
sum. Taken from a suite built 2026-11-05 to measure `patterns/summary`, with the Burger Shop
demo's own data. It shows the shape of a suite; md2ui's own suites are kept privately.

A **capability** suite. The tasks and their data are in `tasks.md`, which is sent to the agents
verbatim; this file never is.

## Conditions

| condition | theme | tasks |
|---|---|---|
| root | the root `THEME.md` | all four |

## What each task scores

As of 2026-11-05. An answer is **right** when its money reads in the order the row says; the
rest of the answer is not graded here.

| task | counts as right | wrong |
|---|---|---|
| totals1-cart | the lines first, each with its amount at the edge; then subtotal and delivery (free said in words), each a label with its amount at the edge; the total last and heaviest; checkout as the main action | the total above the lines, or no heavier than them; parts run into a sentence; a total the tool did not return |
| totals2-receipt | the two lines, then subtotal, delivery and total, the total last and heaviest; how it was paid kept | the total only in prose; delivery left out; the parts not at the edge |
| totals3-refund | what was refunded is the heaviest amount, named as a refund, with where it went (Visa •••• 4242); the lines it was made of kept | the refund only in a sentence; the amount not said as refunded |
| totals5-menu | three priced items, no total, no subtotal | a sum of the three prices, which the user did not ask for |
