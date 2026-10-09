// Escena 3D única del diseño v2 (Needle Engine): la portada y "Cada pieza: en su lugar"
// comparten el mismo <needle-engine id="bike-3d">, fijo mientras se recorre la sección.
//
// Recorrido del scroll (p = 0 → 1 dentro de la sección):
//   portada (título, bici 3/4, palabra fantasma) → se funde a "Cada pieza" → vista armada
//   → vista lateral → vista explotada (se desarma) → queda quieta.
// Además: pestañas, flechas ‹ › y arrastre para girar, etiquetas con línea y selector de color.
import { onStart, onBeforeRender, type Context } from "@needle-tools/engine";
import {
  AnimationMixer,
  LoopOnce,
  MathUtils,
  PerspectiveCamera,
  Vector3,
  type AnimationAction,
  type Material,
  type Mesh,
  type Object3D,
} from "three";
import { DEFAULT_SWATCH, LABEL_ANCHORS, PAINT_MATERIAL, SWATCHES, VIEWS, type View } from "../data/parts";

// ---------- ajustes ----------
const H_FOV = 2 * Math.atan(18 / 35); // lente de 35 mm como en Blender
const DAMPING = 5; // suavizado (más alto = sigue más rápido al scroll / mouse)
const HERO_PARALLAX = { az: 7, el: 3 }; // grados que se mueve la bici con el mouse en la portada
const ROTATE_STEP = 35; // grados por click en las flechas ‹ ›
const DRAG_SPEED = 0.35; // grados por píxel al arrastrar
// Tramos del scroll dentro de la sección (0 = arriba de todo, 1 = termina la sección fija)
const STEPS = {
  introStart: 0.02, introEnd: 0.13, // la portada se funde en "Cada pieza"
  armadaEnd: 0.24, // vista armada
  lateralEnd: 0.42, // gira a la vista lateral
  explodeEnd: 0.84, // se desarma mientras va a la vista explotada
};
const TAB_TARGETS = { armada: 0.19, lateral: 0.43, explotada: 0.93 }; // dónde salta cada pestaña
const CALLOUT_FROM = 0.7; // las etiquetas aparecen con la bici explotada a partir de este valor

const fromBlender = (x: number, y: number, z: number) => new Vector3(x, z, -y);
const clamp01 = (t: number) => Math.min(1, Math.max(0, t));
const ease = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const span = (p: number, a: number, b: number) => ease(clamp01((p - a) / (b - a)));

type Cam = { az: number; el: number; dist: number; target: Vector3; lift: number };
type Rig = {
  ctx: Context;
  nodes: Map<string, Object3D>;
  mixer: AnimationMixer | null;
  action: AnimationAction | null;
  duration: number;
  paints: Material[];
  explode: number;
  cam: Cam;
};
let rig: Rig | null = null;
let paintHex = SWATCHES.find((s) => s.id === DEFAULT_SWATCH)!.hex;

// ---------- DOM ----------
const section = document.querySelector<HTMLElement>("[data-explode]");
const stage = section?.querySelector<HTMLElement>("[data-stage]");
const tabs = Array.from(document.querySelectorAll<HTMLButtonElement>("[data-tab]"));
const callouts = Array.from(document.querySelectorAll<HTMLElement>("[data-callout]"));
const leaders = Array.from(document.querySelectorAll<SVGPathElement>("[data-leader]"));
const points = Array.from(document.querySelectorAll<SVGCircleElement>("[data-point]"));

// ---------- preparación ----------
function setup(ctx: Context) {
  const nodes = new Map<string, Object3D>();
  ctx.scene.traverse((o) => {
    if (o.name.startsWith("BICI_") && !nodes.has(o.name)) nodes.set(o.name, o); // la 1.ª es la raíz de la pieza
  });
  let root: Object3D | null = null;
  ctx.scene.traverse((o) => {
    if (!root && o.animations?.length) root = o;
  });
  let mixer: AnimationMixer | null = null, action: AnimationAction | null = null, duration = 1;
  if (root) {
    const clip = (root as Object3D).animations[0];
    mixer = new AnimationMixer(root);
    action = mixer.clipAction(clip);
    action.setLoop(LoopOnce, 1);
    action.clampWhenFinished = true;
    action.play();
    duration = clip.duration;
  }
  const paints = new Set<Material>();
  ctx.scene.traverse((o) => {
    const m = (o as Mesh).material;
    if (m) for (const mat of Array.isArray(m) ? m : [m]) if (mat.name === PAINT_MATERIAL) paints.add(mat);
  });
  // fondo transparente: la palabra fantasma y el fondo de la página se ven detrás de la bici
  ctx.scene.background = null;
  ctx.renderer.setClearColor(0x000000, 0);
  const v = VIEWS.hero;
  rig = { ctx, nodes, mixer, action, duration, paints: [...paints], explode: 0,
    cam: { az: v.az, el: v.el, dist: v.dist, target: fromBlender(...v.target), lift: v.lift ?? 0 } };
  applyPaint();
  stage?.classList.add("is-ready");
  document.documentElement.classList.add("scene-ready"); // señal para herramientas de captura
}

