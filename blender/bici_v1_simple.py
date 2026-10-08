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
GLB_PATH = os.path.join(HERE, "..", "web", "public", "models", "bici.glb")
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
CAM_DELAY_SECONDS = 0.0              # espera antes de que la cámara empiece a moverse
VIDEO_HOLD_START = 0.6               # segundos quieta al inicio del video de preview
VIDEO_HOLD_END = 1.2                 # segundos quieta al final

# ---------- LOOK: colores en HEX (como en Figma) ----------
# Los materiales de la bici viajan en el .glb → se ven igual en la web.
MATERIALS = {          #  color      metálico (0-1)  rugosidad (0 = espejo, 1 = mate)
    "paint":  ("#1F4D3A", 0.35, 0.25),   # pintura del cuadro y horquilla (verde inglés)
    "metal":  ("#E5E6EA", 1.00, 0.18),   # cromados (rayos, llantas, manubrio, tija)
    "dark":   ("#3A3A3D", 0.90, 0.35),   # transmisión, potencia, punteras
    "rubber": ("#C9A97A", 0.00, 0.80),   # cubiertas y puños (crema)
    "saddle": ("#A0673A", 0.00, 0.45),   # asiento (cuero miel)
}
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
SPOKES = 24
BB = Vector((0.0, 0.0, 0.29))        # eje de pedalera
REAR_AXLE = Vector((-0.42, 0.0, WHEEL_R))
FRONT_AXLE = Vector((0.60, 0.0, WHEEL_R))
SEAT_TOP = Vector((-0.13, 0.0, 0.82))
HEAD_TOP = Vector((0.46, 0.0, 0.86))
HEAD_BOT = Vector((0.49, 0.0, 0.74))
CHAIN_Y = 0.075                      # plano lateral de cadena/plato

