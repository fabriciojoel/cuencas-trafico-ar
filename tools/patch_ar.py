"""Adapta el index.html del CuencasTrafico original (España) a Argentina. Se corre una sola vez."""
import re, sys
p = sys.argv[1]
h = open(p, encoding="utf-8").read()

def rep(old, new, count=1):
    global h
    n = h.count(old)
    if n != count:
        raise SystemExit(f"esperaba {count} y hay {n}: {old[:80]!r}")
    h = h.replace(old, new)

def rex(pat, new, count=1):
    global h
    h2, n = re.subn(pat, new, h, flags=re.M)
    if n != count:
        raise SystemExit(f"regex esperaba {count} y hay {n}: {pat[:80]!r}")
    h = h2

# ---------- póster vertical (Argentina es alta y angosta)
rep(".poster-wrap { position: relative; width: 100%; aspect-ratio: 16 / 10; max-width: 100%;",
    ".poster-wrap { position: relative; width: min(100%, calc((100vh - 72px) * 0.75)); margin: 0 auto; aspect-ratio: 3 / 4; max-width: 100%;")
rep("const PW = 1600, PH = 1000;", "const PW = 1200, PH = 1600;")
rep("const header = 150, footer = 120, padX = 56;", "const header = 262, footer = 150, padX = 56;")
rep('ctx.font = `600 15px ${FM}`; const reserve = Math.max(520, ctx.measureText(halfLine).width + 60);', "const reserve = 0;")
rep('ctx.font = `600 15px ${FM}`; const reserve = Math.max(520, ...lines.slice(2).map(([t]) => ctx.measureText(t).width + 60));', "const reserve = 0;")
rep('ctx.font = `400 15px ${FM}`; ctx.fillStyle = st.muted; ctx.textAlign = "right";', 'ctx.font = `400 15px ${FM}`; ctx.fillStyle = st.muted; ctx.textAlign = "left";')
rep("ctx.fillText(scopeTxt, PW - padX, 62);", "ctx.fillText(scopeTxt, padX, 166);")
rep("ctx.fillText(wTxt, PW - padX, 86);", "ctx.fillText(wTxt, padX, 190);")
rep("ctx.fillText(halfLine, PW - padX, 112);", "ctx.fillText(halfLine, padX, 218);")
rep("${fmtDur(R.farD)} ${where}`, PW - padX, 134);", "${fmtDur(R.farD)} ${where}`, padX, 242);")
rep('ctx.textAlign = "right";\n  const ys = [62, 86, 112, 134];', 'ctx.textAlign = "left";\n  const ys = [166, 190, 218, 242];')
rep("ctx.fillText(t, PW - padX, ys[i]);", "ctx.fillText(t, padX, ys[i]);")
# notas al pie: en 1200 px de ancho no entran en una línea
rep("function fmtHours(h) {", """function fillWrap(ctx, text, x, yLast, maxW, lh) {
  const words = text.split(" "), lines = []; let cur = "";
  for (const w of words) { const t = cur ? cur + " " + w : w; if (cur && ctx.measureText(t).width > maxW) { lines.push(cur); cur = w; } else cur = t; }
  if (cur) lines.push(cur);
  lines.forEach((l, i) => ctx.fillText(l, x, yLast - (lines.length - 1 - i) * lh));
}
function fmtHours(h) {""")
rex(r'^(\s*)ctx\.fillText\((R\.sheds \? "Cada color.*?), padX, PH - 26\);$', r'\1fillWrap(ctx, \2, padX, PH - 26, PW - 2 * padX, 13);')
rex(r'^(\s*)ctx\.fillText\((`Las líneas gruesas.*?`), padX, PH - 26\);$', r'\1fillWrap(ctx, \2, padX, PH - 26, PW - 2 * padX, 13);')
rex(r'^(\s*)ctx\.fillText\(("Cada carretera se colorea.*?"), padX, PH - 26\);$', r'\1fillWrap(ctx, \2, padX, PH - 26, PW - 2 * padX, 13);')

# ---------- proyección Albers para Argentina, sin desplazamiento de Canarias
rep("  if (lon < -11 && lat < 31.5) { lon += 5.8; lat += 9.2; } // Canarias desplazadas (convención de los mapas de España)\n", "")
rep("p1 = 37 * d, p2 = 43 * d, p0 = 40 * d, l0 = -4 * d;", "p1 = -30 * d, p2 = -46 * d, p0 = -38 * d, l0 = -64 * d;", 2)
rep("  if (lon0 > -13 && lon0 < -7.6 && lat1 > 36.5 && lat1 < 39) { lon0 -= 5.8; lat1 -= 9.2; }\n", "")
rep("°N", "°S", 4)

