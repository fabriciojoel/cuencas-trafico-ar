# Todos los caminos llevan a… · Argentina

Adaptación a Argentina de [CuencasTrafico](https://github.com/Ntizar/CuencasTrafico) (David Antizar), que a su vez trae a España el mapa *«All Roads Lead to Richmond»* de [Arterial Mapping](https://arterialmapping.wordpress.com/2022/03/20/all-roads-lead-to-richmond-2/).

Todos los cruces de la red vial argentina se enrutan hacia un solo punto y el mapa dibuja el árbol de rutas más rápidas. El grosor de cada línea es el territorio (o la gente) que arrastra.

Accesos rápidos: **Córdoba, Buenos Aires, Mendoza, Rosario, Salta y Puerto San Julián**. Se puede elegir cualquier otra ciudad del buscador o hacer clic en el mapa.

## Cómo se abre

Es un solo `index.html`, sin servidor: doble clic y se abre en el navegador (Chrome, Edge o Firefox actuales). Los datos viajan comprimidos adentro del propio archivo.

## Los cuatro mapas

| Modo | Qué responde |
|---|---|
| **Un destino** | Si todo el país manejara hacia un mismo punto, ¿qué rutas se llenarían? |
| **Cuencas viales** | Varias ciudades se reparten Argentina: cada punto va a la que llega antes. |
| **Punto de encuentro** | Dónde juntarse para que el que más maneja tarde lo mínimo (o el total sea mínimo). |
| **Efecto autopista** | Cuánto ahorran las autopistas y autovías frente a rutas comunes de 90 km/h. |

## Qué cambió respecto del original español

- **Datos**: red de OpenStreetMap de Argentina (Geofabrik, nov 2026): autopistas, troncales, rutas primarias, secundarias y terciarias con sus ramales. Se recorta al territorio argentino (afuera quedan los tramos chilenos, bolivianos, etc. que trae el extracto).
- **Proyección**: Albers equivalente con paralelos estándar 30° S y 46° S, meridiano central 64° O.
- **Póster vertical** (1200 × 1600, exporta a 3600 × 4800 px), porque el país es alto y angosto.
- **Velocidades** (km/h): autopista 120, autovía 110, troncal 100, primaria 95, secundaria 80, terciaria 65, ramales 50; en ripio o tierra 50–60. Si OSM trae la máxima señalizada, se usa esa (con tope).
- **Tierra del Fuego**: la RN 3 pasa por Chile y cruza el estrecho de Magallanes en balsa. Se modela con un tramo sintético de 270 km y 5 h 30 entre el paso Integración Austral y el paso San Sebastián.
- **Población**: localidades de OSM (con su población cuando la tienen) escaladas al total del censo 2022 de cada provincia. Es aproximado.
- **Superficie**: grilla de 2 km dentro del país; cada celda se asigna al cruce más cercano.
- Textos en castellano rioplatense y nombres de ruta normalizados a `RN 9`, `RP 2`, etc.

## Límites

- Velocidades estimadas: sin tránsito, sin peajes, sin costos de giro, sin estado real del ripio.
- Las rutas son no dirigidas (no se modelan sentidos únicos).
- Sin Malvinas ni Antártida.
- Los porcentajes de las leyendas son orientativos.

## Regenerar los datos

```bash
pip install osmium shapely numpy scipy
curl -L -o _datos/argentina-latest.osm.pbf https://download.geofabrik.de/south-america/argentina-latest.osm.pbf
python -I tools/build_data.py _datos/argentina-latest.osm.pbf
```

El script inyecta los datos nuevos dentro de `index.html`. `tools/patch_ar.py` es el parche que se usó una sola vez para pasar el HTML original de España a Argentina (queda como registro).

## Licencias

- **Código**: MIT — ver [LICENSE](LICENSE) (© David Antizar, autor del original).
- **Datos viales**: © colaboradores de OpenStreetMap, ODbL 1.0.
- **Tipografías**: Overpass / Overpass Mono, SIL OFL.