# Desplazamiento de cada parte en la vista explotada (x adelante, y lateral, z arriba)
EXPLODE = {
    "Cuadro":          (0.00, 0.00, 0.00),
    "Rueda_Trasera":   (-0.42, 0.00, 0.00),
    "Rueda_Delantera": (0.45, 0.00, 0.00),
    "Horquilla":       (0.16, 0.00, 0.22),
    "Manubrio":        (0.10, 0.00, 0.48),
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


def make_mat(name, color, metallic=0.0, roughness=0.5):
    if isinstance(color, str):
        color = hex_to_linear(color)
    full = PREFIX + name
    mat = bpy.data.materials.get(full) or bpy.data.materials.new(full)
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    mat.diffuse_color = (*color, 1.0)
    return mat


# ============ constructor de partes (una bmesh por parte) ============
class Part:
    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.mats = []

    def _begin(self):
        self.bm.faces.ensure_lookup_table()
        return len(self.bm.faces)

    def _end(self, n0, mat, smooth):
        if mat not in self.mats:
            self.mats.append(mat)
        idx = self.mats.index(mat)
        self.bm.faces.ensure_lookup_table()
        for f in self.bm.faces[n0:]:
            f.material_index = idx
            f.smooth = smooth

    def tube(self, p1, p2, r, mat, seg=16, r2=None, smooth=True):
        p1, p2 = Vector(p1), Vector(p2)
        d = p2 - p1
        rot = d.normalized().to_track_quat('Z', 'Y').to_matrix().to_4x4()
        m = Matrix.Translation((p1 + p2) / 2) @ rot
        n0 = self._begin()
        bmesh.ops.create_cone(self.bm, cap_ends=True, cap_tris=False, segments=seg,
                              radius1=r, radius2=r if r2 is None else r2,
                              depth=d.length, matrix=m)
        self._end(n0, mat, smooth)

    def box(self, center, size, mat, rot=None):
        m = Matrix.Translation(Vector(center))
        if rot is not None:
            m = m @ rot
        m = m @ Matrix.Diagonal((*size, 1.0))
        n0 = self._begin()
        bmesh.ops.create_cube(self.bm, size=1.0, matrix=m)
        self._end(n0, mat, False)

    def ellipsoid(self, center, size, mat):
        m = Matrix.Translation(Vector(center)) @ Matrix.Diagonal((*size, 1.0))
        n0 = self._begin()
        bmesh.ops.create_uvsphere(self.bm, u_segments=32, v_segments=16, radius=1.0, matrix=m)
        self._end(n0, mat, True)

    def torus(self, center, R, r, mat, seg_u=96, seg_v=14):
        """Toro en el plano XZ (eje = Y), como una rueda vista de costado."""
        c = Vector(center)
        n0 = self._begin()
        rows = []
        for i in range(seg_u):
            a = 2 * math.pi * i / seg_u
            radial = Vector((math.cos(a), 0, math.sin(a)))
            ring = []
            for j in range(seg_v):
                b = 2 * math.pi * j / seg_v
                p = c + radial * (R + r * math.cos(b)) + Vector((0, r * math.sin(b), 0))
                ring.append(self.bm.verts.new(p))
            rows.append(ring)
        for i in range(seg_u):
            for j in range(seg_v):
                i2, j2 = (i + 1) % seg_u, (j + 1) % seg_v
                self.bm.faces.new((rows[i][j], rows[i][j2], rows[i2][j2], rows[i2][j]))
        self._end(n0, mat, True)

    def sweep_loop(self, pts, r, mat, seg_v=6):
        """Tubo cerrado que recorre una polilínea en el plano XZ (para la cadena)."""
        n0 = self._begin()
        rows = []
        n = len(pts)
        Y = Vector((0, 1, 0))
        for i, p in enumerate(pts):
            t = (pts[(i + 1) % n] - pts[i - 1]).normalized()
            nrm = t.cross(Y).normalized()
            ring = []
            for j in range(seg_v):
                b = 2 * math.pi * j / seg_v
                ring.append(self.bm.verts.new(p + nrm * (r * math.cos(b)) + Y * (r * 1.6 * math.sin(b))))
            rows.append(ring)
        for i in range(n):
            for j in range(seg_v):
                i2, j2 = (i + 1) % n, (j + 1) % seg_v
                self.bm.faces.new((rows[i][j], rows[i][j2], rows[i2][j2], rows[i2][j]))
        self._end(n0, mat, True)

    def gear(self, center, R, teeth, depth, mat):
        """Disco dentado con eje en Y (plato / piñón)."""
        c = Vector(center)
        self.tube(c - Vector((0, depth / 2, 0)), c + Vector((0, depth / 2, 0)), R, mat, seg=48, smooth=False)
        tooth = 2 * math.pi * R / teeth * 0.45
        for i in range(teeth):
            a = 2 * math.pi * i / teeth
            rot = Matrix.Rotation(-a, 4, 'Y')
            pos = c + Vector((math.cos(a), 0, math.sin(a))) * (R + tooth * 0.4)
            self.box(pos, (tooth * 0.9, depth, tooth), mat, rot=rot)

    def build(self):
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces[:])
        # origen en el centro de la caja envolvente → ancla para etiquetas en la web
        lo = Vector((min(v.co[i] for v in self.bm.verts) for i in range(3)))
        hi = Vector((max(v.co[i] for v in self.bm.verts) for i in range(3)))
        center = (lo + hi) / 2
        bmesh.ops.translate(self.bm, verts=self.bm.verts[:], vec=-center)
        me = bpy.data.meshes.new(PREFIX + self.name)
        self.bm.to_mesh(me)
        self.bm.free()
        for m in self.mats:
            me.materials.append(m)
        obj = bpy.data.objects.new(PREFIX + self.name, me)
        obj.location = center
        bpy.context.scene.collection.objects.link(obj)
        return obj


