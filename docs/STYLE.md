# TTSkill Coach style

Table and rubber pairs condensed italic headlines with the colors of the sport. Dark mode uses a near-black canvas and deep table blue. Light mode uses a lavender canvas and softly tinted surfaces. Rubber red marks primary actions, titles, focus, and the active tab. Orange is reserved for the brand ball and small video accents.

| CSS variable | Dark | Light | Use |
| --- | --- | --- | --- |
| `--training-bg` | `#0A0D12` | `#F7F5FC` | Page and header |
| `--training-surface` | `#0E2A47` | `#EEEAF8` | Cards and panels |
| `--training-field` | `#122F4D` | `#FCFAFF` | Inputs and surface hover |
| `--training-ink` | `#F5F7FA` | `#1B1722` | Main text |
| `--training-muted` | `#B8C9D9` | `#51485F` | Supporting text and placeholders |
| `--training-line` | `#395672` | `#CEC5DF` | Dividers and panel edges |
| `--training-control-line` | `#778FA8` | `#897E9D` | Input boundaries |
| `--training-accent` | `#FF8190` | `#A51B2A` | Readable red text and focus rings |
| `--training-secondary` | `#FF8190` | `#6958A3` | Section labels |
| `--training-action` | `#D7262E` | `#B81F26` | Button fills, active tab, and large page title |
| `--training-action-hover` | `#B91E2B` | `#941722` | Hovered primary button |
| `--training-on-action` | `#FFFFFF` | `#FFFFFF` | Text and icons on solid red |
| `--training-error` | `#FFBDC5` | `#8D1526` | Error text and invalid input edges |
| `--training-media` | `#090B0E` | `#090B0E` | Video frames |
| `--color-ball` | `#FF6B2C` | `#FF6B2C` | Ball highlights and video accents |

### Semantic colors

| CSS variable | Dark | Light | Use |
| --- | --- | --- | --- |
| `--training-forehand` | `#D7262E` | `#B81F26` | Forehand label fill |
| `--training-backhand` | `#20242B` | `#2B2A30` | Backhand label fill |
| `--training-backhand-line` | `#B8C6D5` | `#776E85` | Backhand outline |
| `--training-good` | `#1E7F4F` | `#17663F` | Good or improved label fill |

Use white label text over the semantic fills. Pair each fill with a written label and use the outlined charcoal swatch for backhand, especially against the dark canvas.

- **Contrast.** Use a minimum of 4.5:1 for body text, labels, and placeholders, and 3:1 for large text and essential control boundaries. Keep the brighter red for small text on dark blue and use solid rubber red with white text for primary controls. [WCAG text contrast](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) · [WCAG non-text contrast](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html)
- **Actions.** Solid rubber red is the enabled primary button. Disabled buttons use the page surface, muted text, and an inset red outline.
- **Type.** Use Barlow Condensed 800 italic for display and Barlow 400–700 for body and controls. Use 48–88 px for the form title, 28–40 px for section titles, 16 px for body, and 13 px for labels. Both fonts are bundled under SIL OFL 1.1.
- **Spacing.** Work from 8, 16, 24, 32, and 48 px. Keep the form in one column on phones and use two shrinkable columns on wider displays. Give notes and videos separate rows. Below 600 px, the navigation tabs scroll in their own row.
- **Edges.** Use 8 px for controls and 12 px for panels and media. Use a dashed outline to identify the upload target and a solid red rule to identify the coaching notes. Keep the header divider as the line above the page.
- **Motion.** Use 160 ms for color and border feedback and up to 300 ms for progress fills. Respect reduced motion for transitions and status pulses. Switch the header text and background colors together.