# ---------- nombres y rango de rutas argentinas; autopistas por clase de vía (A.lcls)
rep('function roadRank(s) { return /^(AP|A|M)- ?\\d/.test(s) ? 3 : /^N- ?\\d/.test(s) ? 1.6 : /^[A-Z]{1,3}- ?\\d/.test(s) ? 1.1 : 1; }',
    'function roadRank(s) { return /^(AU|Autopista|Autovía)/i.test(s) ? 3 : /^RN \\w/.test(s) ? 2.2 : /^RP \\w/.test(s) ? 1.3 : 1; }')
rep('if (!s) return "carreteras locales";', 'if (!s) return "rutas locales";')
rep('function isInterstate(l) { return /^(AP|A|M)- ?\\d/.test(M.names[A.lname[l]] || ""); }', "function isInterstate(l) { return A.lcls[l] > 0; }")
rep("noICost[l] = isInterstate(l) ? A.lk[l] / 80 * 60 : A.lt[l];", "noICost[l] = isInterstate(l) ? A.lk[l] / 90 * 60 : A.lt[l];")
rep("const reachCost = mode === \"dist\" ? S.reach * 60 * 1.609344 : S.reach * 60;", "const reachCost = S.reach * 60;")

# ---------- ciudades: etiqueta con el nombre de la provincia
rep("return { name, st, pop, x, y, label: `${name}, ${st}`, slug: slug(`${name}-${st}`) };",
    "const pn = (M.states.find(s => s[0] === st) || [st, st])[1];\n    const label = st === \"CABA\" || slug(pn) === slug(name) ? name : `${name}, ${pn}`;\n    return { name, st, pop, x, y, label, slug: slug(`${name}-${st}`) };")
rep("if (c) label = `${c.name}, ${c.st}`;", "if (c) label = c.label;")

rep("""const PRESETS = {
  clasicas: [["Madrid", 40.4168, -3.7038], ["Barcelona", 41.3874, 2.1686], ["Valencia", 39.4699, -0.3763], ["Sevilla", 37.3891, -5.9845], ["Bilbao", 43.2630, -2.9350], ["Zaragoza", 41.6488, -0.8891]],
  esquinas: [["A Coruña", 43.3623, -8.4115], ["Girona", 41.9794, 2.8214], ["Cádiz", 36.5271, -6.2886], ["Alicante", 38.3452, -0.4810]],
  costas: [["Santander", 43.4623, -3.8099], ["Vigo", 42.2328, -8.7226], ["Valencia", 39.4699, -0.3763], ["Málaga", 36.7213, -4.4214]],
};""", """const PRESETS = {
  clasicas: [["Córdoba", -31.4201, -64.1888], ["Buenos Aires", -34.6037, -58.3816], ["Mendoza", -32.8895, -68.8458], ["Rosario", -32.9442, -60.6505], ["Salta", -24.7821, -65.4232], ["Puerto San Julián", -49.3067, -67.7275]],
  esquinas: [["La Quiaca", -22.1056, -65.5928], ["Puerto Iguazú", -25.5991, -54.5736], ["Mar del Plata", -38.0055, -57.5426], ["Ushuaia", -54.8019, -68.3030], ["Malargüe", -35.4752, -69.5853]],
  costas: [["Mar del Plata", -38.0055, -57.5426], ["Bahía Blanca", -38.7183, -62.2663], ["Puerto Madryn", -42.7692, -65.0385], ["Comodoro Rivadavia", -45.8641, -67.4966], ["Río Gallegos", -51.6230, -69.2168]],
};""")
rex(r"^const CAPITALS = .*$", 'const CAPITALS = [["Buenos Aires","CABA",-34.6037,-58.3816],["La Plata","BA",-34.9214,-57.9545],["Córdoba","CBA",-31.4201,-64.1888],["Santa Fe","SF",-31.6333,-60.7],["Paraná","ER",-31.7319,-60.5238],["Mendoza","MZA",-32.8895,-68.8458],["San Juan","SJ",-31.5375,-68.5364],["San Luis","SL",-33.3017,-66.3378],["San Miguel de Tucumán","TUC",-26.8083,-65.2176],["Salta","SAL",-24.7821,-65.4232],["San Salvador de Jujuy","JUJ",-24.1858,-65.2995],["Santiago del Estero","SDE",-27.7951,-64.2615],["San Fernando del Valle de Catamarca","CAT",-28.4696,-65.7795],["La Rioja","LR",-29.4131,-66.8558],["Resistencia","CHA",-27.4606,-58.9839],["Corrientes","COR",-27.4692,-58.8306],["Posadas","MIS",-27.3671,-55.8961],["Formosa","FOR",-26.1775,-58.1781],["Santa Rosa","LP",-36.6167,-64.2833],["Neuquén","NQN",-38.9516,-68.0591],["Viedma","RN",-40.8135,-62.9967],["Rawson","CHU",-43.3002,-65.1023],["Río Gallegos","SC",-51.623,-69.2168],["Ushuaia","TDF",-54.8019,-68.303]];')
rex(r"^const QUICK = .*$", 'const QUICK = ["cordoba-cba", "buenos-aires-caba", "mendoza-mza", "rosario-sf", "salta-sal", "puerto-san-julian-sc"];')
rep('cityList.find(c => c.slug === "madrid-m")', 'cityList.find(c => c.slug === "cordoba-cba")')
rep('<button type="button" class="chip" data-preset="clasicas">Clásicas</button>', '<button type="button" class="chip" data-preset="clasicas">Las seis</button>')
rep('<button type="button" class="chip" data-preset="costas">Costas</button>', '<button type="button" class="chip" data-preset="costas">Costa atlántica</button>')
rep('<input id="reach" type="range" min="1" max="12" step="0.5" value="4"', '<input id="reach" type="range" min="1" max="24" step="0.5" value="6"')
rep("reach: 4,", "reach: 6,")

