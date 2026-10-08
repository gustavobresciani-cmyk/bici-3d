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

This is a Needle Engine project (@needle-tools/engine 5.1). The 3D model comes from `../blender/bici.py` (exported raw to `models-src/bici.glb`, compressed with `npm run optimize` into `public/models/bici.glb`). Scroll logic lives in `src/scripts/bike.ts`; part texts and camera views in `src/data/parts.ts`.

Note: Needle stops rendering if the `<needle-engine>` element itself has `opacity: 0`, so fade the parent container instead.
