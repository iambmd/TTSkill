# TTSkill Coach style

A table-tennis training desk with ball orange, condensed italic headlines, and quiet surfaces. The upload panel borrows angled court markings. In the result, an orange rule marks the coaching notes and the footage gets a clear frame of its own.

| CSS variable | Dark | Light |
| --- | --- | --- |
| `--training-surface` | `#101319` | `#fff8f6` |
| `--training-field` | `#191e26` | `#ffefeb` |
| `--training-ink` | `#f4f4f6` | `#291310` |
| `--training-muted` | `#aeb5c2` | `#684641` |
| `--training-line` | `#343b46` | `#d9b6ae` |
| `--training-accent` | `#ff6b2c` | `#a9300c` |
| `--training-action` | `#ff6b2c` | `#ff6b2c` |
| `--training-action-disabled` | `#db9270` | `#db9270` |
| `--training-on-action` | `#17100c` | `#17100c` |
| `--training-error` | `#fecaca` | `#9f2020` |
| `--training-media` | `#090b0e` | `#090b0e` |

- **Type.** Use Barlow Condensed 800 italic for display and Barlow 400–700 for body and controls. Use 48–88 px for the form title, 28–40 px for section titles, 16 px for body, and 13 px for labels. Both fonts are already bundled under SIL OFL 1.1.
- **Spacing.** Work from 8, 16, 24, 32 and 48 px. Keep the form in one column on phones. Use two shrinkable columns on wider displays. Keep the notes and videos in separate rows in the result column.
- **Edges.** Use 8 px for controls and 12 px for panels and media. Use a dashed outline to identify the upload target and a solid orange rule to identify the coaching notes.
- **Motion.** Use 160 ms for color and border feedback and up to 300 ms for progress fills. Respect reduced motion for transitions and status pulses.
