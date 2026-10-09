"""
Bicicleta procedural + animación de vista explotada, lista para Needle Engine.

Uso:
  - Desde Blender: pegar en Scripting y Run Script (re-ejecutable, se limpia sola).
  - Desde terminal (exporta GLB; --render = imágenes, --video = MP4, --save = guarda bici.blend):
      /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
        --python bici.py -- --render --video

Cada parte es UN objeto con su origen en el centro de la pieza.
El sitio web usa esos nombres (BICI_Cuadro, BICI_Rueda_Delantera, ...) para
posicionar las etiquetas, así que si renombrás algo, actualizalo también en la web.
"""
import bpy, bmesh, math, os, sys
from mathutils import Vector, Matrix

# ============ CONFIG ============
PREFIX = "BICI_"                     # prefijo de todo lo que crea el script (cleanup)
HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() and os.path.exists(__file__) \
    else "/Users/gustavo/Blender/bici-3d/blender"
GLB_PATH = os.path.join(HERE, "..", "web", "models-src", "bici.glb")      # export crudo
WEB_DIR = os.path.join(HERE, "..", "web")   # al exportar se comprime a web/public/models/bici.glb
BLEND_PATH = os.path.join(HERE, "bici.blend")
PREVIEW_DIR = os.path.join(HERE, "preview")

FPS = 30
EXPLODE_SECONDS = 4.0                # duración total de la explosión (la web la scrollea)
STAGGER = 0.01                       # desfase entre partes (0 = todas a la vez, sube = más escalonado)
WHEEL_SPIN_TURNS = 0.5               # vueltas que giran las ruedas mientras se separan
# Curva de velocidad de cada desarme (igual que en Graph Editor: T = tipo, Ctrl+E = easing)
EASING_TYPE = 'EXPO'                 # BEZIER, SINE, QUAD, CUBIC, QUART, QUINT, EXPO, CIRC, BACK, ELASTIC, BOUNCE
                                     # (de suave a brusco: SINE < QUAD < CUBIC < QUART < QUINT < EXPO)
EASING_MODE = 'EASE_OUT'             # EASE_OUT = arranca rápido y frena suave; EASE_IN = al revés; EASE_IN_OUT = ambos

# Cámara de preview: órbita alrededor de la bici durante el desarme.
#   azimuth: 0 = de frente (+X), 90 = lado de la cadena (+Y), -90 = lado opuesto (-Y)
#   elevation: grados hacia arriba · distance: metros al target · target: punto que mira
CAM_START = dict(azimuth=38, elevation=14, distance=2.45, target=(0.10, 0.0, 0.52))   # 3/4 frontal, armada
CAM_END   = dict(azimuth=-84, elevation=13, distance=3.3, target=(0.07, 0.0, 0.66))   # lateral casi puro, lado opuesto a la cadena
CAM_LENS = 35                        # mm (menos = más gran angular)
CAM_EASE = 'EASE_OUT'                # LINEAR, EASE_OUT, EASE_IN_OUT (movimiento de cámara)
CAM_SECONDS = 1.5                    # duración del giro de cámara; None = igual que el desarme.
                                     # Menos segundos = giro más rápido (después queda quieta hasta el final)
CAM_DELAY_SECONDS = 0.1              # espera antes de que la cámara empiece a moverse
VIDEO_HOLD_START = 0.6               # segundos quieta al inicio del video de preview
VIDEO_HOLD_END = 1.2                 # segundos quieta al final

# ---------- LOOK: colores en HEX (como en Figma) ----------
# Los materiales de la bici viajan en el .glb → se ven igual en la web.
MATERIALS = {          #  color      metálico (0-1)  rugosidad (0 = espejo, 1 = mate)
    "paint":  ("#1F4D3A", 0.35, 0.25),   # pintura del cuadro y horquilla (verde inglés)
    "metal":  ("#E5E6EA", 1.00, 0.18),   # cromados (rayos, llantas, manubrio, tija)
    "dark":   ("#3A3A3D", 0.90, 0.35),   # transmisión, potencia, punteras
    "rubber": ("#C9A97A", 0.00, 0.80),   # flancos de las cubiertas y puños (crema)
    "tread":  ("#2B2724", 0.00, 0.90),   # banda de rodamiento de las cubiertas
    "saddle": ("#A0673A", 0.00, 0.45),   # asiento (cuero miel)
}
PAINT_COAT = 0.6                     # barniz sobre la pintura (0 = sin brillo extra, 1 = auto recién lavado)

# Fondo, piso y luces: SOLO afectan el render/video de Blender (no van al .glb;
# en la web el fondo y la luz se configuran en Needle).
BG_COLOR = "#3F3F42"                 # color de fondo
BG_STRENGTH = 1.0                    # el fondo también ilumina la escena: subilo = sombras más suaves y todo más claro
FLOOR = True                         # mostrar piso
FLOOR_COLOR = "#6F6F71"
EXPOSURE = 0.0                       # brillo general en stops (+1 = el doble de claro, -1 = la mitad)
LIGHTS = [  # nombre, posición (x adelante, y lado cadena, z arriba), potencia W, tamaño m, color
    ("Key",  ( 2.5,  1.5, 3.0), 350, 2.5, "#FFFFFF"),   # luz principal
    ("Fill", ( 1.5, -2.5, 1.5), 150, 3.0, "#FFFFFF"),   # relleno: suaviza sombras
    ("Rim",  (-2.5,  0.5, 2.5), 300, 2.0, "#FFFFFF"),   # contraluz: recorta la silueta
]
LIGHT_TARGET = (0.0, 0.0, 0.5)       # punto al que apuntan todas las luces

# Geometría (metros)
WHEEL_R = 0.347                      # radio exterior de la rueda (toca el piso en z=0)
TIRE_R = 0.022                       # grosor de la cubierta
SPOKES = 32                          # rayos por rueda
SPOKE_CROSS = 3                      # cruces de cada rayo (3 = rueda clásica, 0 = radial)
RIM_OUT = WHEEL_R - 2 * TIRE_R + 0.006   # borde exterior de la llanta
BB = Vector((0.0, 0.0, 0.29))        # eje de pedalera
REAR_AXLE = Vector((-0.42, 0.0, WHEEL_R))
FRONT_AXLE = Vector((0.60, 0.0, WHEEL_R))
SEAT_TOP = Vector((-0.13, 0.0, 0.82))
HEAD_TOP = Vector((0.46, 0.0, 0.86))
HEAD_BOT = Vector((0.49, 0.0, 0.74))
CHAIN_PITCH = 0.0127                 # paso de cadena de 1/2"
CHAINRING_TEETH = 44                 # dientes del plato
COG_TEETH = [32, 28, 24, 21, 18, 16, 14, 12]   # coronas del cassette (de la más grande a la más chica)
CHAIN_COG = 4                        # en qué corona está la cadena (índice en COG_TEETH)
COG_Y0, COG_STEP = 0.032, 0.0042     # posición lateral de la primera corona y separación
CHAIN_Y = COG_Y0 + CHAIN_COG * COG_STEP   # plano de la cadena

# Nivel de detalle (bajalo si el .glb pesa mucho para la web)
TIRE_TREAD = True                    # dibujo en la banda de rodamiento
CHAIN_LINKS = True                   # cadena con eslabones reales (False = tubo simple, más liviano)
BEVEL_EDGES = True                   # chaflán en aristas vivas (brillos en los bordes)
BEVEL_WIDTH = 0.0006                 # tamaño del chaflán en metros
SMOOTH_ANGLE = 35                    # aristas con más ángulo que esto quedan vivas

