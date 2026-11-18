<!-- ESCAPES THAT DECLINE A READING.

     Two escapes live in this pipeline and they say opposite things, told apart
     by which character carries them — and, for the separators, by whether the
     character is doing any separating where it sits:

       \-  \|  \:  \,  \.   spaced: do not SPLIT here — detection sees THROUGH it
       \/  \%  \$           this token is TEXT — detection STOPS
       \-  \|  \:  \,  \.   tight (no space either side): this token is TEXT too

     "This token is text" means no data point, and therefore no bar, no ring,
     no day chip, no chart point and no stat tile. The structure the author
     wrote is untouched — a key-value pair stays a pair — and the backslash is
     markup, so it is never drawn.

     Every case below sits beside the unescaped twin that must still draw. If a
     twin ever stops drawing, this file is where the snapshot says so. -->

## Ratios

4/8

4\/8

750/1800 Kcal

750\/1800 Kcal

## Percentages

Elapsed: 45%

Elapsed: 45\%

## Currency

$412M

\$412M

## The pair survives the escape

_Expires:_ 12/26

_Expires:_ 12\/26

Minutes: 7\/8

## Charts

<!-- Three Key: percentage rows are a chart. -->

- Jan: 75%
- Feb: 50%
- Mar: 100%

<!-- Escape them all and there is no chart, and no per-row bar either. -->

- Jan: 75\%
- Feb: 50\%
- Mar: 100\%

<!-- Escape ONE and it leaves the run the way any other non-percentage row
     would: the remaining contiguous three still chart. -->

- Jan: 75\%
- Feb: 50%
- Mar: 100%
- Apr: 20%

## Day chips

<!-- The dash is the chip; the space is how prose writes a date, so it stays
     text; and a TIGHT escape declines even the dash. -->

Mon-15

Mon 15

Mon\-15

Jun-5 | Jun-6 | Jun-7

## A spaced separator escape is the OTHER meaning

<!-- Detection still sees through these: the datapoint each one protects is
     exactly what the escape is for. -->

February 04\, 9:17 PM

8:00 AM \- 9:00 AM

Fri, Aug 14 \- Sun, Aug 16
