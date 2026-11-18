<!-- A code block asks Stack sections for the width it draws (its widest source
line in the code face), not for its widest word in the body face. The `Install`
band's line draws about 630 px, so at 767 the two bands do not fit side by side
and `Install` stacks above `Notes`; at 1280 they share a row and the code block
draws whole, without scrolling. -->

# Setup

## Install

```bash
curl -fsSL https://example.com/install.sh | sh -s -- --prefix /usr/local --yes
```

## Notes

Run it once per machine.
