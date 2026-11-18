<!-- Feed slots: every place a feed writes words, in every tier. Each `[words](feed:name)`
     draws exactly as its words would without the link: Status's chip a pill, the
     key line's value plain text, Arrives a stacked display stat, Ready a colon-column
     stat, the bold, caption, struck and ___hero___ lines in their tiers, the sentence's
     slot bold inside it, Courier's chip in a colon column and the order's chip across
     a spring. Track's label is fed by `md2ui.feed`: it stays a button. Before the
     slots were read, each drew as a link or a button variant (a dark pill for the stat,
     the caption and the hero, a grey disabled pill for the struck line), and each was a
     target ahead of Track. -->

## Order BS-1043

[`Preparing`](feed:status)

Placed: [3:41 PM](feed:placed)

_Arrives_
___[3:53 PM](feed:arrives)___

_Ready_ : ___[3:48 PM](feed:ready)___

**[Packed with care](feed:packed)**

_[Updated a minute ago](feed:updated)_

~~[Pickup at the counter](feed:pickup)~~

___[12 min](feed:eta)___

Your order arrives at **[3:53 PM](feed:sentence)** today.

[`Sam`](feed:courier) : _Courier_

Order BS-1043 ... [`On the way`](feed:leg)

[Track · Preparing](agent:track?id=BS-1043&md2ui.feed=track) | [Cancel](agent:cancel?id=BS-1043)