# Desplazamiento de cada parte en la vista explotada (x adelante, y lateral, z arriba).
# Un valor simple = recorrido en línea recta. Una LISTA = recorrido con puntos intermedios
# (cada tramo con su propio easing): sirve para que una pieza salga deslizándose por un
# tubo antes de irse, y al armar (la animación al revés) se inserte en vez de atravesarlo.
HEAD_DIR = (HEAD_TOP - HEAD_BOT).normalized()     # eje del tubo de dirección
EXPLODE = {
    "Cuadro":          (0.00, 0.00, 0.00),
    "Rueda_Trasera":   (-0.42, 0.00, 0.00),
    "Rueda_Delantera": (0.45, 0.00, 0.00),
    "Horquilla":       tuple(-HEAD_DIR * 0.06),   # baja por el eje del tubo de dirección, cerca del cuadro
    "Manubrio":        tuple(HEAD_DIR * 0.347),   # sube recto por el eje (como el asiento por su tubo);
                                                  # 0.347 deja los puños a la altura del cuero del asiento
    "Asiento":         (-0.06, 0.00, 0.28),
    "Transmision":     (0.00, 0.42, -0.04),
}
# Orden en que arrancan a moverse
EXPLODE_ORDER = ["Asiento", "Manubrio", "Horquilla", "Rueda_Delantera",
                 "Rueda_Trasera", "Transmision", "Cuadro"]

# ============ derivados ============
F_START = 1
F_END = F_START + int(round(EXPLODE_SECONDS * FPS))
CAM_F0 = F_START + int(round(CAM_DELAY_SECONDS * FPS))
CAM_F1 = max(CAM_F0 + 1, CAM_F0 + int(round((CAM_SECONDS or EXPLODE_SECONDS - CAM_DELAY_SECONDS) * FPS)))


# ============ materiales ============
def hex_to_linear(hex_color):
    """'#F38145' (sRGB, como en Figma) → RGB lineal que usa Blender."""
    h = hex_color.lstrip("#")
    def lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return tuple(lin(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4))


def make_mat(name, color, metallic=0.0, roughness=0.5, coat=0.0):
    if isinstance(color, str):
        color = hex_to_linear(color)
    full = PREFIX + name
    mat = bpy.data.materials.get(full) or bpy.data.materials.new(full)
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if "Coat Weight" in bsdf.inputs:
        bsdf.inputs["Coat Weight"].default_value = coat
        bsdf.inputs["Coat Roughness"].default_value = 0.05
    mat.diffuse_color = (*color, 1.0)
    return mat


# ============ helpers de geometría ============
Y_AXIS = Vector((0, 1, 0))


def basis(x, y, z):
    """Matriz 4x4 cuyas columnas son los ejes locales x, y, z (deben ser ortonormales)."""
    return Matrix((x, y, z)).transposed().to_4x4()


def smoothstep(e0, e1, x):
    t = min(1.0, max(0.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def smooth_path(pts, sub=6):
    """Curva Catmull-Rom que pasa por todos los puntos."""
    pts = [Vector(p) for p in pts]
    out = []
    for i in range(len(pts) - 1):
        p0 = pts[i - 1] if i > 0 else pts[i]
        p1, p2 = pts[i], pts[i + 1]
        p3 = pts[i + 2] if i + 2 < len(pts) else pts[i + 1]
        for k in range(sub):
            t = k / sub
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(pts[-1])
    return out


def resample_closed(pts, n):
    """Reparte n puntos equidistantes sobre una polilínea cerrada."""
    segs = [(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]
    lens = [(b - a).length for a, b in segs]
    step = sum(lens) / n
    out, acc, k = [], 0.0, 0
    for i in range(n):
        target = i * step
        while k < len(segs) - 1 and acc + lens[k] < target:
            acc += lens[k]
            k += 1
        a, b = segs[k]
        out.append(a.lerp(b, (target - acc) / lens[k] if lens[k] else 0.0))
    return out


def pitch_r(teeth):
    """Radio primitivo de un engranaje de cadena de 1/2" con `teeth` dientes."""
    return CHAIN_PITCH / (2 * math.sin(math.pi / teeth))


def hull2d(points):
    pts = sorted(set(points))
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for q in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], q) <= 0:
            lower.pop()
        lower.append(q)
    for q in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], q) <= 0:
            upper.pop()
        upper.append(q)
    return lower[:-1] + upper[:-1]


