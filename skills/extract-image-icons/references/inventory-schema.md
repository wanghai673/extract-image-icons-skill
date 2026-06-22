# Icon inventory schema

Write one JSON file before generation:

```json
{
  "schema_version": 1,
  "source_image": "/absolute/path/source.png",
  "max_icons_per_sheet": 9,
  "max_parallel_calls": 4,
  "key_color": "#FF00FF",
  "icons": [
    {
      "id": "memory_agent",
      "description": "Green-accent robot holding a pencil",
      "occurrences": 1,
      "grouping_note": "Keep the robot, pencil, antenna, and shadow together",
      "text_policy": "remove readable text",
      "fidelity_note": "Preserve the exact visible pose, green palette, pencil position, strokes, shading, and proportions; clarify only source-supported blurry edges"
    }
  ]
}
```

## Field rules

- `source_image`: required absolute path to the source image.
- `max_icons_per_sheet`: integer from 1 to 9. Nine is the hard maximum.
- `max_parallel_calls`: integer from 1 to 8. This limits concurrent asset-sheet edit jobs.
- `key_color`: six-digit RGB hex color selected to be far from every icon's colors.
- `icons`: non-empty list of unique assets.
- `icons[].id`: stable lowercase snake-case identifier, unique across the inventory.
- `icons[].description`: visual identity, location when useful, pose, palette, and distinguishing details.
- `icons[].occurrences`: number of visually identical instances in the source.
- `icons[].grouping_note`: which visible parts belong to the one movable asset.
- `icons[].text_policy`: normally `remove readable text`; preserve only inseparable brand marks.
- `icons[].fidelity_note`: record the source details that must remain unchanged. It may tighten fidelity requirements but may not permit redesign, enhancement, invented detail, pose changes, or style changes.

Do not list ordinary text, cards, panels, arrows, connectors, borders, or simple layout shapes as icons.

Strict fidelity is global and cannot be weakened by an inventory item. Low-resolution areas may receive conservative denoising, antialiasing, resampling, and source-supported edge clarification. Never infer a specific missing feature, redraw a shape, or change a blurry region's semantic content when the source does not provide enough evidence.
