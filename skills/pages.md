---
name: md2ui-pages
description: Whole example pages, each rendered. Read one only when you are writing a whole page, never to copy it.
---

# Whole pages

Each of these is a complete document that renders as intended with its own theme. They are
**references for how sections compose into a page**, not templates: your answer has its own
content and its own sections, and the user's theme owns the look. A section shape on its
own is cheaper to read, and lives in `patterns`. Their names, places and figures are made up;
the shape is what each one shows. Where a page shows fewer figures than your data has, keep
yours: a review count, a discount, a second date.

Read one with `guide("pages/<name>")`, or open `pages/<name>.md` beside this note.

Each leads with one thing and shows the rest smaller, as real designs do: find the kind of page
you are writing, and see what it leads with and how its secondary items are shown.

| kind | name | use it for | leads with, then | about |
|---|---|---|---|---|
| dashboard | `widget-board` | a first screen of many unlike things, each its own tile | each tile its own number or title; rings, bars, charts, chips, a calendar and a switch | 0.6k tokens |
| dashboard | `home-board` | a day at a glance: agenda, weather, travel, music, tasks | 15 tiles, each with one lead: a music player, an agenda with coloured gutters, maps | 0.5k tokens |
| money | `wallet-overview` | one card or account, or one person's money: its balance, what is due, recent activity | one balance as the hero number; the rest as rows and smaller amounts | 0.5k tokens |
| money | `money-dashboard` | a bank's whole home screen across many products at once: accounts, a card, loans, savings and rewards side by side | the total balance and a card side by side; quick actions, spending, recent transactions as rows, then four small figure tiles | 0.3k tokens |
| markets | `watchlist` | prices the user follows: a watchlist's day, one ticker over time | each ticker a row with its day as a small line and its change as a chip; one ticker's detail: its price, a range selector, a line chart and its figures; the other tickers' figures stay too, smaller | 0.3k tokens |
| weather | `current-conditions` | the weather in one place, when the news is what it is like now | the current temperature, large; stats, hourly, then the days as rows | 0.3k tokens |
| weather | `hours-ahead` | when the news is how the next hours turn: rain moving in, a cold night, a storm's hours | the temperature now beside a few figures; the hours as a line chart, then the days as a strip of small tiles | 0.1k tokens |
| weather | `places` | several places at once, each with its local time | one place large; the others as rows with their time and temperature; the details as figure tiles | 0.1k tokens |
| catalog | `dish-grid` | many items of one kind the user picks by their picture | equal image cards, the chips and save button over each photo, the name and price below, the price as its biggest text | 0.4k tokens |
| catalog | `shelves` | items that fall into groups the user compares: two places, categories, why each is suggested | each group its own heading over a shelf of the same small card, every item of the group and every figure it came with kept | 0.6k tokens |
| detail | `artist-page` | one person or group and everything they made | a banner image card; songs as ranked rows with small covers, albums and artists as cover shelves, merch as rows | 1.3k tokens |
| detail | `garment-detail` | one product to buy, with choices | the product's pictures beside its name and price; colour, size and quantity choices, buy buttons, then reviews as rows, a score card and related products as a grid | 1.2k tokens |
| detail | `stay-detail` | one place to stay, or any item with a long description and reviews | the title over its photo grid; highlights with icons, amenities, a date calendar, rating bars, reviews with small avatars, the host card and house rules | 2.7k tokens |
| documentation | `api-reference` | technical reference: prose, code and parameters | each section's title and prose; code blocks with copy and ask buttons, parameter rows, status-code tables | 3.3k tokens |
| landing | `publisher-console` | a product's front page with a few features | a headline; offers as cards with small icons | 1.5k tokens |
| landing | `workspace-landing` | a long product page that tells its story section by section | a hero; four feature sections with screenshots, an AI section | 2.2k tokens |

## Recipes

A recipe is a starting point for the order and weight of the content you already have, by kind
of page: the data decides, all of it stays, and a section your data lacks is left out. Each row
reads in page order: the one **primary** section the page is about, then the **secondary**
sections that serve it, then the **additional** ones that complete it. A name in backticks is a
pattern (`guide("patterns/<name>")`); plain words are an element from the core note's table.
The last column names the page above that shows the recipe whole.

| kind | primary | secondary | additional | shown in |
|---|---|---|---|---|
| dashboard | `hero-figure` or `kpis`, or the one tile the day is about: a player, today's events | `agenda`, `status-list`, `inbox`, rings, bars and `chart-card`, one tile each | `shortcuts`, `quick-actions` | `widget-board`, `home-board` |
| money, a statement | the balance or total as `hero-figure`, with the card or account it belongs to | `quick-actions`; transactions as `people` rows; spending as `chart-card` | the other figures as `kpis`; what is due | `wallet-overview`, `money-dashboard` |
| markets | the ticker the question is about: its price, its change and its line over the range, as `chart-card` | the other tickers as `ticker-rows` | its figures as `figure-tiles`; the other tickers' figures | `watchlist` |
| weather, now | the temperature now as `hero-figure` | the figures that matter today as `figure-tiles`; the hours | the days as rows | `current-conditions` |
| weather, the next hours | the temperature now with a few figures | the hours as `chart-card` | the days | `hours-ahead` |
| weather, several places | the place asked about | the other places as rows with their local time and temperature | the details as `figure-tiles` | `places` |
| catalog | the items as `listing` or `picture-rows`, every figure each came with | groups, each a `shelf`, when the items fall into groups | `suggestions` for filters and follow-ups | `dish-grid`, `shelves` |
| detail, a product | `gallery` with its name and price, or `split` | `buy-box`; `specs` | `reviews`; related items as a `shelf` | `garment-detail` |
| detail, a place to stay | its title over its photos | highlights, amenities as `specs`, a `month-calendar` for dates | `reviews`, the host as `profile`, house rules | `stay-detail` |
| detail, a person or group and their work | `profile`, or a banner picture | their best-known work as ranked `people` rows | the rest of their work, a `shelf` each | `artist-page` |
| profile | `profile` | `specs` for the facts about them; `quick-actions` to call, message or share | `people` they know or work with; `feed` of what they made | none (partly `artist-page`) |
| documentation | each section's title and paragraphs | `code-sample` for code; parameters as `reference-list` | status codes and other tables | `api-reference` |
| landing | `hero`, or a headline with `split` when the product has a picture | `features`, or a `split` section each; how it works as `steps` | `testimonials`; `call-to-action`; links as `directory` | `publisher-console`, `workspace-landing` |
| recommendations | `feed`, or `listing` when each has a picture and a price | why each is suggested, as a paragraph or the `shelf` it sits in | `comparison` of the top few; `suggestions` | `shelves`, partly |
| how-to guide | `steps` | what you need, as `task-list` or `specs` | tips about named things as `guide`; `suggestions` | none |
| cooking recipe | the dish as `split`, with its time and servings | ingredients as `task-list`; method as `steps` | tips and variations as `guide` | none |
| report, summary | the conclusion, as a paragraph and its `kpis` | `chart-card`, tables and `status-list` for what it rests on | method, sources, open questions | none |
| schedule | today's `agenda`, or the trip's `itinerary` | `month-calendar` when free and busy days matter | `task-list` for what to prepare | none |
| account settings | `profile` for whose account it is | settings as toggle rows; plan and limits as `specs` | help and policy links as `directory` | none |
| article | `article`: its lead picture and paragraphs | quotes; `split` for a point with its picture | related reads as `feed`; `suggestions` | none |

Renders of two dashboard boards, written against the designs beside them, are in [`renders/`](renders/README.md).
