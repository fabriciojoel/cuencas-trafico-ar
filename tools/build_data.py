"""Arma la red vial argentina para CuencasTrafico-AR a partir de un .osm.pbf de Geofabrik.

Salida: tools/out/roaddata.b64 (gzip + base64 en el formato que lee index.html)
y la inyecta en index.html (entre <script id="roaddata"> y </script>).

Uso:  python -I tools/build_data.py _datos/argentina-latest.osm.pbf
"""
import sys, os, json, math, re, gzip, base64, struct, unicodedata, time
from array import array
import numpy as np
import osmium
import shapely
from shapely import wkb as swkb
from scipy.spatial import cKDTree

T0 = time.time()
def log(*a):
    print(f"[{time.time() - T0:6.1f}s]", *a, flush=True)

PBF = sys.argv[1]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "tools", "out")
os.makedirs(OUT, exist_ok=True)

# ---------- proyección: Albers equivalente para Argentina (debe coincidir con albers() en index.html)
R_E, D = 6371.0, math.pi / 180
P1, P2, P0, L0 = -30 * D, -46 * D, -38 * D, -64 * D
NN = (math.sin(P1) + math.sin(P2)) / 2
CC = math.cos(P1) ** 2 + 2 * NN * math.sin(P1)
RHO0 = R_E * math.sqrt(CC - 2 * NN * math.sin(P0)) / NN

def albers_np(lon, lat):
    lon = np.asarray(lon, dtype=np.float64); lat = np.asarray(lat, dtype=np.float64)
    th = NN * (lon * D - L0)
    rho = R_E * np.sqrt(CC - 2 * NN * np.sin(lat * D)) / NN
    return rho * np.sin(th), RHO0 - rho * np.cos(th)

def hav_km(lon1, lat1, lon2, lat2):
    p1, p2 = lat1 * D, lat2 * D
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin((lon2 - lon1) * D / 2) ** 2
    return 2 * R_E * np.arcsin(np.sqrt(a))

# ---------- provincias (código corto, nombre, población censo 2022 INDEC)
PROVS = [
    ("CABA", "Ciudad de Buenos Aires", 3121707, ["ciudad autonoma de buenos aires", "ciudad de buenos aires"]),
    ("BA", "Buenos Aires", 17523996, ["buenos aires"]),
    ("CAT", "Catamarca", 429562, ["catamarca"]),
    ("CHA", "Chaco", 1129606, ["chaco"]),
    ("CHU", "Chubut", 592621, ["chubut"]),
    ("CBA", "Córdoba", 3840905, ["cordoba"]),
    ("COR", "Corrientes", 1212696, ["corrientes"]),
    ("ER", "Entre Ríos", 1425578, ["entre rios"]),
    ("FOR", "Formosa", 607419, ["formosa"]),
    ("JUJ", "Jujuy", 811611, ["jujuy"]),
    ("LP", "La Pampa", 361859, ["la pampa"]),
    ("LR", "La Rioja", 384607, ["la rioja"]),
    ("MZA", "Mendoza", 2043540, ["mendoza"]),
    ("MIS", "Misiones", 1278873, ["misiones"]),
    ("NQN", "Neuquén", 710814, ["neuquen"]),
    ("RN", "Río Negro", 762067, ["rio negro"]),
    ("SAL", "Salta", 1440672, ["salta"]),
    ("SJ", "San Juan", 822853, ["san juan"]),
    ("SL", "San Luis", 542069, ["san luis"]),
    ("SC", "Santa Cruz", 337226, ["santa cruz"]),
    ("SF", "Santa Fe", 3556522, ["santa fe"]),
    ("SDE", "Santiago del Estero", 1060906, ["santiago del estero"]),
    ("TDF", "Tierra del Fuego", 185732, ["tierra del fuego"]),
    ("TUC", "Tucumán", 1731820, ["tucuman"]),
]

def plain(s):
    return unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().lower().strip()

