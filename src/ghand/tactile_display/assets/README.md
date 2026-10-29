# Tactile display asset manifest

The display packages these copied GUI images and resolves them relative to this Python module,
so it has no runtime dependency on `E:\GHand-GUI`.

Packaged files and their original GUI locations:

- `resources/products/ghand5/right_hand_icon.png`
- `resources/products/ghand5/left_hand_icon.png`
- `resources/images/bg/thumb.png` and `thumb1.png`
- `resources/images/bg/cc` and `four_fingers1.png`

GHand5 point coordinates come from
`src/layout/finger_tactile_layout.cc::InitializeTactilePoints`: 38 thumb points and 31 points
for each other finger. They are used as widget positions with a `-22 px` offset inside a
finger scene based at `(248, 83)`. The Python widget preserves the corresponding `(8, 18)`
main-image/overlay offset and the point-center offset.
