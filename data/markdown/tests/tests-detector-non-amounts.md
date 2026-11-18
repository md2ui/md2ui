<!-- LINES THE DETECTOR ONCE COULD NOT READ.

     Each of these used to stop the whole document from grouping: a parser
     raised instead of answering "not this type". A string the detector cannot
     read as a value is not a value; it stays text, and the rest of the
     document is untouched. -->

## Dots before a trailing currency symbol

<!-- Three dot groups are not an amount: the date reads as a DATE and the €
     stays text. -->
Price: 25.12.2021 €

<!-- Same shape as a version: a VERSION, with the € left as text. -->
Build: 1.2.3 €

<!-- Control: dots that each group three digits are European thousands, one
     CURRENCY. -->
Total: 1.234.567 €

## A comma datetime with a bare hour and a year

<!-- One DATE, 15:00. -->
Meeting: February 4, 2026, 3 PM

<!-- Control: the same with minutes. -->
Call: February 4, 2026, 3:00 PM
