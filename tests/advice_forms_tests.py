"""
Unit tests for the advice on a form written a turn at a time (advice_forms.py).

Pinned here:

  * a row of ``agent:`` buttons spelling a stepper, ➖ n ➕ or − n +, is advised a
    count, ``Quantity: ➖ [n/9] ➕``; a count already written is not;
  * a stepper an include drew is the backend's and is not advised; a stepper the
    agent typed on the same page still is;
  * a stepper whose ``agent:`` slugs a registered handler answers costs no turn and
    is not advised, nor named as the count no press carries; with no handlers, or
    another slug, it still is;
  * a count or a choice beside an ``agent:`` button with no commit press is
    advised one, naming the page's own button when it stands with the values; a
    lone slider, a checklist, and a page with a commit press are not;
  * in a cart, the first stepper is named and the press after the rows is the
    one to mark, never a row's own link to its item;
  * tabs, toggles and actions alone are never advised;
  * the advice points to ``elements/what-a-click-does`` once per session, and
    never once ``elements`` was read.

Run with: uv run python tests/advice_forms_tests.py
"""

import contextlib
import io

from md2ui import session
from md2ui.advice import FORMS, Reading, reply_issues
from md2ui.advice_forms import form_hints
from md2ui.includes import Region

_KIT = None


def _ast(markdown: str):
    global _KIT
    if _KIT is None:
        with contextlib.redirect_stdout(io.StringIO()):
            _KIT = session.load_grouping_kit()
    ast = session.group_markdown(markdown, _KIT)
    assert ast is not None
    return ast


def _advice(markdown: str, reading: Reading | None = None) -> list[str]:
    advice = (reading or Reading()).advise(_ast(markdown).to_dict(), None)
    return [a["message"] for a in advice if a["read"] == FORMS]


STEPPER = """## Bacon BBQ

$9.50

__[➖](agent:cart-remove?id=bb)__ - **2** - __[➕](agent:cart-add?id=bb)__

[Add to cart](agent:add?id=bb&md2ui.commit=1)
"""


def test_a_stepper_of_buttons_is_advised_a_count():
    [message] = _advice(STEPPER)
    assert "`Quantity: ➖ [2/9] ➕`" in message, message
    assert message.endswith("words."), message
    minus = STEPPER.replace("➖", "−").replace("➕", "+")
    assert len(_advice(minus)) == 1
    counted = STEPPER.replace(
        "__[➖](agent:cart-remove?id=bb)__ - **2** - __[➕](agent:cart-add?id=bb)__",
        "Quantity: ➖ [2/9] ➕",
    )
    assert _advice(counted) == [], counted
    print("  ✓  a stepper of buttons is advised a count; a count is not")


def test_a_stepper_an_include_drew_is_not_advised():
    cart = "### Classic Smash\n\n" + STEPPER.split("\n\n")[2] + "\n"
    page = f"## Cart\n\n{cart}\n[Checkout](agent:checkout?md2ui.commit=1)\n"
    ast = _ast(page)
    start = page.split("\n").index("### Classic Smash")
    region = (Region("{{cart}}", start, start + 3),)
    issues = reply_issues(page, ast, None, Reading(), None, region)
    assert not [i for i in issues if i.get("read") == FORMS], issues
    issues = reply_issues(page, ast, None, Reading())
    assert [i for i in issues if i.get("read") == FORMS], issues
    typed = page + "\n### Fries\n\n[➖](agent:dec?id=f) | 1 | [➕](agent:inc?id=f)\n"
    issues = reply_issues(typed, _ast(typed), None, Reading(), None, region)
    [advice] = [i["message"] for i in issues if i.get("read") == FORMS]
    assert "[➖](agent:dec) 1 [➕](agent:inc)" in advice, advice
    print("  ✓  a stepper an include drew is not advised; one typed beside it is")


