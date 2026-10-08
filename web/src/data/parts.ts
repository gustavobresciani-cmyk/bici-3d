// Contenido y cámara de cada pieza.
// Las vistas usan las MISMAS coordenadas que el CONFIG de bici.py (Blender, Z arriba):
//   az: 0 = de frente, 90 = lado de la cadena, -90 = lado opuesto · el: grados hacia arriba
//   dist: metros al punto que mira · target: [x, y, z] o el nombre de una pieza

export type View = {
  az: number;
  el: number;
  dist: number;
  target: [number, number, number] | string;
  /** desplazamiento extra del punto que mira (Blender) cuando target es una pieza */
  offset?: [number, number, number];
};

// Igual que CAM_START / CAM_END en bici.py
export const START_VIEW: View = { az: 38, el: 14, dist: 2.45, target: [0.1, 0.0, 0.52] };
// (la web la aleja un poco más que Blender para que entren las etiquetas)
export const END_VIEW: View = { az: -84, el: 13, dist: 3.7, target: [0.07, 0.0, 0.66] };
/** Fracción del desarme en la que la cámara termina de girar (CAM_SECONDS / EXPLODE_SECONDS) */
export const CAM_FRACTION = 1.5 / 4.0;

export type Part = {
  id: string;
  number: string;
  name: string;
  kicker: string;
  body: string;
  details: string[];
  /** cuánto queda fija la tarjeta (scroll extra, ej. "150vh"). Si no se indica, usa --part-hold del CSS */
  hold?: string;
  /** nodos del .glb que forman esta pieza (nombres de objetos en Blender) */
  nodes: string[];
  view: View;
};

export const PARTS: Part[] = [
  {
    id: "cuadro",
    number: "01",
    name: "Cuadro",
    kicker: "La estructura",
    body:
      "Es el esqueleto de la bici: todas las demás piezas se montan sobre él. Los tubos forman el clásico doble triángulo, que reparte el peso del ciclista y las fuerzas del pedaleo. En los cuadros de acero clásicos, las uniones llevan refuerzos que también le dan su estética.",
    details: ["Tubo superior", "Tubo inferior", "Tubo de asiento", "Vainas y tirantes"],
    nodes: ["BICI_Cuadro"],
    view: { az: -62, el: 14, dist: 2.8, target: "BICI_Cuadro", offset: [0, 0, 0.05] },
  },
  {
    id: "horquilla",
    number: "02",
    name: "Horquilla",
    kicker: "Dirección y estabilidad",
    body:
      "Sostiene la rueda delantera y gira junto con el manubrio. La curva de sus brazos adelanta el eje de la rueda, lo que hace que la bici vaya derecha sola y absorba parte de las vibraciones del camino. En la corona va montado el freno delantero.",
    details: ["Corona", "Brazos curvos", "Punteras", "Freno de herradura"],
    nodes: ["BICI_Horquilla"],
    view: { az: -32, el: 8, dist: 1.6, target: "BICI_Horquilla" },
  },
  {
    id: "ruedas",
    number: "03",
    name: "Ruedas",
    kicker: "El contacto con el suelo",
    body:
      "Cada rueda combina una llanta liviana, rayos tensados que se cruzan para transmitir la fuerza del pedaleo y una maza central que gira sobre rulemanes. La cubierta tiene una banda de rodamiento con dibujo para agarrarse al piso.",
    details: ["Cubierta", "Llanta", "32 rayos cruzados", "Maza y cierre rápido"],
    nodes: ["BICI_Rueda_Delantera", "BICI_Rueda_Trasera"],
    view: { az: -86, el: 6, dist: 4.1, target: [0.2, 0.0, 0.45] },
  },
  {
    id: "transmision",
    number: "04",
    name: "Transmisión",
    kicker: "Del pedal al avance",
    body:
      "Convierte el pedaleo en movimiento. Las bielas hacen girar el plato, la cadena lleva esa fuerza hasta el cassette de la rueda trasera, y el cambio mueve la cadena entre coronas para elegir un pedaleo más liviano o más rápido.",
    details: ["Plato y bielas", "Pedales", "Cadena", "Cassette de 8 coronas"],
    nodes: ["BICI_Transmision"],
    view: { az: 58, el: 18, dist: 2.1, target: "BICI_Transmision" },
  },
  {
    id: "manubrio",
    number: "05",
    name: "Manubrio",
    kicker: "Control en tus manos",
    body:
      "Desde acá se dirige y se frena. El tubo de dirección baja por dentro del cuadro hasta la horquilla y la potencia lo une al manubrio. Los puños dan agarre y las manetas tiran de los cables que accionan los frenos.",
    details: ["Tubo de dirección", "Potencia", "Puños", "Manetas de freno"],
    nodes: ["BICI_Manubrio"],
    view: { az: -18, el: 22, dist: 1.25, target: "BICI_Manubrio" },
  },
  {
    id: "asiento",
    number: "06",
    name: "Asiento",
    kicker: "Comodidad",
    body:
      "El asiento de cuero se apoya sobre dos rieles de acero que funcionan como un pequeño resorte. La tija entra en el tubo de asiento y se ajusta en altura para que la pierna quede casi estirada al pedalear.",
    details: ["Asiento de cuero", "Rieles", "Tija regulable", "Remaches"],
    nodes: ["BICI_Asiento"],
    view: { az: -128, el: 18, dist: 1.15, target: "BICI_Asiento" },
  },
];

/** Nombre corto para la etiqueta de cada nodo */
export const NODE_LABELS: Record<string, string> = {
  BICI_Cuadro: "Cuadro",
  BICI_Horquilla: "Horquilla",
  BICI_Rueda_Delantera: "Rueda delantera",
  BICI_Rueda_Trasera: "Rueda trasera",
  BICI_Transmision: "Transmisión",
  BICI_Manubrio: "Manubrio",
  BICI_Asiento: "Asiento",
};

/** Dónde apunta la etiqueta, relativo al centro de la pieza (Blender). El centro del
 * cuadro cae en el hueco del triángulo, así que se sube al tubo superior. */
export const LABEL_ANCHORS: Record<string, [number, number, number]> = {
  BICI_Cuadro: [0.02, 0, 0.24],
  // el manubrio incluye el tubo de dirección: se apunta a la potencia, no al centro
  BICI_Manubrio: [-0.04, 0, 0.06],
};
