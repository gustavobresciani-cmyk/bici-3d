## Development

When starting the dev server, use background mode:

```
astro dev --background
```

Manage the background server with `astro dev stop`, `astro dev status`, and `astro dev logs`.

## Documentation

Full documentation: https://docs.astro.build

Consult these guides before working on related tasks:

- [Adding pages, dynamic routes, or middleware](https://docs.astro.build/en/guides/routing/)
- [Working with Astro components](https://docs.astro.build/en/basics/astro-components/)
- [Using React, Vue, Svelte, or other framework components](https://docs.astro.build/en/guides/framework-components/)
- [Adding or managing content](https://docs.astro.build/en/guides/content-collections/)
- [Adding styles or using Tailwind](https://docs.astro.build/en/guides/styling/)
- [Supporting multiple languages](https://docs.astro.build/en/guides/internationalization/)

## Needle Engine

This is a Needle Engine project (@needle-tools/engine 5.1). The 3D model comes from `../blender/bici.py` (exported raw to `models-src/bici.glb`, compressed with `npm run optimize` into `public/models/bici.glb`). Branch `main` = diseño v1 (scroll storytelling, `src/scripts/bike.ts`). Branch `diseno-v2` = landing v2: two `<needle-engine>` (`#hero-3d`, `#explode-3d`) driven by `src/scripts/scenes.ts` (hero parallax; sticky section scroll → armada/lateral/explotada, tabs, ‹ › and drag rotation, callouts with leaders), color picker in `src/scripts/ui.ts` (recolors material `BICI_Pintura` live), content/views in `src/data/parts.ts`, tokens = Figma "Bici v2 · Tokens" in `:root`. Part images in `public/img/parts/*.webp` come from `bici.py -- --parts`. Needle only starts a viewer when it enters the viewport.

Note: Needle stops rendering if the `<needle-engine>` element itself has `opacity: 0`, so fade the parent container instead.

Figma (diseño editable, equipo Finsweet): https://www.figma.com/design/Br1e8eLa1NxdfKCaoXXyhF — variables "Bici · Tokens" = :root de global.css; componentes Tag, Nav Item, Chip, Part Card, Button, Topbar.

Figma · Diseño v2 (página "🎨 Diseño v2", node 14:227): rediseño estilo catálogo de producto — paleta neutra blanco/gris/negro (variables "Bici v2 · Tokens", prefijo v2/), títulos en Archivo SemiBold en mayúsculas con la 2.ª línea en gris claro (text styles "Bici v2/…"), cuerpo en Inter. Landing desktop "Desktop · Landing v2" (16:196): Hero, Exploded View, Parts, Detail, CTA, Footer. Componentes v2 en el frame "Componentes v2" de esa página: Button v2, Section Title, Callout, Spec Tile, Feature Card. Los renders usan las capturas del diseño v1 en escala de grises (filtros de imagen + multiply); en la web habría que pasar el material del cuadro a grafito. Los estilos v1 siguen vigentes: la web actual no usa todavía v2.
