// Contenido del diseño v2 (Figma · "🎨 Diseño v2") y configuración de las escenas 3D.
// Las vistas usan las MISMAS coordenadas que el CONFIG de bici.py (Blender, Z arriba):
//   az: 0 = de frente, 90 = lado de la cadena, -90 = lado opuesto · el: grados hacia arriba
//   dist: metros al punto que mira · target: [x, y, z]

/** lift: corre la imagen en vertical (fracción del alto; negativo = la bici baja) para dejar lugar a los textos */
export type View = { az: number; el: number; dist: number; target: [number, number, number]; lift?: number };

// ---------- vistas de cámara ----------
export const VIEWS = {
  // portada: la bici abajo y a la derecha del título (la escena ocupa toda la pantalla)
  hero: { az: 38, el: 14, dist: 3.2, target: [0.1, 0.0, 0.5], lift: -0.13 },
  heroMobile: { az: 38, el: 14, dist: 3.3, target: [0.3, 0.0, 0.5], lift: -0.13 },
  armada: { az: 32, el: 12, dist: 3.35, target: [0.1, 0.0, 0.52], lift: 0.03 },
  armadaMobile: { az: 32, el: 12, dist: 3.1, target: [0.25, 0.0, 0.52], lift: -0.02 },
  lateral: { az: -90, el: 3, dist: 3.2, target: [0.09, 0.0, 0.52], lift: -0.02 },      // perfil puro
  explotada: { az: -84, el: 13, dist: 3.8, target: [0.07, 0.0, 0.62], lift: -0.03 },  // = CAM_END (un poco más lejos)
  explotadaMobile: { az: -84, el: 13, dist: 5.2, target: [0.12, 0.0, 0.62], lift: 0.02 }, // celular: más lejos para que entren las ruedas
} satisfies Record<string, View>;

// ---------- colores de la bici (selector) ----------
// hex = variables "v2/swatch-*" de Figma. Cambian solo la pintura del cuadro y la horquilla.
export const SWATCHES = [
  { id: "sky", name: "Sky", hex: "#B9CBD6" },
  { id: "sand", name: "Sand", hex: "#C9C1AE" },
  { id: "graphite", name: "Graphite", hex: "#4B5048" },
  { id: "forest", name: "British racing green", hex: "#1F4D3A" },
  { id: "accent", name: "Red", hex: "#E5483A" },
];
export const DEFAULT_SWATCH = "graphite";
/** nombre del material de pintura dentro del .glb (make_mat("Pintura") en bici.py) */
export const PAINT_MATERIAL = "BICI_Pintura";

// ---------- sección "Cada pieza: en su lugar" ----------
// Pestañas: el scroll dentro de la sección las recorre en orden; un click salta a cada una.
export const TABS = [
  { id: "armada", title: "Assembled view", body: "The complete bike, just as it hits the street." },
  { id: "lateral", title: "Side view", body: "The profile, with the frame's real proportions." },
  { id: "explotada", title: "Exploded view", body: "Every part floating along its mounting axis." },
] as const;

// Etiquetas con miniatura: posición de la tarjeta en % de la pantalla de la escena fija
// (entre el título de arriba y las pestañas de abajo) y la pieza a la que apunta la línea.
export const CALLOUTS = [
  { node: "BICI_Asiento", label: "Saddle", img: "asiento", x: 20.8, y: 24 },
  { node: "BICI_Manubrio", label: "Handlebar", img: "manubrio", x: 72.2, y: 23 },
  { node: "BICI_Transmision", label: "Drivetrain", img: "transmision", x: 45.8, y: 71 },
  { node: "BICI_Rueda_Delantera", label: "Front wheel", img: "ruedas", x: 82, y: 52 },
];

/** Dónde apunta cada línea, relativo al centro de la pieza (Blender). */
export const LABEL_ANCHORS: Record<string, [number, number, number]> = {
  BICI_Cuadro: [0.02, 0, 0.24],
  BICI_Manubrio: [-0.04, 0, 0.06],
  BICI_Asiento: [0.0, 0, 0.06],
};

// ---------- "Las piezas: una por una" ----------
// row: fila de la grilla · weight: ancho relativo dentro de la fila (al hacer hover la tarjeta crece)
// img: nombre del render; la web usa <img>-<color>.webp según el color elegido
export const PARTS = [
  { id: "cuadro", title: "Frame", body: "The steel skeleton that holds it all together: top tube, down tube and seat tube.", img: "cuadro", row: 1, weight: 2 },
  { id: "manubrio", title: "Handlebar", body: "Steering, brakes and grip, mounted on the steerer tube.", img: "manubrio", row: 1, weight: 1 },
  { id: "ruedas", title: "Wheels", body: "Two 700 mm rims with hand-tensioned spokes and city tires.", img: "ruedas", row: 2, weight: 1 },
  { id: "transmision", title: "Drivetrain", body: "Chainring, cranks, chain and cassette turn every pedal stroke into forward motion.", img: "transmision", row: 2, weight: 2 },
  { id: "horquilla", title: "Fork", body: "Holds the front wheel and soaks up the bumps in the road.", img: "horquilla", row: 3, weight: 1 },
  { id: "asiento", title: "Saddle", body: "A leather saddle on an adjustable seatpost to find just the right height.", img: "asiento", row: 3, weight: 1 },
] as const;

// ---------- "El detalle: en números" ----------
export const SPECS = [
  { title: "Frame", value: "Chromoly steel, 2.1 kg" },
  { title: "Drivetrain", value: "Single speed, 46 × 16 gearing" },
  { title: "Wheels", value: "700c rims, 32 spokes" },
  { title: "Total weight", value: "10.8 kg, ready to ride" },
];

// ---------- índice del CTA (cada fila lleva a su tarjeta) ----------
export const INDEX = [
  { n: "01", name: "Frame", href: "#cuadro" },
  { n: "02", name: "Fork", href: "#horquilla" },
  { n: "03", name: "Front wheel", href: "#ruedas" },
  { n: "04", name: "Rear wheel", href: "#ruedas" },
  { n: "05", name: "Drivetrain", href: "#transmision" },
  { n: "06", name: "Handlebar", href: "#manubrio" },
  { n: "07", name: "Saddle", href: "#asiento" },
];
