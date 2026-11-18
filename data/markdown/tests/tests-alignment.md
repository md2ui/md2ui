<!-- The `...` SPRING: an authored expanding gap that pushes what sits on
     either side of it toward opposite edges. Spacing is the lenient rule the
     row separators use — a space on both sides mid-line, with the start and
     the end of the line counting as boundaries. -->

<!-- One spring: everything before it goes left, everything after it right.
     The `-` still separates B from C, and still draws per ## Separators. -->
A ... B - C

<!-- A spring on each side: the content between them centres. -->
... A ...

<!-- A leading spring: the whole line is pushed right. -->
... A - B - C

<!-- A trailing spring: the whole line is pushed left (visible when the theme
     aligns centre or right). -->
A - B ...

<!-- Two springs, three regions: left, centre, right. -->
A ... B ... C

<!-- Only A is placed to the left, and G to the right, the rest is centered -->
A ... B ... C ... D ... E ... F ... G

---

<!-- The shapes this was written for. -->
Subtotal ... $42.50

`* New`

`A` `B` `C`

**Home in Raito** ... `⭐ New`

<!-- This does not produce chip/pill and second explicit separator ` - ` is redundant-->
**Home in Raito** ... `* New`

**Home in Raito** - `* New`

**Home in Raito** ... *[Rent](/rent)*

**Jonas Whitfield** ... Product Designer

Jul 5 - Dec 5 ... $19,357

... Read more

Home ... About ... Contact

---

<!-- A spaced colon stacks its pieces into a column; the spring aligns those
     COLUMNS as units, and the alignment cascades onto the leaves inside. -->
450 : Projects done ... 35 : Happy users

94% : Accuracy ... 1,293 : Customers ... 12 : Awards

94% : Accuracy | 1,293 : Customers | 12 : Awards

---

_Accuracy_: ... ___94%___ ... _Customers_: ... ___1,293___ ... _Awards_: ... ___12___

_Accuracy_ : ___94%___ ... _Customers_ : ___1,293___ ... _Awards_ : ___12___


_Accuracy_: ... ___94%___ ... | ... _Customers_: ... ___1,293___ ... | ... _Awards_: ... ___12___

---

<!-- Key: ... Value — the spring after a key-value colon is not a region
     boundary. It puts the PAIR on one row, key left and value right, instead
     of the default stack. -->
Key: ... Value

Order ID: ... ORD-2026-02-04-78923

**Total:** ... $128.00

<!-- ...but a line where a separator would claim precedence keeps the spring as
     a region boundary, so it is never consumed silently. -->
A - Key: ... Value

Discount: ... -$10.80 : _(10% off on 5+ avocados)_

<!-- List -->
___

## 5. **Fresh Avocados** - Local Farm  
   - Quantity: ... 6 pieces 
   - ---
   - Price: ... $18.00 each  
   - ---
   - Subtotal: ... $108.00  
   - ---
   - Discount: ... -$10.80 : _(10% off on 5+ avocados)_
   - ---
   - **Total**: ... $97.20 MXN ✨

***

## 5. **Fresh Avocados** - Local Farm  
   - ---
   - __Quantity__ ... **6 pieces**
   - ---
   - __Price__ ... **$18.00 each**
   - ---
   - __Subtotal__ ... **$108.00**
   - ---
   - __Discount__ ... **-$10.80** : _(10% off on 5+ avocados)_
   - ---
   - **Total** ... ___$97.20 MXN___ ✨

***

<!-- NEGATIVES — none of these is a spring, except the last two: since 2026-10-04 (`8355178d`) a
     spaced ` ... ` springs on any line, prose or not. -->

<!-- Four dots are an author writing dots. -->
A .... B

<!-- No space: an ellipsis inside a word. -->
wait...what

<!-- Backticks protect their contents, exactly as they do for ` - `. -->
`Total ... $128`

<!-- ...and so do quotes. -->
"Total ... $128"

<!-- A pause in a sentence: a spring all the same — two pieces pushed apart. A literal pause is
     `…` or `\...`. -->
He paused ... unsure what to say next.

<!-- A trailing spring: the line goes left. A literal truncation is `Loading...` or `Loading \...`. -->
Loading your dashboard ...


<!-- Headings -->

# Transaction History ... [`…`](/more)
***

## Transaction History ... [`…`](/more)
***

### Transaction History ... [`…`](/more)
***

#### Transaction History ... [`…`](/more)
***

##### Transaction History ... [`…`](/more)
***

###### Transaction History ... [`…`](/more)
***


... [[35%]](agent:set-effects?channel=music)