# ============ constructor de partes (una bmesh por parte) ============
class Part:
    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.mats = []

    def mi(self, mat):
        if mat not in self.mats:
            self.mats.append(mat)
        return self.mats.index(mat)

    def _assign(self, faces, mat):
        # se asigna a las caras exactas que creó cada primitiva: bmesh reutiliza huecos de
        # memoria, así que "las últimas caras de la lista" no siempre son las nuevas
        idx = self.mi(mat)
        for f in faces:
            f.material_index = idx

    def _assign_verts(self, verts, mat):
        self._assign({f for v in verts for f in v.link_faces}, mat)

    def tube(self, p1, p2, r, mat, seg=24, r2=None):
        p1, p2 = Vector(p1), Vector(p2)
        d = p2 - p1
        rot = d.normalized().to_track_quat('Z', 'Y').to_matrix().to_4x4()
        m = Matrix.Translation((p1 + p2) / 2) @ rot
        res = bmesh.ops.create_cone(self.bm, cap_ends=True, cap_tris=False, segments=seg,
                                    radius1=r, radius2=r if r2 is None else r2,
                                    depth=d.length, matrix=m)
        self._assign_verts(res["verts"], mat)

    def box(self, center, size, mat, rot=None):
        m = Matrix.Translation(Vector(center))
        if rot is not None:
            m = m @ rot
        m = m @ Matrix.Diagonal((*size, 1.0))
        res = bmesh.ops.create_cube(self.bm, size=1.0, matrix=m)
        self._assign_verts(res["verts"], mat)

    def ellipsoid(self, center, size, mat, segs=(24, 12)):
        m = Matrix.Translation(Vector(center)) @ Matrix.Diagonal((*size, 1.0))
        res = bmesh.ops.create_uvsphere(self.bm, u_segments=segs[0], v_segments=segs[1], radius=1.0, matrix=m)
        self._assign_verts(res["verts"], mat)

    def sweep(self, pts, radius, mat, seg=16, closed=False, caps=True, squash=1.0):
        """Tubo que sigue una curva (radio fijo o lista de radios). `squash` aplana
        la sección en el eje lateral → horquillas ovaladas, bielas, placas."""
        pts = [Vector(p) for p in pts]
        n = len(pts)
        radii = radius if isinstance(radius, (list, tuple)) else [radius] * n
        tangents = []
        for i in range(n):
            t = (pts[(i + 1) % n] - pts[i - 1]) if closed else (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)])
            tangents.append(t.normalized())
        ref = Y_AXIS if abs(tangents[0].dot(Y_AXIS)) < 0.9 else Vector((0, 0, 1))
        nrm = tangents[0].cross(ref).normalized()
        faces = []
        rings = []
        for i in range(n):
            t = tangents[i]
            nrm = (nrm - t * nrm.dot(t)).normalized()     # transporte paralelo: sin torsiones
            bi = t.cross(nrm).normalized()
            rings.append([self.bm.verts.new(pts[i] + nrm * (radii[i] * math.cos(2 * math.pi * j / seg))
                                            + bi * (radii[i] * squash * math.sin(2 * math.pi * j / seg)))
                          for j in range(seg)])
        for i in range(n if closed else n - 1):
            a, b = rings[i], rings[(i + 1) % n]
            for j in range(seg):
                j2 = (j + 1) % seg
                faces.append(self.bm.faces.new((a[j], a[j2], b[j2], b[j])))
        if caps and not closed:
            faces.append(self.bm.faces.new(list(reversed(rings[0]))))
            faces.append(self.bm.faces.new(rings[-1]))
        self._assign(faces, mat)

    def revolve(self, center, profile, mat, seg_u=96, mat_fn=None, offset_fn=None):
        """Gira un perfil cerrado [(radio, lateral)] alrededor del eje Y (cubiertas, llantas, mazas)."""
        c = Vector(center)
        m = len(profile)
        rows = []
        for i in range(seg_u):
            a = 2 * math.pi * i / seg_u
            radial = Vector((math.cos(a), 0, math.sin(a)))
            row = []
            for j, (r, y) in enumerate(profile):
                if offset_fn:
                    r += offset_fn(i, j)
                row.append(self.bm.verts.new(c + radial * r + Vector((0, y, 0))))
            rows.append(row)
        for i in range(seg_u):
            i2 = (i + 1) % seg_u
            for j in range(m):
                j2 = (j + 1) % m
                f = self.bm.faces.new((rows[i][j], rows[i][j2], rows[i2][j2], rows[i2][j]))
                f.material_index = self.mi(mat_fn(i, j) if mat_fn else mat)

    def gear(self, center, R, teeth, depth, mat, inner=None, tooth_h=0.0045):
        """Engranaje con dientes cónicos, eje en Y. R = radio primitivo."""
        c = Vector(center)
        root = R - tooth_h * 0.45
        inner = inner or 0.002
        self.revolve(c, [(inner, -depth / 2), (root, -depth / 2), (root, depth / 2), (inner, depth / 2)],
                     mat, seg_u=max(48, teeth * 2))
        w = 2 * math.pi * R / teeth * 0.42
        for i in range(teeth):
            a = 2 * math.pi * i / teeth
            radial = Vector((math.cos(a), 0, math.sin(a)))
            tang = Y_AXIS.cross(radial)
            m = (Matrix.Translation(c + radial * (root + tooth_h / 2)) @ basis(tang, Y_AXIS, radial)
                 @ Matrix.Diagonal((1, depth / w, 1, 1)) @ Matrix.Rotation(math.pi / 4, 4, 'Z'))
            res = bmesh.ops.create_cone(self.bm, cap_ends=True, cap_tris=False, segments=4,
                                        radius1=w * 0.71, radius2=w * 0.32, depth=tooth_h, matrix=m)
            self._assign_verts(res["verts"], mat)

    def build(self, origin=None):
        bm = self.bm
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        if BEVEL_EDGES:   # chaflán mínimo en aristas vivas → brillos realistas en los bordes
            sharp = [e for e in bm.edges if e.is_manifold and e.calc_face_angle(0) > math.radians(60)]
            if sharp:
                try:
                    bmesh.ops.bevel(bm, geom=sharp, offset=BEVEL_WIDTH, segments=2, profile=0.5,
                                    affect='EDGES', clamp_overlap=True)
                except Exception as ex:
                    print("bevel omitido en", self.name, ex)
        for f in bm.faces:
            f.smooth = True
        # "auto smooth": separa las aristas con mucho ángulo para que queden vivas
        hard = [e for e in bm.edges if e.is_manifold and e.calc_face_angle(0) > math.radians(SMOOTH_ANGLE)]
        bmesh.ops.split_edges(bm, edges=hard)
        if origin is None:   # origen en el centro de la caja envolvente → ancla para etiquetas en la web
            lo = Vector((min(v.co[i] for v in bm.verts) for i in range(3)))
            hi = Vector((max(v.co[i] for v in bm.verts) for i in range(3)))
            origin = (lo + hi) / 2
        origin = Vector(origin)
        bmesh.ops.translate(bm, verts=bm.verts[:], vec=-origin)
        me = bpy.data.meshes.new(PREFIX + self.name)
        bm.to_mesh(me)
        bm.free()
        for m in self.mats:
            me.materials.append(m)
        obj = bpy.data.objects.new(PREFIX + self.name, me)
        obj.location = origin
        bpy.context.scene.collection.objects.link(obj)
        return obj


# ============ geometría compartida entre partes ============
def head_dir():
    return (HEAD_TOP - HEAD_BOT).normalized()


def fork_crown():
    return HEAD_BOT - head_dir() * 0.028


def caliper_frame(mount, axle, side_dir):
    """Ejes de un freno de herradura: d = radial (eje → montaje), t = hacia donde mira el freno."""
    d = (mount - axle)
    d.y = 0
    d.normalize()
    t = Y_AXIS.cross(d).normalized()
    if t.dot(side_dir) < 0:
        t = -t
    barrel = axle + d * (WHEEL_R + 0.008) + t * 0.014 + Y_AXIS * 0.032
    return d, t, barrel, barrel + d * 0.022


def top_tube_line():
    st = (SEAT_TOP - BB).normalized()
    return SEAT_TOP - st * 0.035, HEAD_TOP - head_dir() * 0.03


def top_tube_stops():
    """Topes del cable del freno trasero, arriba del tubo superior (adelante, atrás)."""
    a, b = top_tube_line()
    up = -Y_AXIS.cross((b - a).normalized())
    if up.z < 0:
        up = -up
    return a.lerp(b, 0.88) + up * 0.016, a.lerp(b, 0.14) + up * 0.016


def caliper(p, mount, axle, side_dir, M):
    """Freno de herradura (side-pull) con brazos, zapatas, tuerca y regulador de cable."""
    metal, dark = M["metal"], M["dark"]
    d, t, barrel, barrel_top = caliper_frame(mount, axle, side_dir)
    pad_r = RIM_OUT - 0.009
    body = mount + t * 0.016
    p.tube(mount - t * 0.014, body + t * 0.012, 0.0032, metal, seg=12)    # tornillo pasante
    p.tube(body + t * 0.010, body + t * 0.018, 0.0062, metal, seg=6)      # tuerca hexagonal
    for s in (-1, 1):
        arm = smooth_path([body + Y_AXIS * s * 0.004,
                           body + Y_AXIS * s * 0.022 - d * 0.004,
                           axle + d * (WHEEL_R + 0.006) + t * 0.014 + Y_AXIS * s * 0.032,
                           axle + d * (pad_r + 0.014) + t * 0.010 + Y_AXIS * s * 0.026,
                           axle + d * (pad_r + 0.002) + t * 0.007 + Y_AXIS * s * 0.020], 5)
        p.sweep(arm, 0.0046, metal, seg=12, squash=0.55)
        pad = axle + d * pad_r + t * 0.004 + Y_AXIS * s * 0.0158
        p.box(pad, (0.036, 0.0065, 0.009), dark, rot=basis(t, Y_AXIS, t.cross(Y_AXIS)))   # zapata
        p.tube(pad + Y_AXIS * s * 0.003, pad + Y_AXIS * s * 0.008, 0.0035, metal, seg=6)  # tornillo de zapata
    p.tube(barrel, barrel_top, 0.0028, metal, seg=12)                     # regulador del cable
    return barrel_top


def sleeve(p, a, b, r, length, mat):
    """Refuerzo (lug) en el extremo `a` del tubo a→b, como en los cuadros de acero clásicos."""
    a, b = Vector(a), Vector(b)
    p.tube(a, a + (b - a).normalized() * length, r, mat, seg=32)


