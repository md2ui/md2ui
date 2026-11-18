# ADR-204: A chart value is a number; its unit is declared

**Status:** active
**Domain:** markdown grouper
**Read when:** a run of values does not chart, a line stays text, or you are about to add a unit
a chart accepts as written.

## Decision

A bar chart and a line take the same values, and declare a unit the same way.

1. **Three forms stand alone**, because each is a number with a mark: a percentage (`40%`), a
   currency (`$220.06`, `200 EUR`), and a magnitude (`5K`, `$274.5B`).
2. **Everything else is a bare number with its unit declared once**: a short line ending in
   `(unit)` above a bar chart's rows (`Storage (GB):`), or the key of a line
   (`High (°C): 24 → 23 → 21`). That covers plain counts (`Users (count):`) and every other unit
   (`GB`, `kg`, `°C`, `km/h`).
3. **A unit written inline outside the three forms keeps the run as text** — `- Photos: 61 GB`,
   `82 kg → 80.5 kg` — and `check` says how to declare it.
4. **Plain numbers and magnitudes are one kind**, so `900` and `1.2K` share a chart; the run
   needs the declaration because a plain number is in it.
5. **A ring takes the declaration too**: `Disk (GB): 61/128` draws as `Disk: 61/128 GB` does.
   Its inline form — any one word after the ratio — stays, because it matches a position, not
   a unit list.

## Rejected alternative

A closed list of units a chart accepts as written (sizes, measurement units). An open-looking
list teaches agents that any unit works, and most do not (`24°`, `120 bpm`): every unit the
detector does not know fails silently, and knowing every unit is not possible. A strict syntax
has no such tail: the number is the value, and the author names the unit.

Two rules for one concept — a line drawing plain numbers undeclared while a bar chart requires
the declaration — must both be taught and remembered. One rule is what agents carry across
figures.

## Constraint created

- A new unit is never added to what a chart accepts as written; it is declared.
- The theme's `Value format` shows a declared unit; a value written in one of the three forms
  is drawn as written.
- The corpus keeps refused spellings beside their declared twins
  (`data/markdown/tests/tests-chart-units.md`, `tests-line-chart-text.md` /
  `tests-line-chart.md`, `tests-ring-declared-unit.md`).

## Reconsider when

A unit the detector reads reliably and agents write by default keeps being refused in real
answers often enough that declaring it costs more than the tail it would open.
