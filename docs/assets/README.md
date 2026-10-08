# Promo assets

Tracked media for the GitHub README (exempt from root `*.png` / `*.mp4` ignores).

| File | Role |
|------|------|
| `showcase-still.jpg` | Vertical still from a local episode open frame |
| `demo.mp4` | Optional short demo reel (drop here before publish) |

To refresh the still from a series open frame:

```bash
# example
cp "templates/<series>/assets/episode_open/EP001.png" docs/assets/tmp.png
# then re-encode to JPEG (~500KB) for README weight
```

`demo.mp4` tip: keep under ~15–25 MB for GitHub browsing; longer cuts belong in [Releases](../../releases).
