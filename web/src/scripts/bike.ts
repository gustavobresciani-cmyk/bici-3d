// Conecta el scroll de la página con la escena de Needle Engine:
// animación de desarme (exportada desde Blender), cámara, atenuado de piezas y etiquetas.
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
import { CAM_FRACTION, END_VIEW, LABEL_ANCHORS, NODE_LABELS, PARTS, START_VIEW, type View } from "../data/parts";

// ---------- ajustes ----------
const H_FOV = 2 * Math.atan(18 / 35); // lente de 35 mm como la cámara de Blender
const DAMPING = 5; // suavizado del movimiento (más alto = sigue al scroll más rápido)
const DIM_OPACITY = 0.12; // opacidad de las piezas que no están en foco
// corre la bici a la derecha en escritorio para dejar lugar al texto (fracción del ancho)
const SHIFT = { hero: 0.25, explode: 0.13, part: 0.17 };
// en celular la tarjeta va abajo: se sube la bici (fracción del alto)
const MOBILE_LIFT = 0.2;

// Blender (Z arriba) → three.js / glTF (Y arriba)
const fromBlender = (x: number, y: number, z: number) => new Vector3(x, z, -y);

type Resolved = { az: number; el: number; dist: number; target: Vector3 };
type SceneState = { explode: number; view: Resolved; focus: string | null; shift: number; lift?: number };

const nodes = new Map<string, Object3D>();
const partMaterials = new Map<string, Material[]>();
let action: AnimationAction | null = null;
let mixer: AnimationMixer | null = null;
let clipDuration = 1;

const current = {
  explode: 0,
  az: START_VIEW.az,
  el: START_VIEW.el,
  dist: START_VIEW.dist,
  target: fromBlender(...(START_VIEW.target as [number, number, number])),
  shift: 0,
  lift: 0,
};
const opacity = new Map<string, number>();

const easeOutCubic = (t: number) => 1 - Math.pow(1 - t, 3);
const clamp01 = (t: number) => Math.min(1, Math.max(0, t));

function nodeWorldPosition(name: string, offset?: [number, number, number]) {
  const obj = nodes.get(name);
  const p = new Vector3();
  if (obj) obj.getWorldPosition(p);
  if (offset) p.add(fromBlender(...offset));
  return p;
}

function resolveView(v: View): Resolved {
  const target = typeof v.target === "string" ? nodeWorldPosition(v.target, v.offset) : fromBlender(...v.target);
  return { az: v.az, el: v.el, dist: v.dist, target };
}

function mixViews(a: Resolved, b: Resolved, t: number): Resolved {
  return {
    az: MathUtils.lerp(a.az, b.az, t),
    el: MathUtils.lerp(a.el, b.el, t),
    dist: MathUtils.lerp(a.dist, b.dist, t),
    target: a.target.clone().lerp(b.target, t),
  };
}

// ---------- scroll → estado de la escena ----------
const sections = Array.from(document.querySelectorAll<HTMLElement>("[data-scene]"));
const isDesktop = () => window.innerWidth >= 900;

function sceneFromScroll(): SceneState {
  const mid = window.innerHeight * 0.5;
  let active = sections[0];
  let progress = 0;
  for (const s of sections) {
    const r = s.getBoundingClientRect();
    if (r.top <= mid) {
      active = s;
      progress = clamp01((mid - r.top) / r.height);
    }
  }
  const start = resolveView(START_VIEW);
  const end = resolveView(END_VIEW);
  const kind = active.dataset.scene;
  const d = isDesktop() ? 1 : 0;
  switch (kind) {
    case "explode":
      return {
        explode: progress,
        view: mixViews(start, end, easeOutCubic(clamp01(progress / CAM_FRACTION))),
        focus: null,
        shift: d * MathUtils.lerp(SHIFT.hero, SHIFT.explode, clamp01(progress / CAM_FRACTION)),
      };
    case "part": {
      const part = PARTS.find((p) => p.id === active.dataset.part)!;
      return { explode: 1, view: resolveView(part.view), focus: part.id, shift: d * SHIFT.part, lift: (1 - d) * MOBILE_LIFT };
    }
    case "assemble":
      return {
        explode: 1 - progress,
        view: mixViews(end, start, easeOutCubic(progress)),
        focus: null,
        shift: d * MathUtils.lerp(SHIFT.explode, SHIFT.hero, progress),
      };
    default: // hero / outro
      return { explode: 0, view: start, focus: null, shift: d * SHIFT.hero };
  }
}