# ============ partes ============
def build_frame(M):
    p = Part("Cuadro")
    paint = M["paint"]
    p.tube(BB, SEAT_TOP, 0.019, paint)                                  # tubo de asiento
    p.tube(SEAT_TOP + Vector((0.01, 0, -0.03)), HEAD_TOP + Vector((0.005, 0, -0.025)), 0.017, paint)  # tubo superior
    p.tube(BB, HEAD_BOT + Vector((-0.005, 0, 0.02)), 0.022, paint)      # tubo inferior
    p.tube(HEAD_TOP, HEAD_BOT, 0.024, paint)                            # tubo de dirección
    for s in (-1, 1):
        ax = REAR_AXLE + Vector((0, 0.065 * s, 0))
        p.tube(BB + Vector((0, 0.04 * s, 0)), ax, 0.011, paint)         # vainas
        p.tube(SEAT_TOP + Vector((0.005, 0.03 * s, -0.05)), ax, 0.009, paint)  # tirantes
        p.box(ax, (0.035, 0.008, 0.03), M["dark"])                      # punteras
    p.tube(BB + Vector((0, -0.045, 0)), BB + Vector((0, 0.045, 0)), 0.024, M["dark"])  # caja pedalera
    return p.build()


def build_fork(M):
    p = Part("Horquilla")
    crown = HEAD_BOT + Vector((0.004, 0, -0.02))
    p.box(crown, (0.045, 0.13, 0.03), M["paint"])
    p.tube(HEAD_BOT, HEAD_TOP + Vector((0, 0, 0.02)), 0.014, M["metal"])  # tubo de dirección (steerer)
    for s in (-1, 1):
        top = crown + Vector((0, 0.05 * s, 0))
        mid = top.lerp(FRONT_AXLE + Vector((0, 0.05 * s, 0)), 0.6) + Vector((0.01, 0, 0))
        p.tube(top, mid, 0.013, M["paint"], r2=0.011)
        p.tube(mid, FRONT_AXLE + Vector((0, 0.05 * s, 0)), 0.011, M["paint"], r2=0.009)
    return p.build()


def build_wheel(M, name, axle):
    p = Part(name)
    rim_r = WHEEL_R - TIRE_R * 2 + 0.006
    p.torus(axle, WHEEL_R - TIRE_R, TIRE_R, M["rubber"])                 # cubierta
    p.torus(axle, rim_r, 0.011, M["metal"], seg_v=10)                   # llanta
    p.tube(axle + Vector((0, -0.055, 0)), axle + Vector((0, 0.055, 0)), 0.006, M["metal"], seg=10)  # eje
    p.tube(axle + Vector((0, -0.04, 0)), axle + Vector((0, 0.04, 0)), 0.017, M["metal"])  # maza
    for i in range(SPOKES):
        a = 2 * math.pi * i / SPOKES
        side = 1 if i % 2 == 0 else -1
        hub = axle + Vector((math.cos(a + 0.35 * side) * 0.022, 0.032 * side, math.sin(a + 0.35 * side) * 0.022))
        rim = axle + Vector((math.cos(a), 0, math.sin(a))) * (rim_r - 0.008)
        p.tube(hub, rim, 0.0018, M["metal"], seg=6)
    return p.build()


def build_handlebar(M):
    p = Part("Manubrio")
    stem_top = HEAD_TOP + Vector((0.0, 0, 0.07))
    bar_c = stem_top + Vector((0.07, 0, 0.01))
    p.tube(HEAD_TOP + Vector((0, 0, 0.005)), stem_top, 0.017, M["dark"])   # potencia (vertical)
    p.tube(stem_top, bar_c, 0.015, M["dark"])                            # potencia (avance)
    for s in (-1, 1):
        mid = bar_c + Vector((0, 0.10 * s, 0.0))
        end = bar_c + Vector((-0.04, 0.26 * s, 0.02))
        p.tube(bar_c, mid, 0.012, M["metal"])
        p.tube(mid, end, 0.011, M["metal"])
        g0 = mid.lerp(end, 0.45)
        p.tube(g0, end + (end - mid).normalized() * 0.01, 0.017, M["rubber"])  # puños
        lever = mid.lerp(end, 0.38) + Vector((0.05, 0, -0.01))
        p.tube(mid.lerp(end, 0.38), lever, 0.006, M["dark"], seg=8)          # manetas de freno
    return p.build()