function applyPaint() {
  rig?.paints.forEach((m) => (m as any).color?.set(paintHex));
}
window.addEventListener("bike:color", (e) => {
  paintHex = (e as CustomEvent<string>).detail;
  applyPaint();
});

// ---------- scroll y controles ----------
function progress() {
  if (!section) return 0;
  const r = section.getBoundingClientRect();
  return clamp01(-r.top / Math.max(1, r.height - innerHeight));
}
function scrollToProgress(p: number) {
  if (!section) return;
  const top = window.scrollY + section.getBoundingClientRect().top;
  window.scrollTo({ top: top + p * (section.offsetHeight - innerHeight), behavior: "smooth" });
}
tabs.forEach((t) => t.addEventListener("click", () => scrollToProgress(TAB_TARGETS[t.dataset.tab as keyof typeof TAB_TARGETS])));
document.querySelectorAll<HTMLElement>("[data-goto]").forEach((a) =>
  a.addEventListener("click", (e) => {
    e.preventDefault();
    scrollToProgress(TAB_TARGETS[a.dataset.goto as keyof typeof TAB_TARGETS] ?? 0);
  }),
);

let userAz = 0, userAzTarget = 0;
document.querySelectorAll<HTMLButtonElement>("[data-rotate]").forEach((b) =>
  b.addEventListener("click", () => (userAzTarget += ROTATE_STEP * Number(b.dataset.rotate))),
);
if (stage) {
  let dragX: number | null = null;
  stage.addEventListener("pointerdown", (e) => {
    if ((e.target as Element).closest("button, a")) return; // botones y links no inician arrastre (la captura les roba el click)
    dragX = e.clientX; stage.setPointerCapture(e.pointerId); stage.classList.add("is-dragging");
  });
  stage.addEventListener("pointermove", (e) => { if (dragX === null) return; userAzTarget -= (e.clientX - dragX) * DRAG_SPEED; dragX = e.clientX; });
  const end = () => { dragX = null; stage.classList.remove("is-dragging"); };
  stage.addEventListener("pointerup", end);
  stage.addEventListener("pointercancel", end);
}
const pointer = { x: 0, y: 0 };
window.addEventListener("pointermove", (e) => {
  pointer.x = (e.clientX / innerWidth) * 2 - 1;
  pointer.y = (e.clientY / innerHeight) * 2 - 1;
});

// ---------- cámara ----------
const toCam = (v: View, azOffset = 0): Cam => ({ az: v.az + azOffset, el: v.el, dist: v.dist, target: fromBlender(...v.target), lift: v.lift ?? 0 });
const mixCam = (a: Cam, b: Cam, t: number): Cam => ({
  az: MathUtils.lerp(a.az, b.az, t), el: MathUtils.lerp(a.el, b.el, t), dist: MathUtils.lerp(a.dist, b.dist, t),
  target: a.target.clone().lerp(b.target, t), lift: MathUtils.lerp(a.lift, b.lift, t),
});

function placeCamera(r: Rig, goal: Cam, k: number) {
  const c = r.cam;
  c.az = MathUtils.lerp(c.az, goal.az, k);
  c.el = MathUtils.lerp(c.el, goal.el, k);
  c.dist = MathUtils.lerp(c.dist, goal.dist, k);
  c.target.lerp(goal.target, k);
  c.lift = MathUtils.lerp(c.lift, goal.lift, k);
  const cam = r.ctx.mainCamera as PerspectiveCamera;
  const az = MathUtils.degToRad(c.az), el = MathUtils.degToRad(c.el);
  const w = r.ctx.domElement.clientWidth, h = r.ctx.domElement.clientHeight;
  const aspect = w / Math.max(1, h);
  // en vertical el FOV horizontal se achica con el ancho: alejar un poco para que entre la bici
  const narrow = aspect < 1 ? Math.pow(1 / aspect, 0.3) : 1;
  cam.position.copy(c.target).addScaledVector(fromBlender(Math.cos(el) * Math.cos(az), Math.cos(el) * Math.sin(az), Math.sin(el)), c.dist * narrow);
  cam.lookAt(c.target);
  cam.fov = MathUtils.radToDeg(2 * Math.atan(Math.tan(H_FOV / 2) / Math.max(aspect, 1)));
  cam.aspect = aspect;
  cam.near = 0.01;
  cam.far = 50;
  // lift: corre la imagen en vertical (negativo = la bici baja) para dejar lugar a los textos
  cam.setViewOffset(w, h, 0, c.lift * h, w, h);
  cam.updateProjectionMatrix();
}

