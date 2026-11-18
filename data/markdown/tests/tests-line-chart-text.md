<!-- Arrow chains that stay text, each with its `check` note (ADR-204,
     2026-10-14). Moved out of tests-line-chart.md so that file draws every
     chain (owner, 2026-10-14). Users and Weight are the refused twins of the
     declared `Users (count):` and `Weight (kg):` there: plain numbers and a
     unit written inline need the key to declare it. The rest: two values are
     a change, a numeric parenthesis is a second value, a word chain is a
     state change, mixed units, an ellipsis, `Quarters:` (plain numbers with
     no declared unit) and `->`, which is no arrow. -->
# Chains that stay text

Users: 900 → 1.2K → 3.4K → 2.9K → 5K

Weight: 82 kg (Jan) → 80.5 kg → 79 kg (Mar) → 78.2 kg (Apr)

Change: $702 → $720

Revenue: $412M (49%) → $430M → $450M

State: registered → active → deprecated

Mix: $5 → 6 EUR → $7

Gap: $702 → … → $720 → $730

Quarters: 900 (Q1) → 1.2K (Q2) → 3.4K (Q3)

Ascii: $710 -> $713 -> $720