# ============ partes ============
def build_frame(M):
    p = Part("Cuadro")
    paint, dark, metal = M["paint"], M["dark"], M["metal"]
    Y = Y_AXIS
    st = (SEAT_TOP - BB).normalized()
    hd = head_dir()
    tt0, tt1 = top_tube_line()
    dt1 = HEAD_BOT + hd * 0.025
    p.tube(BB, SEAT_TOP, 0.0143, paint, seg=32)                          # tubo de asiento
    p.tube(tt0, tt1, 0.0127, paint, seg=32)                              # tubo superior
    p.tube(BB, dt1, 0.0175, paint, seg=32, r2=0.0159)                    # tubo inferior (cónico)
    p.tube(HEAD_BOT - hd * 0.004, HEAD_TOP + hd * 0.004, 0.0185, paint, seg=32)  # tubo de dirección
    # refuerzos en las uniones
    sleeve(p, HEAD_TOP, HEAD_BOT, 0.0203, 0.028, paint)
    sleeve(p, HEAD_BOT, HEAD_TOP, 0.0203, 0.030, paint)
    sleeve(p, tt1, tt0, 0.0143, 0.030, paint)
    sleeve(p, tt0, tt1, 0.0143, 0.025, paint)
    sleeve(p, dt1, BB, 0.0182, 0.032, paint)
    sleeve(p, SEAT_TOP, BB, 0.0160, 0.045, paint)
    # juego de dirección (cazoletas arriba y abajo)
    p.tube(HEAD_TOP + hd * 0.004, HEAD_TOP + hd * 0.013, 0.0195, dark, seg=32)
    p.tube(HEAD_BOT - hd * 0.012, HEAD_BOT - hd * 0.004, 0.0205, dark, seg=32)
    # abrazadera de la tija con su tornillo
    p.tube(SEAT_TOP - st * 0.018, SEAT_TOP + st * 0.004, 0.0172, dark, seg=32)
    back = -Y.cross(st)
    bolt = SEAT_TOP - st * 0.008 + back * 0.019
    p.tube(bolt - Y * 0.014, bolt + Y * 0.014, 0.0035, metal, seg=6)
    # caja pedalera
    p.tube(BB - Y * 0.034, BB + Y * 0.034, 0.0195, paint, seg=32)
    # vainas (abajo) y tirantes (arriba), con punteras
    stays = {}
    for s in (-1, 1):
        ax = REAR_AXLE + Y * 0.064 * s
        cs = smooth_path([BB + Vector((-0.03, 0.021 * s, 0.0)), BB + Vector((-0.15, 0.026 * s, 0.012)),
                          REAR_AXLE + Vector((0.12, 0.055 * s, -0.006)), ax + Vector((0.012, 0, 0))], 6)
        p.sweep(cs, [0.0105 - 0.003 * i / (len(cs) - 1) for i in range(len(cs))], paint, seg=20)
        a = SEAT_TOP - st * 0.04 + back * 0.012 + Y * 0.017 * s
        b = ax + Vector((0.004, 0, 0.008))
        p.tube(a, b, 0.0085, paint, seg=20, r2=0.0068)
        p.ellipsoid(a, (0.0095, 0.0095, 0.0095), paint)
        p.box(ax + Vector((0.006, 0, 0.002)), (0.04, 0.006, 0.03), paint)   # puntera
        stays[s] = (a, b)
    p.box(REAR_AXLE + Vector((0.002, 0.069, -0.016)), (0.014, 0.005, 0.032), dark)  # patilla del cambio
    # puente de los tirantes (lleva el freno trasero)
    target = WHEEL_R + 0.03
    def on_stay(a, b):
        lo, hi = 0.0, 1.0
        for _ in range(40):
            mid = (lo + hi) / 2
            q = a.lerp(b, mid)
            if math.hypot(q.x - REAR_AXLE.x, q.z - REAR_AXLE.z) > target:
                lo = mid
            else:
                hi = mid
        return a.lerp(b, lo)
    bl, br = on_stay(*stays[-1]), on_stay(*stays[1])
    p.tube(bl, br, 0.0055, paint, seg=16)
    p.tube(BB + Vector((-0.10, -0.025, 0.006)), BB + Vector((-0.10, 0.025, 0.006)), 0.005, paint, seg=16)
    barrel = caliper(p, (bl + br) / 2, REAR_AXLE, Vector((-1, 0, 0)), M)
    # porta caramañola (dos remaches sobre el tubo inferior)
    ddt = (dt1 - BB).normalized()
    up = -Y.cross(ddt)
    for f in (0.35, 0.58):
        c = BB.lerp(dt1, f)
        p.tube(c + up * 0.015, c + up * 0.021, 0.0032, metal, seg=10)
    # cable del freno trasero: tope delantero → alambre sobre el tubo superior → funda → freno
    front_stop, rear_stop = top_tube_stops()
    ttd = (tt1 - tt0).normalized()
    for stop in (front_stop, rear_stop):
        p.box(stop + Vector((0, 0, -0.005)), (0.016, 0.006, 0.01), paint, rot=basis(ttd, Y, ttd.cross(Y)))
    p.tube(front_stop, rear_stop, 0.0008, metal, seg=6)
    housing = smooth_path([rear_stop - ttd * 0.006, rear_stop - ttd * 0.04 + Vector((0, 0.01, 0.035)),
                           barrel + Vector((0.02, 0.0, 0.07)), barrel], 8)
    p.sweep(housing, 0.0025, dark, seg=10)
    return p.build()


def build_fork(M):
    p = Part("Horquilla")
    paint, dark, metal = M["paint"], M["dark"], M["metal"]
    Y = Y_AXIS
    hd = head_dir()
    crown = fork_crown()
    fwd = Vector((hd.z, 0, -hd.x))
    p.tube(crown + hd * 0.012, crown + hd * 0.020, 0.0195, dark, seg=32)  # anillo de rodamiento
    p.box(crown - hd * 0.002, (0.034, 0.112, 0.026), paint, rot=basis(fwd, Y, hd))   # corona
    for s in (-1, 1):
        top = crown - hd * 0.012 + Y * 0.046 * s
        p.ellipsoid(top, (0.017, 0.015, 0.017), paint)                   # hombros
        end = FRONT_AXLE + Y * 0.05 * s
        blade = smooth_path([top, top - hd * 0.16 + Y * 0.003 * s, end + Vector((-0.012, 0, 0.10)),
                             end + Vector((0.0, 0, 0.012))], 8)
        p.sweep(blade, [0.0125 - 0.0047 * i / (len(blade) - 1) for i in range(len(blade))],
                paint, seg=24, squash=0.72)                              # brazos curvos y ovalados
        p.box(end + Vector((0.004, 0, 0.004)), (0.024, 0.005, 0.03), paint)   # puntera
    caliper(p, crown, FRONT_AXLE, Vector((1, 0, 0)), M)
    return p.build()


