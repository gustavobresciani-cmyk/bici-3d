// Interfaz del diseño v2: selector de color (pinta la bici 3D y cambia los renders de las
// piezas y del detalle al mismo color), animación de las cotas y newsletter.
import { DEFAULT_SWATCH, SWATCHES } from "../data/parts";

const swatchButtons = Array.from(document.querySelectorAll<HTMLButtonElement>("[data-swatch]"));
// imágenes renderizadas en Blender en cada color: /img/parts/<pieza>-<color>.webp
const partImages = Array.from(document.querySelectorAll<HTMLImageElement | SVGImageElement>("[data-part-img]"));

function selectSwatch(id: string) {
  const s = SWATCHES.find((x) => x.id === id);
  if (!s) return;
  swatchButtons.forEach((b) => {
    const on = b.dataset.swatch === id;
    b.classList.toggle("is-active", on);
    b.setAttribute("aria-pressed", String(on));
  });
  document.documentElement.style.setProperty("--bike-color", s.hex);
  partImages.forEach((img) => {
    const src = `/img/parts/${img.dataset.partImg}-${id}.webp`;
    if (img instanceof SVGImageElement) img.setAttribute("href", src);
    else img.src = src;
  });
  window.dispatchEvent(new CustomEvent("bike:color", { detail: s.hex }));
  try { localStorage.setItem("bike-color", id); } catch {}
}

swatchButtons.forEach((b) => b.addEventListener("click", () => selectSwatch(b.dataset.swatch!)));

let saved: string | null = null;
try { saved = localStorage.getItem("bike-color"); } catch {}
selectSwatch(saved && SWATCHES.some((s) => s.id === saved) ? saved : DEFAULT_SWATCH);

// el formulario del newsletter es solo visual por ahora
document.querySelector<HTMLFormElement>("[data-newsletter]")?.addEventListener("submit", (e) => {
  e.preventDefault();
  const f = e.currentTarget as HTMLFormElement;
  f.classList.add("is-sent");
  f.querySelector("input")!.value = "";
  f.querySelector("input")!.placeholder = "Thanks! We'll be in touch soon.";
});

// cotas del detalle: se dibujan cuando la sección entra en pantalla (una sola vez)
const dims = document.querySelector("[data-dims]");
if (dims) {
  const io = new IntersectionObserver((entries) => {
    if (entries.some((e) => e.isIntersecting)) { dims.classList.add("is-in"); io.disconnect(); }
  }, { threshold: 0.45 });
  io.observe(dims);
}
