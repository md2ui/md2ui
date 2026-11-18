<!-- A stacked row's caption is one muted line, whatever it holds (ADR-205,
2026-11-05; findings/stacked-caption-divides-at-bullet, md2ui-ts only): spaced
bullets and a colon inside `_..._` divide nothing, as commas do. Each row is a
lead title over its muted caption, with the total at the far edge. -->

## 1. spaced bullets

- __Order BS-1040__ : _Nov 1 • 4 items • Classic Smash_ ... **$30.80**

## 2. a colon

- __Order BS-1040__ : _Nov 1, 4 items: Classic Smash_ ... **$30.80**

## 3. commas only

- __Order BS-1040__ : _Nov 1, 4 items, Classic Smash_ ... **$30.80**