def build_saddle(M):
    p = Part("Asiento")
    d = (SEAT_TOP - BB).normalized()
    post_top = SEAT_TOP + d * 0.11
    p.tube(SEAT_TOP - d * 0.06, post_top, 0.0135, M["metal"])           # tija
    p.box(post_top + Vector((0, 0, 0.012)), (0.05, 0.03, 0.018), M["dark"])  # abrazadera
    seat = post_top + Vector((-0.01, 0, 0.035))
    p.ellipsoid(seat, (0.08, 0.07, 0.025), M["saddle"])                  # cola
    p.ellipsoid(seat + Vector((0.09, 0, 0.002)), (0.09, 0.028, 0.02), M["saddle"])  # punta
    return p.build()


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


def build_drivetrain(M):
    p = Part("Transmision")
    dark, metal = M["dark"], M["metal"]
    ring_r, cog_r = 0.095, 0.042
    p.gear(BB + Vector((0, CHAIN_Y, 0)), ring_r, 40, 0.006, metal)       # plato
    p.gear(REAR_AXLE + Vector((0, CHAIN_Y, 0)), cog_r, 16, 0.006, metal)  # piñón
    p.tube(BB + Vector((0, -0.09, 0)), BB + Vector((0, 0.09, 0)), 0.009, metal, seg=12)  # eje
    # cadena: envolvente convexa de los dos engranajes
    samples = []
    for c, r in ((BB, ring_r + 0.008), (REAR_AXLE, cog_r + 0.008)):
        for i in range(48):
            a = 2 * math.pi * i / 48
            samples.append((round(c.x + r * math.cos(a), 6), round(c.z + r * math.sin(a), 6)))
    hull = hull2d(samples)
    path = []
    for i, (x, z) in enumerate(hull):   # subdividir los tramos rectos
        x2, z2 = hull[(i + 1) % len(hull)]
        steps = max(1, int(math.hypot(x2 - x, z2 - z) / 0.02))
        for k in range(steps):
            t = k / steps
            path.append(Vector((x + (x2 - x) * t, CHAIN_Y, z + (z2 - z) * t)))
    p.sweep_loop(path, 0.0045, dark)
    # bielas y pedales (opuestos)
    crank_a = math.radians(-35)
    for s, a in ((1, crank_a), (-1, crank_a + math.pi)):
        y = 0.09 * s
        tip = BB + Vector((math.cos(a) * 0.17, y, math.sin(a) * 0.17))
        p.tube(BB + Vector((0, y, 0)), tip, 0.011, dark)
        p.box(tip + Vector((0, 0.05 * s, 0)), (0.07, 0.085, 0.018), dark)
        p.tube(tip, tip + Vector((0, 0.01 * s, 0)), 0.012, metal)
    return p.build()


# ============ animación ============
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
        for f, loc, rot in ((F_START, base, 0.0), (f0, base, 0.0),
                            (f1, base + Vector(EXPLODE[key]), 1.0), (F_END, base + Vector(EXPLODE[key]), 1.0)):
            obj.location = loc
            obj.keyframe_insert("location", frame=f)
            if spin:
                # gira como si rodara: sentido según hacia dónde se desplaza en X
                # (+Y en Blender lleva la parte de arriba de la rueda hacia +X)
                roll = math.copysign(1.0, EXPLODE[key][0])
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
    M = {
        "paint": make_mat("Pintura", *MATERIALS["paint"]),
        "metal": make_mat("Metal", *MATERIALS["metal"]),
        "dark": make_mat("MetalOscuro", *MATERIALS["dark"]),
        "rubber": make_mat("Goma", *MATERIALS["rubber"]),
        "saddle": make_mat("Cuero", *MATERIALS["saddle"]),
    }
    parts = {
        "Cuadro": build_frame(M),
        "Horquilla": build_fork(M),
        "Rueda_Trasera": build_wheel(M, "Rueda_Trasera", REAR_AXLE),
        "Rueda_Delantera": build_wheel(M, "Rueda_Delantera", FRONT_AXLE),
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