def prov_index(osm_name):
    p = plain(osm_name)
    p = re.sub(r"^provincia (de |del )?", "", p)
    # más específico primero: CABA antes que Buenos Aires
    for i, (_, _, _, keys) in enumerate(PROVS):
        for k in keys:
            if p == k or p.startswith(k + ",") or p.startswith(k + " ("):
                return i
    for i, (_, _, _, keys) in enumerate(PROVS):
        for k in keys:
            if k in p:
                return i
    return -1

# ---------- clases de vía y velocidades (km/h)
KEEP = {"motorway": 1, "trunk": 2, "primary": 3, "secondary": 4, "tertiary": 5,
        "motorway_link": 6, "trunk_link": 6, "primary_link": 6, "secondary_link": 6, "tertiary_link": 6}
UNPAVED = {"unpaved", "gravel", "dirt", "ground", "compacted", "fine_gravel", "earth", "sand", "mud", "grass", "pebblestone"}

def speed_of(hw, tags):
    oneway = tags.get("oneway") in ("yes", "1", "true")
    base = {"motorway": 120, "trunk": 110 if oneway else 100, "primary": 95, "secondary": 80, "tertiary": 65}.get(hw, 50)
    surf = tags.get("surface", "")
    if surf in UNPAVED:
        base = min(base, 60 if hw in ("trunk", "primary", "secondary") else 50)
    ms = tags.get("maxspeed", "")
    m = re.match(r"^\s*(\d{2,3})\s*$", ms)
    if m:
        v = int(m.group(1))
        if 20 <= v <= 130:
            base = min(v, base + 20)
    return base

def clean_ref(ref, name):
    r = (ref or "").split(";")[0].strip()
    if r:
        r = re.sub(r"^(Ruta\s+Nacional|R\.?\s*N\.?)\s*(N[°º]?\s*)?", "RN ", r, flags=re.I)
        r = re.sub(r"^(Ruta\s+Provincial|R\.?\s*P\.?)\s*(N[°º]?\s*)?", "RP ", r, flags=re.I)
        r = re.sub(r"^(RN|RP|AU|AP)\s*-?\s*(\d)", r"\1 \2", r)
        r = re.sub(r"\s+", " ", r).strip()
        return r
    n = (name or "").strip()
    m = re.match(r"^Ruta\s+Nacional\s+(N[°º]?\s*)?(\w+)", n, flags=re.I)
    if m: return "RN " + m.group(2)
    m = re.match(r"^Ruta\s+Provincial\s+(N[°º]?\s*)?(\w+)", n, flags=re.I)
    if m: return "RP " + m.group(2)
    return n[:60]