// ---------- preparación de la escena ----------
function setup(ctx: Context) {
  // solo los nodos raíz de cada pieza: las mallas hijas del glTF repiten el nombre
  ctx.scene.traverse((obj) => {
    if (obj.name in NODE_LABELS && !nodes.has(obj.name)) nodes.set(obj.name, obj);
  });

  // la animación de Blender viaja dentro del .glb (un solo clip con todas las piezas)
  let root: Object3D | null = null;
  ctx.scene.traverse((obj) => {
    if (!root && obj.animations?.length) root = obj;
  });
  if (root) {
    const clip = (root as Object3D).animations[0];
    mixer = new AnimationMixer(root);
    action = mixer.clipAction(clip);
    action.setLoop(LoopOnce, 1);
    action.clampWhenFinished = true;
    action.play();
    clipDuration = clip.duration;
  }

  // materiales propios por pieza → se puede atenuar una sin afectar a las demás
  for (const [name, obj] of nodes) {
    const mats: Material[] = [];
    obj.traverse((child) => {
      const mesh = child as Mesh;
      if (!mesh.isMesh) return;
      const clone = (m: Material) => {
        const c = m.clone();
        mats.push(c);
        return c;
      };
      mesh.material = Array.isArray(mesh.material) ? mesh.material.map(clone) : clone(mesh.material);
    });
    partMaterials.set(name, mats);
    opacity.set(name, 1);
  }

  document.documentElement.classList.add("scene-ready");
}

// ---------- etiquetas ----------
const tags = Array.from(document.querySelectorAll<HTMLElement>("[data-tag]"));
const tmp = new Vector3();

function updateTags(ctx: Context, state: SceneState) {
  const cam = ctx.mainCamera as PerspectiveCamera;
  const focusNodes = state.focus ? PARTS.find((p) => p.id === state.focus)!.nodes : [];
  const overview = !state.focus && current.explode > 0.8;
  const rect = ctx.domElement.getBoundingClientRect();
  for (const tag of tags) {
    const name = tag.dataset.tag!;
    const visible = focusNodes.includes(name) || overview;
    tag.classList.toggle("is-visible", visible);
    tag.classList.toggle("is-focus", focusNodes.includes(name));
    if (!visible && !tag.classList.contains("was-visible")) continue;
    tag.classList.toggle("was-visible", visible);
    tmp.copy(nodeWorldPosition(name, LABEL_ANCHORS[name])).project(cam);
    const x = (tmp.x * 0.5 + 0.5) * rect.width;
    const y = (-tmp.y * 0.5 + 0.5) * rect.height;
    tag.style.transform = `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, 0)`;
  }
}

// ---------- cada frame ----------
function frame(ctx: Context) {
  if (!mixer || !action) return;
  const dt = Math.min(ctx.time.deltaTime, 0.1);
  const k = 1 - Math.exp(-dt * DAMPING);
  const state = sceneFromScroll();

  // desarme: el easing ya viene "horneado" en el clip de Blender
  current.explode = MathUtils.lerp(current.explode, state.explode, k);
  action.time = current.explode * clipDuration;
  mixer.update(0);

  // cámara en órbita (igual que en Blender), suavizada
  current.az = MathUtils.lerp(current.az, state.view.az, k);
  current.el = MathUtils.lerp(current.el, state.view.el, k);
  current.dist = MathUtils.lerp(current.dist, state.view.dist, k);
  current.target.lerp(state.view.target, k);
  current.shift = MathUtils.lerp(current.shift, state.shift, k);
  current.lift = MathUtils.lerp(current.lift, state.lift ?? 0, k);

  const cam = ctx.mainCamera as PerspectiveCamera;
  const az = MathUtils.degToRad(current.az);
  const el = MathUtils.degToRad(current.el);
  const dir = fromBlender(Math.cos(el) * Math.cos(az), Math.cos(el) * Math.sin(az), Math.sin(el));
  const w = ctx.domElement.clientWidth;
  const h = ctx.domElement.clientHeight;
  const aspect = w / h;
  // en pantallas angostas se aleja la cámara para que entre la bici completa
  const narrow = aspect < 1 ? Math.pow(1 / aspect, 0.55) : 1;
  cam.position.copy(current.target).addScaledVector(dir, current.dist * narrow);
  cam.lookAt(current.target);
  cam.fov = MathUtils.radToDeg(2 * Math.atan(Math.tan(H_FOV / 2) / Math.max(aspect, 1)));
  cam.aspect = aspect;
  cam.near = 0.01;
  cam.far = 50;
  cam.setViewOffset(w, h, -current.shift * w, current.lift * h, w, h);
  cam.updateProjectionMatrix();

  // atenuar las piezas que no están en foco
  const focusNodes = state.focus ? PARTS.find((p) => p.id === state.focus)!.nodes : null;
  for (const [name, mats] of partMaterials) {
    const goal = !focusNodes || focusNodes.includes(name) ? 1 : DIM_OPACITY;
    const o = MathUtils.lerp(opacity.get(name)!, goal, k);
    opacity.set(name, o);
    const dim = o < 0.995;
    for (const m of mats) {
      m.transparent = dim;
      m.opacity = o;
      m.depthWrite = !dim;
    }
  }

  updateTags(ctx, state);
}

onStart((ctx) => setup(ctx));
onBeforeRender((ctx) => frame(ctx));
