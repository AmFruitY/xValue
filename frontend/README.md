# xValue Web

Demo 1 is a single-page Next.js frontend for the xValue football valuation concept.
It reads the synthetic mock predictions through a small server-side data boundary:

`CSV -> parser -> adapter -> Player -> UI`

The selected featured player is chosen with a transparent presentation heuristic.
That score and the playing-time bar normalization are UI-only values; neither is an
xValue model output or a scientific metric.

## Local development

```bash
npm install
npm run dev
```

Then open `http://localhost:3000`.

## Validation

```bash
npm run lint
npm run build
```