def build_wheel(M, name, axle, rear):
    p = Part(name)
    Y = Y_AXIS
    metal, dark, rubber, tread = M["metal"], M["dark"], M["rubber"], M["tread"]
    # cubierta: banda de rodamiento con dibujo + flancos de otro color
    Rt = WHEEL_R - TIRE_R
    nv = 28
    prof = [(Rt + TIRE_R * math.cos(2 * math.pi * j / nv), TIRE_R * 0.9 * math.sin(2 * math.pi * j / nv))
            for j in range(nv)]
    def is_tread(j):
        return math.cos(2 * math.pi * j / nv) > 0.55
    def tread_offset(i, j):
        if not TIRE_TREAD or not is_tread(j):
            return 0.0
        side = j if j <= nv // 2 else nv - j
        return 0.0011 if (i + side * 2) % 6 < 3 else 0.0                 # dibujo en espiga
    p.revolve(axle, prof, rubber, seg_u=300, offset_fn=tread_offset,
              mat_fn=lambda i, j: tread if (is_tread(j) and is_tread((j + 1) % nv)) else rubber)
    # llanta de perfil en caja, con canal para la cubierta
    o = RIM_OUT
    rim = [(o, 0.0105), (o - 0.006, 0.0105), (o - 0.020, 0.008), (o - 0.026, 0.004), (o - 0.027, 0.0),
           (o - 0.026, -0.004), (o - 0.020, -0.008), (o - 0.006, -0.0105), (o, -0.0105),
           (o - 0.003, -0.006), (o - 0.003, 0.006)]
    p.revolve(axle, rim, metal, seg_u=160)
    # maza con bridas (la trasera deja lugar al cassette)
    W = 0.062 if rear else 0.048
    fl, fr = 0.030, (0.020 if rear else 0.030)
    hub = [(0.0045, -W), (0.0105, -W), (0.0105, -W + 0.006), (0.0135, -fl - 0.004), (0.0255, -fl - 0.002),
           (0.0255, -fl + 0.0015), (0.0135, -fl + 0.003), (0.0155, 0.0), (0.0135, fr - 0.003),
           (0.0255, fr - 0.0015), (0.0255, fr + 0.002), (0.0135, fr + 0.004), (0.0105, W - 0.006),
           (0.0105, W), (0.0045, W)]
    p.revolve(axle, hub, metal, seg_u=48)
    # rayos cruzados (como una rueda real) con niples en la llanta
    rim_in = RIM_OUT - 0.024
    cross = SPOKE_CROSS * 4 * math.pi / SPOKES
    for k in range(SPOKES):
        side = 1 if k % 2 == 0 else -1
        lead = 1 if (k // 2) % 2 == 0 else -1
        ra = 2 * math.pi * k / SPOKES
        ha = ra + lead * cross
        hub_pt = axle + Vector((math.cos(ha) * 0.0235, fr if side > 0 else -fl, math.sin(ha) * 0.0235))
        rim_pt = axle + Vector((math.cos(ra), 0, math.sin(ra))) * rim_in
        dv = (rim_pt - hub_pt).normalized()
        p.tube(hub_pt, rim_pt, 0.0011, metal, seg=6)
        p.tube(rim_pt - dv * 0.012, rim_pt + dv * 0.004, 0.0021, metal, seg=8)
    # válvula
    va = math.pi / 2 + math.pi / SPOKES
    rad = Vector((math.cos(va), 0, math.sin(va)))
    p.tube(axle + rad * (RIM_OUT - 0.026), axle + rad * (RIM_OUT - 0.055), 0.003, metal, seg=10)
    p.tube(axle + rad * (RIM_OUT - 0.055), axle + rad * (RIM_OUT - 0.066), 0.0037, dark, seg=12)
    # cierre rápido: palanca de un lado, tuerca del otro
    c = axle - Y * (W + 0.004)
    p.tube(axle - Y * W, axle + Y * W, 0.0045, metal, seg=12)              # eje
    p.tube(axle - Y * (W + 0.002), axle - Y * (W + 0.012), 0.0095, metal, seg=24)
    lever = smooth_path([c - Y * 0.007, c - Y * 0.01 + Vector((-0.02, 0, 0.006)),
                         c - Y * 0.009 + Vector((-0.058, 0, 0.022))], 6)
    p.sweep(lever, [0.0045 + 0.002 * i / (len(lever) - 1) for i in range(len(lever))], metal, seg=12, squash=0.45)
    p.tube(axle + Y * (W + 0.002), axle + Y * (W + 0.010), 0.0075, metal, seg=6)
    return p.build(origin=axle)   # origen exacto en el eje → gira sin bambolearse


def build_handlebar(M):
    p = Part("Manubrio")
    paint, dark, metal, rubber = M["paint"], M["dark"], M["metal"], M["rubber"]
    Y, up, X = Y_AXIS, Vector((0, 0, 1)), Vector((1, 0, 0))
    hd = head_dir()
    fwd = Vector((hd.z, 0, -hd.x))
    # potencia: abrazadera al tubo de dirección + extensión + tapa frontal con 4 tornillos
    c0, c1 = HEAD_TOP + hd * 0.013, HEAD_TOP + hd * 0.053
    # tubo de dirección (steerer): va con el manubrio para que en la vista explotada
    # salgan juntos; el corte queda sobre la corona de la horquilla
    p.tube(fork_crown() + hd * 0.021, c1 - hd * 0.002, 0.0125, metal, seg=24)
    p.tube(c0, c1, 0.0175, dark, seg=32)
    p.tube(c1, c1 + hd * 0.005, 0.0165, dark, seg=32)                      # tapa superior
    p.tube(c1 + hd * 0.004, c1 + hd * 0.008, 0.0045, metal, seg=6)
    for f in (0.3, 0.7):
        b = c0.lerp(c1, f) - fwd * 0.019
        p.tube(b - Y * 0.012, b + Y * 0.012, 0.0034, metal, seg=6)        # tornillos de apriete
    cm = c0.lerp(c1, 0.5)
    ext = Vector((0.99, 0, 0.12)).normalized()
    bar_c = cm + ext * 0.09
    p.tube(cm, bar_c, 0.0145, dark, seg=24)
    p.tube(bar_c - Y * 0.022, bar_c + Y * 0.022, 0.0178, dark, seg=32)     # abrazadera del manubrio
    face = bar_c + ext * 0.014
    p.box(face, (0.007, 0.044, 0.038), dark, rot=basis(ext, Y, ext.cross(Y)))
    for dy in (-0.015, 0.015):
        for dz in (-0.013, 0.013):
            q = face + Y * dy + ext.cross(Y) * dz
            p.tube(q, q + ext * 0.006, 0.003, metal, seg=6)
    # manubrio: centro grueso, curva con subida y retroceso hacia los puños
    def half(s):
        return [bar_c + Vector((0, s * 0.045, 0)), bar_c + Vector((-0.004, s * 0.08, 0.008)),
                bar_c + Vector((-0.014, s * 0.115, 0.018)), bar_c + Vector((-0.026, s * 0.16, 0.022)),
                bar_c + Vector((-0.05, s * 0.30, 0.026))]
    path = smooth_path(list(reversed(half(-1))) + [bar_c] + half(1), 6)
    radii = [0.011 + 0.0049 * smoothstep(0.06, 0.035, abs(q.y)) for q in path]
    p.sweep(path, radii, metal, seg=24)
    front_barrel = caliper_frame(fork_crown(), FRONT_AXLE, X)[3]
    rear_stop = top_tube_stops()[0]
    for s in (-1, 1):
        h = half(s)
        g = (h[4] - h[3]).normalized()
        g0 = h[3].lerp(h[4], (0.19 - 0.16) / 0.14)
        # puños con anillos de agarre y tapón
        n = 12
        for k in range(n):
            a, b = g0.lerp(h[4], k / n), g0.lerp(h[4], (k + 1) / n)
            p.tube(a, b, 0.0172 if k % 2 == 0 else 0.0162, rubber, seg=24)
        p.tube(h[4] - g * 0.002, h[4] + g * 0.007, 0.0168, dark, seg=24)
        # maneta de freno
        lc = h[3].lerp(h[4], (0.172 - 0.16) / 0.14)
        p.tube(lc - g * 0.007, lc + g * 0.007, 0.0148, dark, seg=24)
        p.ellipsoid(lc + X * 0.017 + up * 0.002, (0.014, 0.011, 0.013), dark)
        blade = smooth_path([lc + X * 0.016, lc + X * 0.032 + g * 0.014, lc + X * 0.034 + g * 0.05 - up * 0.006,
                             lc + X * 0.031 + g * 0.088 - up * 0.011], 6)
        p.sweep(blade, 0.0044, metal, seg=12, squash=0.45)
        # funda del cable: derecha → freno delantero, izquierda → tubo superior (freno trasero)
        start = lc + X * 0.018 + up * 0.012
        if s > 0:
            pts = [start, start + X * 0.03 + up * 0.03 - Y * 0.04, bar_c + X * 0.09 + Y * 0.03 - up * 0.02,
                   front_barrel + Vector((0.035, 0.0, 0.07)), front_barrel + Vector((0, 0, 0.004))]
        else:
            pts = [start, start + X * 0.03 + up * 0.03 + Y * 0.04, bar_c + X * 0.07 - Y * 0.035 - up * 0.03,
                   rear_stop + Vector((0.06, -0.02, 0.03)), rear_stop + Vector((-0.004, 0, 0.004))]
        p.sweep(smooth_path(pts, 8), 0.0025, dark, seg=10)
    # timbre
    bell = bar_c + Vector((-0.002, -0.066, 0.004))
    p.tube(bell - Y * 0.004, bell + Y * 0.004, 0.0175, dark, seg=24)
    p.tube(bell, bell + up * 0.018, 0.003, metal, seg=10)
    p.ellipsoid(bell + up * 0.026, (0.019, 0.019, 0.012), metal)
    p.box(bell + up * 0.016 + X * 0.012, (0.016, 0.004, 0.003), metal)
    return p.build()


def build_saddle(M):
    p = Part("Asiento")
    leather, metal, dark = M["saddle"], M["metal"], M["dark"]
    Y, up = Y_AXIS, Vector((0, 0, 1))
    d = (SEAT_TOP - BB).normalized()
    post_top = SEAT_TOP + d * 0.11
    p.tube(SEAT_TOP - d * 0.08, post_top, 0.0135, metal, seg=32)           # tija
    p.tube(post_top - Y * 0.02, post_top + Y * 0.02, 0.0105, dark, seg=24)  # cabezal de la tija
    p.box(post_top + up * 0.007, (0.042, 0.05, 0.008), dark)
    p.tube(post_top - Y * 0.026, post_top + Y * 0.026, 0.0035, metal, seg=6)
    S = post_top + Vector((0.005, 0, 0.045))
    # carcasa del asiento: sección abovedada que se afina de la cola a la punta
    x0, x1, nx, nk, skirt = -0.095, 0.17, 40, 18, 0.012
    def section(u):
        back = smoothstep(0.55, 0.15, u)
        env = max(0.0, 1 - abs(2 * u - 1) ** 10) ** 0.5
        w = (0.021 + 0.064 * back) * env + 0.002
        top = (0.020 + 0.006 * back - 0.004 * u) * env + 0.004
        zc = 0.006 * math.sin(math.pi * u) - 0.004 * u
        return w, top, zc, env
    faces = []
    rings = []
    for i in range(nx):
        u = i / (nx - 1)
        x = x0 + (x1 - x0) * u
        w, top, zc, env = section(u)
        ring = []
        for k in range(nk + 1):
            th = math.pi * k / nk
            ring.append(S + Vector((x, w * math.cos(th), zc + top * (math.sin(th) ** 0.55))))
        for yy in (-0.98, -0.5, 0.0, 0.5, 0.98):
            ring.append(S + Vector((x, w * yy, zc - skirt * env)))
        rings.append([p.bm.verts.new(v) for v in ring])
    m = len(rings[0])
    for i in range(nx - 1):
        a, b = rings[i], rings[i + 1]
        for k in range(m):
            k2 = (k + 1) % m
            faces.append(p.bm.faces.new((a[k], b[k], b[k2], a[k2])))
    faces.append(p.bm.faces.new(rings[0]))
    faces.append(p.bm.faces.new(list(reversed(rings[-1]))))
    p._assign(faces, leather)
    # remaches de cobre en la cola
    w, top, zc, _ = section(0.07)
    for yy in (-0.6, -0.3, 0.0, 0.3, 0.6):
        th = math.acos(yy)
        p.ellipsoid(S + Vector((x0 + (x1 - x0) * 0.07, w * yy, zc + top * (math.sin(th) ** 0.55))),
                    (0.0032, 0.0032, 0.0022), metal, segs=(12, 6))
    # rieles debajo de la carcasa
    for s in (-1, 1):
        rail = smooth_path([S + Vector((0.115, s * 0.004, -0.004)), S + Vector((0.07, s * 0.019, -0.026)),
                            post_top + Vector((0.025, s * 0.021, 0.006)), post_top + Vector((-0.03, s * 0.021, 0.006)),
                            S + Vector((-0.068, s * 0.032, -0.024)), S + Vector((-0.082, s * 0.038, -0.004))], 6)
        p.sweep(rail, 0.0035, metal, seg=12)
    return p.build()


def pedal(p, tip, s, M):
    """Pedal plataforma: eje, cuerpo central, jaula y pines."""
    dark, metal = M["dark"], M["metal"]
    Y = Y_AXIS
    p.tube(tip, tip + Y * s * 0.022, 0.0065, metal, seg=12)
    c = tip + Y * s * 0.07
    p.tube(c - Y * 0.048, c + Y * 0.048, 0.0095, dark, seg=16)
    for dx in (-0.05, 0.05):
        p.box(c + Vector((dx, 0, 0)), (0.005, 0.096, 0.024), dark)
    for dy in (-0.046, 0.046):
        p.box(c + Vector((0, dy, 0)), (0.10, 0.005, 0.02), dark)
    for dx in (-0.05, 0.05):
        for dy in (-0.03, -0.01, 0.01, 0.03):
            for dz in (-1, 1):
                p.tube(c + Vector((dx, dy, dz * 0.012)), c + Vector((dx, dy, dz * 0.0155)), 0.0016, metal, seg=6)


def build_drivetrain(M):
    p = Part("Transmision")
    dark, metal = M["dark"], M["metal"]
    Y, X = Y_AXIS, Vector((1, 0, 0))
    # plato con araña de 5 brazos
    ring_c = BB + Y * CHAIN_Y
    ringR = pitch_r(CHAINRING_TEETH)
    p.gear(ring_c, ringR, CHAINRING_TEETH, 0.004, metal, inner=0.072)
    crank_a = math.radians(-35)
    y_sp = CHAIN_Y + 0.006
    for i in range(5):
        a = crank_a + 2 * math.pi * i / 5 + math.pi / 5
        rad = Vector((math.cos(a), 0, math.sin(a)))
        p.sweep([BB + Y * y_sp + rad * 0.015, BB + Y * y_sp + rad * 0.076], [0.0075, 0.0055], dark, seg=12, squash=0.6)
        p.tube(BB + Y * (CHAIN_Y - 0.003) + rad * 0.074, BB + Y * (y_sp + 0.004) + rad * 0.074, 0.0042, metal, seg=12)
    p.tube(BB + Y * (CHAIN_Y + 0.002), BB + Y * 0.062, 0.021, dark, seg=32)
    p.tube(BB - Y * 0.075, BB + Y * 0.075, 0.009, metal, seg=16)            # eje de pedalera
    # bielas y pedales
    for s, a in ((1, crank_a), (-1, crank_a + math.pi)):
        y = 0.067 * s
        rad = Vector((math.cos(a), 0, math.sin(a)))
        tip = BB + rad * 0.170 + Y * y
        p.sweep([BB + Y * y, BB + Y * y + rad * 0.085, tip], [0.0135, 0.0115, 0.0095], dark, seg=20, squash=0.55)
        p.tube(BB + Y * (y - s * 0.006), BB + Y * (y + s * 0.008), 0.0145, dark, seg=24)
        p.tube(BB + Y * (y + s * 0.008), BB + Y * (y + s * 0.010), 0.008, metal, seg=6)
        p.tube(tip - Y * s * 0.006, tip + Y * s * 0.006, 0.0105, dark, seg=20)
        pedal(p, tip + Y * s * 0.006, s, M)
    # cassette de 8 coronas
    for i, n in enumerate(COG_TEETH):
        p.gear(REAR_AXLE + Y * (COG_Y0 + i * COG_STEP), pitch_r(n), n, 0.0018, metal, inner=0.012)
    p.tube(REAR_AXLE + Y * (COG_Y0 - 0.003), REAR_AXLE + Y * (COG_Y0 + len(COG_TEETH) * COG_STEP), 0.016, dark, seg=32)
    # cambio trasero: dos roldanas en una jaula + cuerpo articulado
    cog_c = REAR_AXLE + Y * CHAIN_Y
    cogR = pitch_r(COG_TEETH[CHAIN_COG])
    jR = pitch_r(11)
    L = REAR_AXLE + Vector((0.03, CHAIN_Y, -0.145))
    a, b = cog_c - X * cogR, L - X * jR
    dirv = (b - a).normalized()
    U = (a + b) / 2 + Vector((-dirv.z, 0, dirv.x)) * (jR + 0.0015)
    for w in (U, L):
        p.gear(w, jR, 11, 0.004, dark, inner=0.004)
        p.tube(w - Y * 0.011, w + Y * 0.011, 0.0042, metal, seg=12)
    for s in (-1, 1):
        p.sweep([U + Y * s * 0.008, L + Y * s * 0.008], 0.013, metal, seg=24, squash=0.12)  # placas de la jaula
    K = REAR_AXLE + Vector((-0.004, 0.073, -0.024))
    p.tube(K - Y * 0.004, K + Y * 0.01, 0.009, dark, seg=20)
    P = U + Vector((-0.012, 0.016, 0.012))
    p.sweep(smooth_path([K, K + Vector((-0.022, -0.004, -0.018)), P], 6), 0.0085, dark, seg=16, squash=0.6)
    p.tube(U + Y * 0.010, U + Y * 0.022, 0.011, dark, seg=24)
    # cadena: recorrido envolvente plato → piñón → roldana, con eslabones reales
    samples = []
    for c, r in ((ring_c, ringR), (cog_c, cogR), (L, jR)):
        for i in range(96):
            t = 2 * math.pi * i / 96
            samples.append((round(c.x + r * math.cos(t), 6), round(c.z + r * math.sin(t), 6)))
    hull = [Vector((x, CHAIN_Y, z)) for x, z in hull2d(samples)]
    total = sum((hull[(i + 1) % len(hull)] - hull[i]).length for i in range(len(hull)))
    pins = resample_closed(hull, max(20, round(total / CHAIN_PITCH)))
    if CHAIN_LINKS:
        for i in range(len(pins)):
            a, b = pins[i], pins[(i + 1) % len(pins)]
            dv = (b - a).normalized()
            rot = basis(dv, Y, dv.cross(Y))
            outer = i % 2 == 0
            oy, h, mat = (0.0047, 0.0086, metal) if outer else (0.0032, 0.0076, dark)
            for s in (-1, 1):
                p.box((a + b) / 2 + Y * oy * s, ((b - a).length * 1.32, 0.0011, h), mat, rot=rot)
            p.tube(a - Y * 0.0053, a + Y * 0.0053, 0.0026, metal, seg=8)
    else:
        p.sweep(pins, 0.0045, dark, seg=8, closed=True)
    return p.build()


# ============ animación ============
def explode_path(key):
    """Puntos del recorrido de una pieza (relativos a su posición armada)."""
    v = EXPLODE[key]
    return [Vector(p) for p in v] if isinstance(v, list) else [Vector(v)]


def animate(parts):
    scene = bpy.context.scene
    scene.render.fps = FPS
    scene.frame_start, scene.frame_end = F_START, F_END
    total = F_END - F_START
    n = len(EXPLODE_ORDER)
    dur = total * (1 - STAGGER * (n - 1))
    prefs = bpy.context.preferences.edit
    prev = prefs.keyframe_new_interpolation_type
    prefs.keyframe_new_interpolation_type = 'BEZIER'
    for i, key in enumerate(EXPLODE_ORDER):
        obj = parts[key]
        base = obj.location.copy()
        f0 = F_START + round(total * STAGGER * i)
        f1 = min(F_END, round(f0 + dur))
        spin = "Rueda" in key
        path = explode_path(key)
        # tiempo de cada tramo proporcional a su largo
        lens = [(b - a).length for a, b in zip([Vector()] + path[:-1], path)]
        total_len = sum(lens) or 1.0
        loc_keys = [(F_START, base), (f0, base)]
        acc = 0.0
        for wp, l in zip(path, lens):
            acc += l
            loc_keys.append((round(f0 + (f1 - f0) * acc / total_len), base + wp))
        loc_keys.append((F_END, base + path[-1]))
        for f, loc in loc_keys:
            obj.location = loc
            obj.keyframe_insert("location", frame=f)
        if spin:
            # gira como si rodara: sentido según hacia dónde se desplaza en X
            # (+Y en Blender lleva la parte de arriba de la rueda hacia +X)
            roll = math.copysign(1.0, path[-1].x)
            for f, rot in ((F_START, 0.0), (f0, 0.0), (f1, 1.0), (F_END, 1.0)):
                obj.rotation_euler = (0, roll * rot * WHEEL_SPIN_TURNS * 2 * math.pi, 0)
                obj.keyframe_insert("rotation_euler", frame=f)
        obj.location = base
        obj.rotation_euler = (0, 0, 0)
    prefs.keyframe_new_interpolation_type = prev
    for obj in parts.values():
        apply_easing(obj)
    scene.frame_set(F_START)


def get_fcurves(obj):
    """F-curves de un objeto en Blender 4.4+/5.x (acciones con slots; Action.fcurves ya no existe)."""
    ad = obj.animation_data
    if not ad or not ad.action:
        return []
    fcs = []
    for layer in ad.action.layers:
        for strip in layer.strips:
            cb = strip.channelbag(ad.action_slot)
            if cb:
                fcs.extend(cb.fcurves)
    return fcs


def apply_easing(obj):
    # La interpolación de un keyframe define el tramo hasta el siguiente;
    # los tramos de "espera" tienen el mismo valor en ambos extremos, así que no se ven afectados.
    for fc in get_fcurves(obj):
        for kp in fc.keyframe_points:
            kp.interpolation = EASING_TYPE
            if EASING_TYPE != 'BEZIER':
                kp.easing = EASING_MODE
        fc.update()


# ============ preview (cámara + luces, NO se exportan) ============
def setup_preview():
    scene = bpy.context.scene
    for eng in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
        try:
            scene.render.engine = eng
            break
        except Exception:
            continue
    scene.render.resolution_x, scene.render.resolution_y = 1280, 720
    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == 'BACKGROUND')
    bg.inputs["Color"].default_value = (*hex_to_linear(BG_COLOR), 1)
    bg.inputs["Strength"].default_value = BG_STRENGTH

    scene.view_settings.view_transform = 'Standard'   # colores fieles a los hex (AgX los lava)
    scene.view_settings.exposure = EXPOSURE
    try:
        scene.eevee.taa_render_samples = 32
        scene.eevee.use_raytracing = True      # reflejos reales en cromados y pintura
    except Exception:
        pass

    if FLOOR:   # piso (solo preview, no se exporta)
        me = bpy.data.meshes.new(PREFIX + "Piso")
        bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=4.0)
        bm.to_mesh(me)
        bm.free()
        me.materials.append(make_mat("Piso", FLOOR_COLOR, 0.0, 0.8))
        floor = bpy.data.objects.new(PREFIX + "Piso", me)
        scene.collection.objects.link(floor)

    animate_camera()

    for name, loc, energy, size, color in LIGHTS:
        ld = bpy.data.lights.new(PREFIX + name, 'AREA')
        ld.energy, ld.size = energy, size
        ld.color = hex_to_linear(color)
        lo = bpy.data.objects.new(PREFIX + name, ld)
        lo.location = loc
        lo.rotation_euler = (Vector(LIGHT_TARGET) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
        scene.collection.objects.link(lo)


def ease(t):
    if CAM_EASE == 'LINEAR':
        return t
    if CAM_EASE == 'EASE_OUT':
        return 1 - (1 - t) ** 3
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2   # EASE_IN_OUT (cubic)


def orbit_point(view):
    az, el = math.radians(view["azimuth"]), math.radians(view["elevation"])
    target = Vector(view["target"])
    d = view["distance"]
    return target + Vector((math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el))) * d, target