def test_a_stepper_a_handler_answers_is_not_advised():
    page = STEPPER.replace("&md2ui.commit=1", "")
    issues = reply_issues(page, _ast(page), None, Reading())
    assert [i for i in issues if i.get("read") == FORMS], issues
    handled = {"cart-remove", "cart-add"}
    issues = reply_issues(page, _ast(page), None, Reading(), handled=handled)
    assert not [i for i in issues if i.get("read") == FORMS], issues
    issues = reply_issues(page, _ast(page), None, Reading(), handled={"cart-add"})
    assert [i for i in issues if i.get("read") == FORMS], issues
    print("  ✓  a stepper a handler answers is not advised; one it does not answer is")


def test_values_with_no_commit_press_are_advised_one():
    page = (
        "## Bacon BBQ\n\nQuantity: ➖ [1/9] ➕\n\n- [ ] Gift wrap it\n\n"
        "[Add to cart](agent:add?id=bb) *[Keep shopping](agent:browse)*\n"
    )
    [message] = _advice(page)
    assert "`[Add to cart](agent:add?id=bb&md2ui.commit=1)`" in message, message
    assert "`Quantity`" in message, message
    assert _advice(page.replace("id=bb)", "id=bb&md2ui.commit=1)")) == []
    lone = "## Living room\n\nVolume: [3/10]\n\n[Play](agent:play)\n"
    assert _advice(lone) == [], lone
    boxes = "## Pack\n\n- [ ] Tent\n- [ ] Stove\n\n[Sort by weight](agent:sort)\n"
    assert _advice(boxes) == [], boxes
    assert _advice(page.replace("[Add to cart](agent:add?id=bb) ", "")) != []
    print(
        "  ✓  values with no commit press are advised one; a slider or a checklist is not"
    )


def test_steppers_in_a_cart_name_the_first_and_the_press_after_them():
    row = (
        "- [`{0}`](agent:product?id={0}) ... __[➖](agent:cart-remove?id={0})__ - "
        "**{1}** - __[➕](agent:cart-add?id={0})__\n"
    )
    cart = "## Cart\n\n" + row.format("smash", 2) + row.format("shake", 1)
    [message] = _advice(cart + "\n[Checkout](agent:checkout) *[Back](agent:back)*\n")
    assert "These 2 steppers, `[➖](agent:cart-remove) 2 [➕]" in message, message
    assert "`[Checkout](agent:checkout?md2ui.commit=1)`" in message, message
    print("  ✓  a cart's steppers: the first is named, the press after them marked")


def test_tabs_toggles_and_actions_alone_are_not_advised():
    page = (
        "## Shakes\n\n[Burgers](agent:cat?c=b) | *[Shakes](agent:cat?c=s)*\n\n"
        "### Strawberry\n\n$5.50\n\n[Add](agent:add?id=st)\n\n"
        "## Order BS-1042\n\nCancel this order?\n\n"
        "[Cancel order](agent:confirm-cancel?id=1) *[Keep my order](agent:keep?id=1)*\n"
    )
    assert _advice(page) == [], page
    assert list(form_hints(_ast(page).to_dict())) == []
    print("  ✓  tabs, toggles and actions alone are not advised")


def test_once_and_never_once_read():
    reading = Reading()
    assert len(_advice(STEPPER, reading)) == 1
    assert _advice(STEPPER, reading) == []
    assert _advice(STEPPER, Reading(read={"elements"})) == []
    print("  ✓  once per session, never once the section was read")


TESTS = [
    test_a_stepper_of_buttons_is_advised_a_count,
    test_a_stepper_an_include_drew_is_not_advised,
    test_a_stepper_a_handler_answers_is_not_advised,
    test_values_with_no_commit_press_are_advised_one,
    test_steppers_in_a_cart_name_the_first_and_the_press_after_them,
    test_tabs_toggles_and_actions_alone_are_not_advised,
    test_once_and_never_once_read,
]

if __name__ == "__main__":
    print("Advice Form Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
        except Exception as e:
            print(f"  ✗  {test.__name__}: {e!r}")
            failed += 1
    print("=" * 50)
    raise SystemExit(1 if failed else 0)