// ---------- cada frame ----------
let activeTab = "";
const tmp = new Vector3();

function frame(r: Rig, k: number) {
  const p = progress();
  userAz = MathUtils.lerp(userAz, userAzTarget, k);
  const portrait = r.ctx.domElement.clientWidth < r.ctx.domElement.clientHeight;

  // portada → "Cada pieza": un valor 0..1 que el CSS usa para fundir textos (--intro)
  const intro = span(p, STEPS.introStart, STEPS.introEnd);
  section?.style.setProperty("--intro", intro.toFixed(3));
  section?.classList.toggle("is-explode", intro > 0.5);

  const hero = toCam(portrait ? VIEWS.heroMobile : VIEWS.hero, userAz + pointer.x * HERO_PARALLAX.az * (1 - intro));
  hero.el += -pointer.y * HERO_PARALLAX.el * (1 - intro);
  const armada = toCam(portrait ? VIEWS.armadaMobile : VIEWS.armada, userAz);
  const lateral = toCam(VIEWS.lateral, userAz);
  const explotada = toCam(portrait ? VIEWS.explotadaMobile : VIEWS.explotada, userAz);

  let goal = mixCam(hero, armada, span(p, STEPS.introStart, STEPS.armadaEnd));
  let explode = 0;
  if (p > STEPS.armadaEnd) goal = mixCam(armada, lateral, span(p, STEPS.armadaEnd, STEPS.lateralEnd));
  if (p > STEPS.lateralEnd) {
    const t = clamp01((p - STEPS.lateralEnd) / (STEPS.explodeEnd - STEPS.lateralEnd));
    goal = mixCam(lateral, explotada, ease(t));
    explode = t; // el easing del desarme ya viene en el clip de Blender
  }
  r.explode = MathUtils.lerp(r.explode, explode, k);
  if (r.action && r.mixer) {
    r.action.time = r.explode * r.duration;
    r.mixer.update(0);
  }
  placeCamera(r, goal, k);

  const tab = p < 0.33 ? "armada" : p < 0.62 ? "lateral" : "explotada";
  if (tab !== activeTab) {
    activeTab = tab;
    tabs.forEach((t) => t.classList.toggle("is-active", t.dataset.tab === tab));
  }
  updateCallouts(r);
}

function updateCallouts(r: Rig) {
  if (!stage) return;
  const show = r.explode > CALLOUT_FROM;
  stage.classList.toggle("show-callouts", show);
  if (!show) return;
  const cam = r.ctx.mainCamera as PerspectiveCamera;
  const sr = stage.getBoundingClientRect();
  const er = r.ctx.domElement.getBoundingClientRect();
  callouts.forEach((el, i) => {
    const node = r.nodes.get(el.dataset.callout!);
    if (!node) return;
    node.getWorldPosition(tmp);
    const off = LABEL_ANCHORS[el.dataset.callout!];
    if (off) tmp.add(fromBlender(...off));
    tmp.project(cam);
    const px = er.left - sr.left + (tmp.x * 0.5 + 0.5) * er.width;
    const py = er.top - sr.top + (-tmp.y * 0.5 + 0.5) * er.height;
    const label = el.querySelector<HTMLElement>(".callout__label")!.getBoundingClientRect();
    const right = px > label.right - sr.left;
    const sx = right ? label.right - sr.left : label.left - sr.left;
    const sy = label.top - sr.top + label.height / 2;
    leaders[i]?.setAttribute("d", `M ${sx.toFixed(1)} ${sy.toFixed(1)} H ${px.toFixed(1)} V ${py.toFixed(1)}`);
    points[i]?.setAttribute("cx", px.toFixed(1));
    points[i]?.setAttribute("cy", py.toFixed(1));
  });
}

onStart((ctx) => setup(ctx));
onBeforeRender((ctx) => {
  if (!rig || rig.ctx !== ctx) return;
  frame(rig, 1 - Math.exp(-Math.min(ctx.time.deltaTime, 0.1) * DAMPING));
});