def animate_camera():
    """Órbita de CAM_START a CAM_END en paralelo al desarme. Se interpola en ángulos
    (no en línea recta) para que la cámara gire alrededor de la bici."""
    scene = bpy.context.scene
    cam_data = bpy.data.cameras.new(PREFIX + "Cam")
    cam_data.lens = CAM_LENS
    cam = bpy.data.objects.new(PREFIX + "Cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    prefs = bpy.context.preferences.edit
    prev = prefs.keyframe_new_interpolation_type
    prefs.keyframe_new_interpolation_type = 'LINEAR'   # el easing ya va calculado en cada frame
    for f in range(F_START, F_END + 1):
        t = ease(min(1.0, max(0.0, (f - CAM_F0) / (CAM_F1 - CAM_F0))))
        view = {k: (CAM_START[k] + (CAM_END[k] - CAM_START[k]) * t) if k != "target"
                else Vector(CAM_START[k]).lerp(Vector(CAM_END[k]), t) for k in CAM_START}
        pos, target = orbit_point(view)
        cam.location = pos
        cam.rotation_euler = (target - pos).to_track_quat('-Z', 'Y').to_euler()
        cam.keyframe_insert("location", frame=f)
        cam.keyframe_insert("rotation_euler", frame=f)
    prefs.keyframe_new_interpolation_type = prev
    # al abrir el .blend, los viewports 3D miran por la cámara (Numpad 0 para entrar/salir)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                try:
                    area.spaces[0].region_3d.view_perspective = 'CAMERA'
                except Exception:
                    pass


def render_video():
    """Renderiza la animación con la cámara y arma un MP4 con pausas al inicio y al final."""
    import subprocess, shutil
    scene = bpy.context.scene
    frames_dir = os.path.join(PREVIEW_DIR, "frames")
    shutil.rmtree(frames_dir, ignore_errors=True)
    os.makedirs(frames_dir)
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = (frames_dir + "/f_####").replace("{", "{{").replace("}", "}}")
    bpy.ops.render.render(animation=True)
    out = os.path.join(PREVIEW_DIR, "bici_animacion.mp4")
    ffmpeg = shutil.which("ffmpeg") or os.path.expanduser("~/.local/bin/ffmpeg")
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-framerate", str(FPS),
                    "-i", os.path.join(frames_dir, "f_%04d.png"),
                    "-vf", f"tpad=start_mode=clone:start_duration={VIDEO_HOLD_START}"
                           f":stop_mode=clone:stop_duration={VIDEO_HOLD_END},format=yuv420p",
                    "-c:v", "libx264", "-crf", "18", out], check=True)
    shutil.rmtree(frames_dir, ignore_errors=True)
    print("Video:", out)