# ---------- pasada 1: vías, lugares
class H(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.wnodes = []; self.wlon = []; self.wlat = []; self.wmeta = []
        self.places = []
    def node(self, n):
        pl = n.tags.get("place")
        if pl in ("city", "town", "village", "hamlet") and n.tags.get("name"):
            pop = n.tags.get("population", "")
            try: pop = int(re.sub(r"[^\d]", "", pop)) if pop else 0
            except ValueError: pop = 0
            self.places.append((n.tags.get("name"), pl, pop, n.location.lon, n.location.lat, n.tags.get("capital", "")))
    def way(self, w):
        hw = w.tags.get("highway")
        if hw not in KEEP: return
        if w.tags.get("access") in ("private", "no"): return
        ids = array("q"); lo = array("d"); la = array("d")
        for nd in w.nodes:
            if not nd.location.valid(): continue
            ids.append(nd.ref); lo.append(nd.location.lon); la.append(nd.location.lat)
        if len(ids) < 2: return
        tags = {k: w.tags.get(k) for k in ("oneway", "surface", "maxspeed") if w.tags.get(k)}
        self.wnodes.append(ids); self.wlon.append(lo); self.wlat.append(la)
        self.wmeta.append((KEEP[hw], speed_of(hw, tags), clean_ref(w.tags.get("ref"), w.tags.get("name")), hw, tags.get("oneway") in ("yes", "1", "true")))

log("pasada 1: vías y lugares…")
h = H()
h.apply_file(PBF, locations=True, idx="flex_mem")
log(f"  {len(h.wnodes)} vías, {len(h.places)} lugares")

# ---------- pasada 2: provincias (admin_level=4)
log("pasada 2: límites provinciales…")
prov_geom = [None] * len(PROVS)
fab = osmium.geom.WKBFactory()
fp = osmium.FileProcessor(PBF).with_areas(osmium.filter.TagFilter(("admin_level", "4"))).with_filter(osmium.filter.EntityFilter(osmium.osm.AREA))
for a in fp:
    if a.tags.get("boundary") != "administrative" or a.tags.get("admin_level") != "4": continue
    i = prov_index(a.tags.get("name", ""))
    if i < 0:
        log("  ignorada:", a.tags.get("name")); continue
    try:
        g = swkb.loads(fab.create_multipolygon(a), hex=True)
    except Exception as e:
        log("  error", a.tags.get("name"), e); continue
    prov_geom[i] = g if prov_geom[i] is None else prov_geom[i].union(g)
missing = [PROVS[i][1] for i, g in enumerate(prov_geom) if g is None]
if missing: raise SystemExit(f"faltan provincias: {missing}")

def project_geom(g):
    return shapely.transform(g, lambda c: np.column_stack(albers_np(c[:, 0], c[:, 1])))

prov_xy = [shapely.make_valid(project_geom(g)).simplify(0.2) for g in prov_geom]
# Antártida y Malvinas fuera: quedarse con lo que cae al norte de 56°S y al oeste de 60°O en TDF
tdf = prov_xy[[p[0] for p in PROVS].index("TDF")]
bx0, by0 = albers_np(-69.5, -56.0); bx1, by1 = albers_np(-63.0, -52.3)
prov_xy[[p[0] for p in PROVS].index("TDF")] = tdf.intersection(shapely.box(min(bx0, bx1) - 200, by0, max(bx0, bx1), by1 + 50))
country = shapely.union_all(prov_xy)
shapely.prepare(country)
for g in prov_xy: shapely.prepare(g)
log(f"  superficie país (proyectada): {country.area:,.0f} km²")

# ---------- recorte al país y detección de cruces
log("recortando y armando el grafo…")
country_buf = country.buffer(1.0); shapely.prepare(country_buf)
pieces = []  # (ids, lon, lat, meta)
for ids, lo, la, meta in zip(h.wnodes, h.wlon, h.wlat, h.wmeta):
    lo_a = np.frombuffer(lo, dtype=np.float64); la_a = np.frombuffer(la, dtype=np.float64)
    x, y = albers_np(lo_a, la_a)
    inside = shapely.contains_xy(country_buf, x, y)
    if inside.all():
        pieces.append((np.frombuffer(ids, dtype=np.int64), lo_a, la_a, x, y, meta)); continue
    if not inside.any(): continue
    idx = np.flatnonzero(inside)
    splits = np.split(idx, np.flatnonzero(np.diff(idx) != 1) + 1)
    ida = np.frombuffer(ids, dtype=np.int64)
    for s in splits:
        if len(s) >= 2: pieces.append((ida[s], lo_a[s], la_a[s], x[s], y[s], meta))
del h.wnodes, h.wlon, h.wlat
log(f"  {len(pieces)} tramos dentro del país")

allids = np.concatenate([p[0] for p in pieces])
uniq, counts = np.unique(allids, return_counts=True)
shared = set(uniq[counts >= 2].tolist())
jid = {}  # osm node id -> junction index
JLON, JLAT, JXp, JYp = [], [], [], []
def junction(nid, lon, lat, x, y):
    j = jid.get(nid)
    if j is None:
        j = len(JLON); jid[nid] = j; JLON.append(lon); JLAT.append(lat); JXp.append(x); JYp.append(y)
    return j

L_u, L_v, L_km, L_min, L_name, L_cls, L_geom = [], [], [], [], [], [], []
names = {"": 0}
for ids, lo, la, x, y, (cls, spd, nm, hw, oneway) in pieces:
    n = len(ids)
    isj = np.fromiter((i == 0 or i == n - 1 or int(ids[i]) in shared for i in range(n)), dtype=bool, count=n)
    jpos = np.flatnonzero(isj)
    seg = hav_km(lo[:-1], la[:-1], lo[1:], la[1:])
    cum = np.concatenate([[0], np.cumsum(seg)])
    ni = names.setdefault(nm, len(names))
    lc = 1 if cls == 1 else 2 if (cls == 2 and oneway) else 0  # 1 autopista, 2 autovía (troncal de doble mano)
    for a, b in zip(jpos[:-1], jpos[1:]):
        u = junction(int(ids[a]), lo[a], la[a], x[a], y[a]); v = junction(int(ids[b]), lo[b], la[b], x[b], y[b])
        if u == v: continue
        km = float(cum[b] - cum[a])
        L_u.append(u); L_v.append(v); L_km.append(max(km, 0.001)); L_min.append(max(km, 0.001) / spd * 60)
        L_name.append(ni); L_cls.append(lc); L_geom.append(np.column_stack([x[a:b + 1], y[a:b + 1]]))
log(f"  {len(JLON)} cruces, {len(L_u)} tramos")

JXp = np.array(JXp); JYp = np.array(JYp); JLON = np.array(JLON); JLAT = np.array(JLAT)

# ---------- enlace sintético a Tierra del Fuego (la RN 3 cruza por Chile y el estrecho de Magallanes)
tree0 = cKDTree(np.column_stack([JXp, JYp]))
def near(lon, lat):
    x, y = albers_np(lon, lat); return int(tree0.query([float(x), float(y)])[1])
a_j = near(-69.555, -52.163)   # paso Integración Austral (Monte Aymond)
b_j = near(-68.585, -53.300)   # paso San Sebastián
km = 270.0
L_u.append(a_j); L_v.append(b_j); L_km.append(km); L_min.append(330.0)  # incluye cruce en balsa y aduanas
L_name.append(names.setdefault("Ruta 257-CH y balsa (por Chile)", len(names))); L_cls.append(0)
L_geom.append(np.array([[JXp[a_j], JYp[a_j]], list(albers_np(-69.35, -52.45)), list(albers_np(-69.45, -52.55)), list(albers_np(-69.0, -52.95)), [JXp[b_j], JYp[b_j]]], dtype=np.float64))

# ---------- componente conexa mayor
NJ0, NL0 = len(JLON), len(L_u)
par = np.arange(NJ0)
def find(i):
    while par[i] != i:
        par[i] = par[par[i]]; i = par[i]
    return i
for u, v in zip(L_u, L_v):
    ru, rv = find(u), find(v)
    if ru != rv: par[ru] = rv
roots = np.array([find(i) for i in range(NJ0)])
big = np.bincount(roots).argmax()
keepj = roots == big
log(f"  componente mayor: {keepj.sum()} de {NJ0} cruces")
newj = -np.ones(NJ0, dtype=np.int64); newj[keepj] = np.arange(keepj.sum())
keepl = [i for i in range(NL0) if keepj[L_u[i]]]

JXp, JYp, JLON, JLAT = JXp[keepj], JYp[keepj], JLON[keepj], JLAT[keepj]
NJ = len(JXp)
lu = np.array([newj[L_u[i]] for i in keepl], dtype=np.uint32)
lv = np.array([newj[L_v[i]] for i in keepl], dtype=np.uint32)
lk = np.array([L_km[i] for i in keepl], dtype=np.float32)
lt = np.array([L_min[i] for i in keepl], dtype=np.float32)
lname = np.array([L_name[i] for i in keepl], dtype=np.uint16)
lcls = np.array([L_cls[i] for i in keepl], dtype=np.uint8)
geoms = [L_geom[i] for i in keepl]
NL = len(keepl)

# ---------- simplificación de geometría
log("simplificando geometría…")
ls = shapely.simplify(np.array([shapely.LineString(g) for g in geoms], dtype=object), 0.045)
geoms = [np.asarray(shapely.get_coordinates(g)) for g in ls]
for i, g in enumerate(geoms):  # extremos exactos sobre los cruces
    g[0] = (JXp[lu[i]], JYp[lu[i]]); g[-1] = (JXp[lv[i]], JYp[lv[i]])

# ---------- provincia de cada cruce
jstate = np.full(NJ, 255, dtype=np.uint8)
for i, g in enumerate(prov_xy):
    m = shapely.contains_xy(g, JXp, JYp) & (jstate == 255)
    jstate[m] = i
if (jstate == 255).any():
    rest = np.flatnonzero(jstate == 255)
    pts = shapely.points(JXp[rest], JYp[rest])
    for k, p in zip(rest, pts):
        jstate[k] = int(np.argmin([g.distance(p) for g in prov_xy]))
log("  cruces por provincia:", {PROVS[i][0]: int((jstate == i).sum()) for i in range(len(PROVS))})

# ---------- superficie por cruce (grilla de 2 km)
log("superficie por cruce…")
tree = cKDTree(np.column_stack([JXp, JYp]))
G = 2.0
minx, miny, maxx, maxy = country.bounds
gx, gy = np.meshgrid(np.arange(minx + G / 2, maxx, G), np.arange(miny + G / 2, maxy, G))
gx = gx.ravel(); gy = gy.ravel()
ins = shapely.contains_xy(country, gx, gy)
gx, gy = gx[ins], gy[ins]
_, nearest = tree.query(np.column_stack([gx, gy]), workers=-1)
jarea = np.bincount(nearest, minlength=NJ).astype(np.float32) * G * G
log(f"  superficie total {jarea.sum():,.0f} km²")

# ---------- población por cruce (lugares de OSM escalados al censo 2022 por provincia)
log("población por cruce…")
DEF = {"city": 40000, "town": 4000, "village": 400, "hamlet": 60}
pl = h.places
plon = np.array([p[3] for p in pl]); plat = np.array([p[4] for p in pl])
ppx, ppy = albers_np(plon, plat)
pin = shapely.contains_xy(country, ppx, ppy)
pprov = np.full(len(pl), -1)
for i, g in enumerate(prov_xy):
    m = shapely.contains_xy(g, ppx, ppy) & (pprov == -1); pprov[m] = i
rawpop = np.array([p[2] if p[2] > 0 else DEF[p[1]] for p in pl], dtype=np.float64)
popw = np.zeros(len(pl))
for i in range(len(PROVS)):
    m = (pprov == i) & pin
    s = rawpop[m].sum()
    if s > 0: popw[m] = rawpop[m] * PROVS[i][2] / s
_, pj = tree.query(np.column_stack([ppx, ppy]), workers=-1)
jpop = np.zeros(NJ, dtype=np.float64)
np.add.at(jpop, pj[pin], popw[pin])
jpop = jpop.astype(np.float32)
log(f"  población total {jpop.sum():,.0f}")

# ---------- ciudades y pueblos
cities, towns = [], []
seen = set()
order_p = sorted(range(len(pl)), key=lambda i: -(pl[i][2] or DEF[pl[i][1]] / 10))
for i in order_p:
    if not pin[i] or pprov[i] < 0: continue
    name, kind, pop, lon, lat, cap = pl[i]
    key = (plain(name), int(pprov[i]))
    if key in seen: continue
    seen.add(key)
    code = PROVS[pprov[i]][0]
    if kind in ("city", "town") or pop >= 2000:
        cities.append([name, code, int(pop), round(lon, 4), round(lat, 4)])
    if kind != "hamlet":
        towns.append((name, int(pprov[i]), float(ppx[i]), float(ppy[i]), int(pop)))
cities.sort(key=lambda c: -c[2])
log(f"  {len(cities)} ciudades, {len(towns)} localidades")

# ---------- cuantización y empaquetado
Q = 0.06
x0 = float(min(JXp.min(), min(g[:, 0].min() for g in geoms))) - 1
y0 = float(min(JYp.min(), min(g[:, 1].min() for g in geoms))) - 1
x1 = float(max(JXp.max(), max(g[:, 0].max() for g in geoms))) + 1
y1 = float(max(JYp.max(), max(g[:, 1].max() for g in geoms))) + 1
assert (x1 - x0) / Q < 65535 and (y1 - y0) / Q < 65535, "Q demasiado chico"
qx = lambda v: np.rint((np.asarray(v) - x0) / Q).astype(np.int64)
qy = lambda v: np.rint((np.asarray(v) - y0) / Q).astype(np.int64)
jx = qx(JXp).astype(np.uint16); jy = qy(JYp).astype(np.uint16)
gcnt = np.array([len(g) for g in geoms], dtype=np.int64)
assert gcnt.max() < 65535
gsx = np.zeros(NL, dtype=np.uint16); gsy = np.zeros(NL, dtype=np.uint16)
gd = np.zeros(2 * int(gcnt.sum()), dtype=np.int64)
k = 0
for i, g in enumerate(geoms):
    ix, iy = qx(g[:, 0]), qy(g[:, 1])
    gsx[i] = ix[0]; gsy[i] = iy[0]
    dx = np.diff(ix, prepend=ix[0]); dy = np.diff(iy, prepend=iy[0])
    n = len(g)
    gd[2 * k:2 * (k + n):2] = dx; gd[2 * k + 1:2 * (k + n):2] = dy
    k += n
assert np.abs(gd).max() < 32767
gd = gd.astype(np.int16)

name_list = [None] * len(names)
for nm, i in names.items(): name_list[i] = nm

arrays = [("jx", jx), ("jy", jy), ("jstate", jstate), ("jarea", jarea), ("jpop", jpop),
          ("lu", lu), ("lv", lv), ("lt", lt), ("lk", lk), ("lname", lname), ("lcls", lcls),
          ("gcnt", gcnt.astype(np.uint16)), ("gsx", gsx), ("gsy", gsy), ("gd", gd)]
DT = {np.dtype(np.uint16): "uint16", np.dtype(np.int16): "int16", np.dtype(np.uint8): "uint8",
      np.dtype(np.uint32): "uint32", np.dtype(np.float32): "float32"}
meta_arrays, blobs, off = [], [], 0
for nm, a in arrays:
    a = np.ascontiguousarray(a)
    while off % a.dtype.itemsize: blobs.append(b"\0"); off += 1
    meta_arrays.append([nm, DT[a.dtype], off, int(a.size)])
    b = a.tobytes(); blobs.append(b); off += len(b)

tw = towns
M = {"Q": Q, "x0": x0, "y0": y0, "nj": int(NJ), "nl": int(NL), "nv": int(gcnt.sum()),
     "states": [[p[0], p[1]] for p in PROVS], "cities": cities, "names": name_list,
     "bounds": [x0, y0, x1, y1], "arrays": meta_arrays, "outlines": [],
     "towns": {"n": "|".join(t[0].replace("|", "/") for t in tw), "st": [p[0] for p in PROVS],
               "s": [t[1] for t in tw], "x": [round(t[2] * 10) for t in tw], "y": [round(t[3] * 10) for t in tw],
               "p": [t[4] for t in tw]}}
hdr = json.dumps(M, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
buf = struct.pack("<I", len(hdr)) + hdr
while len(buf) % 8: buf += b"\0"
buf += b"".join(blobs)
gz = gzip.compress(buf, 9, mtime=0)
b64 = base64.b64encode(gz).decode("ascii")
open(os.path.join(OUT, "roaddata.b64"), "w").write(b64)
log(f"datos: {len(buf)/1e6:.1f} MB crudos, {len(gz)/1e6:.1f} MB gzip, {len(b64)/1e6:.1f} MB base64")

# ---------- inyectar en index.html
html_path = os.path.join(ROOT, "index.html")
html = open(html_path, encoding="utf-8").read()
start = html.index('<script id="roaddata" type="application/octet-stream">') + len('<script id="roaddata" type="application/octet-stream">')
end = html.index("</script>", start)
html = html[:start] + b64 + html[end:]
open(html_path, "w", encoding="utf-8", newline="\n").write(html)
log("index.html actualizado")