# ---------- textos: España -> Argentina, en castellano rioplatense
TXT = [
    ("<p>Elige un destino, o un grupo de ciudades rivales. Todos los cruces de España enrutan hacia él y el mapa dibuja el árbol de rutas más rápidas. Las líneas más gruesas arrastran más país.</p>",
     "<p>Elegí un destino, o un grupo de ciudades rivales. Todos los cruces de la red vial argentina enrutan hacia él y el mapa dibuja el árbol de rutas más rápidas. Las líneas más gruesas arrastran más país.</p>", 1),
    ('data-v="interstate" aria-pressed="false">Efecto autovía</button>', 'data-v="interstate" aria-pressed="false">Efecto autopista</button>', 1),
    ("Haz clic en el mapa para añadir o quitar ciudades.", "Hacé clic en el mapa para agregar o quitar ciudades.", 1),
    ('placeholder="Añade una ciudad"', 'placeholder="Agregá una ciudad"', 1),
    ("Haz clic en el mapa para añadir o quitar viajeros.", "Hacé clic en el mapa para agregar o quitar viajeros.", 1),
    ('placeholder="Busca entre las ciudades de España"', 'placeholder="Buscá entre las ciudades de Argentina"', 1),
    ("O haz clic en cualquier punto del mapa para enviar todas las rutas allí.", "O hacé clic en cualquier punto del mapa para mandar todas las rutas ahí.", 1),
    ('data-v="us" aria-pressed="true">Toda España</button>', 'data-v="us" aria-pressed="true">Toda Argentina</button>', 1),
    ('<button type="button" class="secondary" id="record">Grabar vídeo</button>', '<button type="button" class="secondary" id="record">Grabar video</button>', 1),
    ("Descomprimiendo la red viaria de España…", "Descomprimiendo la red vial de Argentina…", 1),
    ("desde cualquier punto de España", "desde cualquier punto de Argentina", 2),
    ('"Las rutas más rápidas en coche hasta"', '"Las rutas más rápidas en auto hasta"', 1),
    ('"Cuencas viales por tiempo de conducción de"', '"Cuencas viales por tiempo de manejo de"', 1),
    ('"Cuánto acortan las autovías cada viaje hasta"', '"Cuánto acortan las autopistas cada viaje hasta"', 1),
    ("`Las autovías recortan el viaje medio en", "`Las autopistas y autovías recortan el viaje medio en", 1),
    ('"Tiempo que ahorran las autovías"', '"Tiempo que ahorran las autopistas"', 2),
    ("si las autovías fueran carreteras convencionales de 80 km/h. Carreteras: © OpenStreetMap (ODbL).",
     "si las autopistas y autovías fueran rutas comunes de 90 km/h. Rutas: © OpenStreetMap (ODbL).", 1),
    ('"El lugar con menos conducción total es"', '"El lugar con menos manejo total es"', 1),
    ("`Conducción total: ", "`Manejo total: ", 1),
    ('"Conducción hasta el punto de quedada"', '"Manejo hasta el punto de encuentro"', 2),
    ("si quedarais allí: lo más oscuro está a 15 minutos del mejor punto. Carreteras: © OpenStreetMap (ODbL).",
     "si se juntaran ahí: lo más oscuro está a 15 minutos del mejor punto. Rutas: © OpenStreetMap (ODbL).", 1),
    ('"color de cada carretera: cuánto peor sería quedar allí"', '"color de cada ruta: cuánto peor sería juntarse ahí"', 1),
    ('"grosor ∝ personas cuya ruta usa la carretera" : "grosor ∝ territorio cuya ruta usa la carretera"', '"grosor ∝ personas cuyo camino usa la ruta" : "grosor ∝ territorio cuyo camino usa la ruta"', 2),
    ('"tiempo en coche"', '"tiempo en auto"', 1),
    ('"Vídeo listo. Usa el enlace o guarda el vídeo con clic derecho."', '"Video listo. Usá el enlace o guardá el video con clic derecho."', 1),
    ('"Vídeo grabado"', '"Video grabado"', 1),
    ("Clic derecho o pulsación larga sobre la imagen para guardarla", "Clic derecho o mantené apretada la imagen para guardarla", 2),
    ("one: \"Cada cruce de España enruta hacia un único lugar.\"", "one: \"Cada cruce de Argentina enruta hacia un único lugar.\"", 1),
    ("Encuentra el mejor lugar para quedar en grupo y dibuja la ruta de cada uno.", "Encuentra el mejor lugar para juntarse en grupo y dibuja la ruta de cada uno.", 1),
    ("interstate: \"Colorea cada carretera según el tiempo que las autovías ahorran en el viaje hasta un lugar.\"",
     "interstate: \"Colorea cada ruta según el tiempo que las autopistas y autovías ahorran en el viaje hasta un lugar.\"", 1),
    ("return `efecto-autovia-${slug(S.destLabel)}`;", "return `efecto-autopista-${slug(S.destLabel)}`;", 1),
    ('<button type="button" data-v="total" aria-pressed="false">Mínimo total conduciendo</button>', '<button type="button" data-v="total" aria-pressed="false">Mínimo total manejando</button>', 1),
    ('"Cada cruce de la red de autopistas, autovías y carreteras nacionales, autonómicas y secundarias enruta hacia el punto marcado. Carreteras: © OpenStreetMap (ODbL)."',
     '"Cada cruce de la red de autopistas, rutas nacionales, provinciales y secundarias enruta hacia el punto marcado. Rutas: © OpenStreetMap (ODbL)."', 1),
    ("las líneas muestran el árbol de rutas dentro de cada cuenca. Carreteras: © OpenStreetMap (ODbL), nov 2026.", "las líneas muestran el árbol de rutas dentro de cada cuenca. Rutas: © OpenStreetMap (ODbL), nov 2026.", 1),
    ("con el nombre de la carretera que sigue su tronco. Carreteras: © OpenStreetMap (ODbL), nov 2026.", "con el nombre de la ruta que sigue su tronco. Rutas: © OpenStreetMap (ODbL), nov 2026.", 1),
]
for a, b, n in TXT:
    rep(a, b, n)