def render_previews():
    scene = bpy.context.scene
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    for f, tag in ((F_START, "armada"), (F_END, "explotada")):
        scene.frame_set(f)
        # Blender 5 interpreta { } en rutas como plantillas: se escapan duplicándolas
        scene.render.filepath = os.path.join(PREVIEW_DIR, f"bici_{tag}.png").replace("{", "{{").replace("}", "}}")
        bpy.ops.render.render(write_still=True)
    scene.frame_set(F_START)


# ============ export ============
def export_glb(parts):
    os.makedirs(os.path.dirname(GLB_PATH), exist_ok=True)
    for o in bpy.context.scene.objects:
        o.select_set(False)
    for o in parts.values():
        o.select_set(True)
    bpy.context.view_layer.objects.active = next(iter(parts.values()))
    bpy.ops.export_scene.gltf(
        filepath=os.path.abspath(GLB_PATH),
        export_format='GLB',
        use_selection=True,
        export_animations=True,
        export_animation_mode='ACTIVE_ACTIONS',   # un solo clip con todas las partes
        export_yup=True,
        export_apply=True,
    )
    print("GLB exportado en", os.path.abspath(GLB_PATH))
    optimize_for_web()


def optimize_for_web():
    """Comprime el .glb para la web (meshopt, ~5x más liviano) con el script `optimize` del proyecto."""
    import subprocess, shutil
    npm = shutil.which("npm") or "/usr/local/bin/npm"
    web = os.path.abspath(WEB_DIR)
    try:
        subprocess.run([npm, "run", "optimize", "--silent"], cwd=web, check=True,
                       env={**os.environ, "PATH": os.environ.get("PATH", "") + ":/usr/local/bin:/opt/homebrew/bin"})
        print("GLB optimizado en", os.path.join(web, "public", "models", "bici.glb"))
    except Exception as ex:   # sin Node a mano: se copia sin comprimir para que la web siga andando
        shutil.copyfile(os.path.abspath(GLB_PATH), os.path.join(web, "public", "models", "bici.glb"))
        print("No se pudo optimizar (", ex, "); se copió el GLB sin comprimir")


