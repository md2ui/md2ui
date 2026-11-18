# Tasks

Each task is what a user asked, plus what your tools returned. Answer each as the md2ui
document you would show that user.

<!-- The data is real tool output, never invented: read 2026-11-05 from the Burger Shop
demo's own services (`cart_view`, `order_view` and its product catalogue), a mock of a real API
with sample data. Each task asks in the user's words, never in the notes' words. What counts as
right is in README.md, which the agents never see. Keep it out of this file: the intro and every
task here are sent to the agent verbatim. -->

## totals1-cart
"What's in my cart?" Your tool `get_cart` returned:
- Classic Smash (burgers), $9.50 each, quantity 2, line total $19.00, photo https://images.unsplash.com/photo-1568901346375-23c9450c58cd
- Crispy Fries (sides), $3.90 each, quantity 1, line total $3.90, photo https://images.unsplash.com/photo-1630384060421-cb20d0e0649d
- Strawberry Shake (shakes), $5.50 each, quantity 1, line total $5.50, photo https://images.unsplash.com/photo-1579954115545-a95591f28bfc
- item count 4; subtotal $28.40; delivery $0.00 (free over $25.00); total $28.40
Your tools can also start checkout (`open_checkout`) and show the menu (`catalog`).

## totals2-receipt
"Can I see the receipt for my order from October 23?" Your tool `get_order` returned:
- order BS-1037, delivered; placed Oct 23 at 12:30 PM, arrived 12:42 PM; rider Jordan; paid with Visa •••• 4242
- Golden Sesame Double × 1, $12.90
- Crispy Fries × 1, $3.90
- subtotal $16.80; delivery $2.99; total $19.79
Your tools can also put a past order back in the cart (`reorder`).

## totals3-refund
"I cancelled an order on October 28. What did I get back?" Your tool `get_order` returned:
- order BS-1039, cancelled at 9:12 PM ("Changed my mind"); placed Oct 28 at 9:10 PM; refunded to Visa •••• 4242
- Smokehouse × 1, $11.50
- Classic Smash × 1, $9.50
- Cookies & Cream Shake × 2, $11.80
- subtotal $32.80; delivery $0.00; total $32.80
Your tools can also put a past order back in the cart (`reorder`).

## totals5-menu
"Which burgers do you have for under $10?" Your tool `find_products` returned:
- Classic Smash, $9.50
- Sunset Crunch, $9.90
- Hearty Classic, $8.90
Your tools can also add a product to the cart (`update_cart`).
