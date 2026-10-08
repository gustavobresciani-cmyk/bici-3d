// Índice de piezas: marca la sección activa y navega con scroll suave.
const links = Array.from(document.querySelectorAll<HTMLAnchorElement>("[data-nav]"));
const parts = Array.from(document.querySelectorAll<HTMLElement>('[data-scene="part"]'));

const observer = new IntersectionObserver(
  (entries) => {
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      const id = (e.target as HTMLElement).dataset.part;
      for (const a of links) a.classList.toggle("is-active", a.dataset.nav === id);
    }
  },
  { rootMargin: "-50% 0px -50% 0px" },
);
parts.forEach((p) => observer.observe(p));

// fuera de las secciones de piezas, ninguna queda marcada
const others = Array.from(document.querySelectorAll<HTMLElement>('[data-scene]:not([data-scene="part"])'));
const clear = new IntersectionObserver(
  (entries) => {
    if (entries.some((e) => e.isIntersecting)) links.forEach((a) => a.classList.remove("is-active"));
  },
  { rootMargin: "-50% 0px -50% 0px" },
);
others.forEach((s) => clear.observe(s));

document.querySelector("[data-top]")?.addEventListener("click", (e) => {
  e.preventDefault();
  window.scrollTo({ top: 0, behavior: "smooth" });
});