# ============ main ============
def cleanup():
    for o in list(bpy.data.objects):
        if o.name.startswith(PREFIX) or (bpy.app.background and o.name in ("Cube", "Light", "Camera")):
            data, t = o.data, o.type
            bpy.data.objects.remove(o, do_unlink=True)
            if data is not None and data.users == 0:
                {'MESH': bpy.data.meshes, 'CAMERA': bpy.data.cameras, 'LIGHT': bpy.data.lights}.get(t, None) \
                    and {'MESH': bpy.data.meshes, 'CAMERA': bpy.data.cameras, 'LIGHT': bpy.data.lights}[t].remove(data)
    for a in list(bpy.data.actions):
        if a.users == 0:
            bpy.data.actions.remove(a)


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    cleanup()
    names = {"paint": "Pintura", "metal": "Metal", "dark": "MetalOscuro", "rubber": "Goma",
             "saddle": "Cuero", "tread": "Banda"}
    M = {k: make_mat(names.get(k, k), *v, coat=PAINT_COAT if k == "paint" else 0.0) for k, v in MATERIALS.items()}
    parts = {
        "Cuadro": build_frame(M),
        "Horquilla": build_fork(M),
        "Rueda_Trasera": build_wheel(M, "Rueda_Trasera", REAR_AXLE, rear=True),
        "Rueda_Delantera": build_wheel(M, "Rueda_Delantera", FRONT_AXLE, rear=False),
        "Manubrio": build_handlebar(M),
        "Asiento": build_saddle(M),
        "Transmision": build_drivetrain(M),
    }
    animate(parts)
    setup_preview()
    export_glb(parts)
    if bpy.app.background:
        if "--save" in args:   # opcional: no pisa el .blend que estés usando en Blender
            bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
        if "--render" in args:
            render_previews()
        if "--video" in args:
            render_video()


main()