rex(r'^const CREDIT = .*$', 'const CREDIT = "Basado en CuencasTrafico de David Antizar (@Ntizar) e inspirado en “All Roads Lead to Richmond” de Arterial Mapping. Datos: © OpenStreetMap (ODbL), nov 2026.";')
rex(r'^      <span>Carreteras: &copy;.*$', '      <span>Rutas: &copy; colaboradores de OpenStreetMap (ODbL), nov 2026: autopistas, rutas nacionales, provinciales y secundarias. Velocidades estimadas por tipo de vía (120/110/95/80/65 km/h, 50–60 en ripio) o la señalizada. Sin tránsito ni costos de giro. Tierra del Fuego se conecta por la ruta chilena y la balsa del estrecho de Magallanes (~5 h 30). Población: localidades de OSM escaladas al censo 2022 por provincia. Adaptación de <a href="https://github.com/Ntizar/CuencasTrafico" target="_blank" rel="noopener">CuencasTrafico</a> (David Antizar), inspirado en <a href="https://arterialmapping.wordpress.com/2022/03/20/all-roads-lead-to-richmond-2/" target="_blank" rel="noopener">&ldquo;All Roads Lead to Richmond&rdquo;</a> de Arterial Mapping.</span>')
rep('<html lang="es">', '<html lang="es-AR">')
open(p, "w", encoding="utf-8", newline="\n").write(h)
print("ok")
