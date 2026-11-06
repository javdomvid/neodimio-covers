# neodimio-covers

Portada mensual **YOU CAN'T MISS ‹MES›** para la playlist de Spotify de [@javdomvid](https://github.com/javdomvid).

Parte siempre de la misma imagen (`base.jpg`: caja de miniCD transparente sobre fondo oscuro). Cada mes **solo cambia el arte impreso en el disco**: la caja, el fondo, la tipografía (Oswald 500), el arco "YOU CAN'T MISS", el mes y la firma se quedan donde están. El arte recibe la luz y los brillos de la foto original, así que parece impreso en el CD.

## Uso

```bash
pip install numpy opencv-python-headless pillow     # si faltan
python3 cover.py --candidates 3 --out out            # mes actual (hora de Madrid): 3 propuestas + hoja de contactos
python3 cover.py --month DECEMBER --year 2026 --candidates 3
python3 cover.py --month NOVEMBER --styles sunburst,marble
```

Las tipografías (Google Fonts, licencia OFL) se descargan solas la primera vez.

## Estilos y rotación

Hay 9 estilos de disco: `aura`, `marble`, `sunburst`, `rings`, `halftone`, `checker`, `gradient`, `waves` y `tiedye`. Cada mes tiene sus paletas de temporada (ver `PALETTES`). Cada mes se proponen 3 estilos: la rotación avanza 3 posiciones (mod 9), así que dos meses seguidos nunca comparten estilo.

## Legibilidad

El color del texto se elige midiendo el contraste WCAG en el peor caso (percentiles 5 y 95) del arte que queda debajo:

1. Si negro, blanco o un color de la paleta llega a 4.5:1, se usa ese color sin adornos.
2. Si el arte está muy cargado, se usa relleno más contorno o halo del color opuesto, que es legible por construcción.

El script imprime `legibility.ok` por cada propuesta.

## Subida a Spotify

```bash
python3 upload.py --file out/november_c0.jpg --playlist <id> --creds-from /tmp/sync.py
```

Necesita un refresh token con el permiso `ugc-image-upload`. Las credenciales nunca van en este repo. Las lee de variables de entorno (`SPOTIFY_CID`, `SPOTIFY_CSEC`, `SPOTIFY_RTOK`) o de un script con líneas `CID="…"`, `CSEC="…"` y `RTOK="…"`.
