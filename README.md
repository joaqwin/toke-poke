# Toke-Poke

Widget flotante para Windows 10 y 11 que rastrea los tokens que consumes con **Claude Code**
y hace evolucionar a tu Pokémon de Kanto en tiempo real.

<img src="assets/icon/pokeball.png" width="96" alt="Icono de Toke-Poke">

## Instalar

Descarga `TokePoke-Setup-1.0.0.exe` desde `dist/installer/` y ejecútalo. Se instala por
usuario en `%LOCALAPPDATA%\Programs\Toke-Poke`, sin pedir permisos de administrador, y crea
accesos directos en el menú de inicio y (opcional) en el escritorio. El instalador ofrece
además arrancar la app al encender Windows.

Tus datos viven aparte, en `%LOCALAPPDATA%\TokePoke` (`state.json` y los sprites), así que
desinstalar o actualizar no borra tu progreso.

## Ejecutar desde el código

```bash
pip install -r requirements.txt
python main.py
```

En el primer arranque eliges un inicial (Bulbasaur, Charmander, Squirtle o Pikachu).
Desde entonces cada respuesta de Claude Code suma tokens (entrada + salida + caché) y,
al alcanzar el umbral de nivel de la especie, tu Pokémon evoluciona con un destello.

- **Arrastrar**: clic izquierdo y mover.
- **Menú**: botón `⋯`, clic derecho o icono de la bandeja del sistema.
- **Cerrar**: botón `✕`.

## Compilar el ejecutable y el instalador

```powershell
pip install -r requirements-dev.txt
winget install JRSoftware.InnoSetup
powershell -ExecutionPolicy Bypass -File build.ps1
```

Genera `dist\TokePoke\TokePoke.exe` (unos 70 MB, sin dependencias externas) y
`dist\installer\TokePoke-Setup-1.0.0.exe` (unos 22 MB).

### Antivirus: falso positivo

Avast, AVG y similares suelen avisar sobre ejecutables recién compilados con PyInstaller.
No es una detección de malware concreto, sino un análisis heurístico de binarios sin firma
digital y desconocidos para el antivirus, y cada recompilación genera un binario nuevo.

El proyecto ya aplica lo que reduce esos avisos: empaquetado en carpeta en lugar de archivo
único (un `--onefile` se autoextrae en `%TEMP%`, que es justo el patrón que dispara alarmas),
sin compresión UPX y con metadatos de versión completos en el ejecutable.

Si Avast sigue avisando mientras desarrollas, añade una exclusión para la carpeta del
proyecto desde su propia interfaz: **Menú > Configuración > General > Excepciones**. Conviene
que lo hagas tú, porque es una opción de seguridad de tu equipo. La solución definitiva es
firmar el ejecutable con un certificado de firma de código, que es de pago.

## Cómo funciona

| Archivo | Rol |
| --- | --- |
| `tracker.py` | Lee de forma incremental los transcripts `*.jsonl` de `%USERPROFILE%\.claude\projects` en un `QThread` y emite los tokens nuevos. Deduplica por `message.id` y solo cuenta líneas completas. |
| `pokemon_manager.py` | Nombres y cadenas evolutivas de los 151 Pokémon de Kanto, umbrales por nivel, descarga de sprites a `assets/pokemon/{id}.png` y persistencia en `state.json`. |
| `gui.py` | Widget frameless en modo oscuro: sprite, nivel, barra animada, contadores de sesión y total, menú de inicial, animación de evolución. |
| `main.py` | Punto de entrada. Detecta si corre empaquetado para elegir dónde guardar los datos. |
| `make_icon.py` | Dibuja el icono de Pokébola y genera el `.ico` multi-tamaño. |
| `toke_poke.spec`, `installer.iss`, `build.ps1` | Empaquetado con PyInstaller e instalador con Inno Setup. |
| `test_simulation.py` | Simulación end-to-end con un transcript ficticio. |

### Umbrales

`state.json` guarda `tokens_per_level` (por defecto `100000`). Un Pokémon que en los juegos
evoluciona al nivel 16 lo hace aquí a `16 × tokens_per_level` tokens de XP. Las evoluciones
por piedra o intercambio usan un nivel equivalente (30-36). Eevee elige al azar entre
Vaporeon, Jolteon y Flareon.

El total histórico de tokens se muestra en **Total**; la XP empieza en 0 al elegir el inicial.

### Sprites

Se descargan bajo demanda desde la CDN de PokeAPI. Si Python no puede validar el certificado
(habitual en Windows con antivirus o proxies), se usa el almacén de certificados del sistema
vía `truststore` y, como último recurso, `curl.exe`.

### Consumo de recursos

Medido en reposo sobre Windows 10 con la app corriendo: **0,3 %** de CPU y unos **70 MB** de
RAM (casi todo el runtime de Qt). El sondeo cada 2 segundos solo consulta tamaño y fecha de
cada transcript, y lee únicamente los bytes nuevos desde el último offset.

## Pruebas

```bash
python test_simulation.py
```

Añade `--visible` para ver el widget durante la simulación. El script crea sus propios
archivos temporales y los borra al terminar.

## Licencia

MIT. Los sprites pertenecen a Nintendo / Game Freak / The Pokémon Company y se descargan
desde el repositorio público de PokeAPI; este proyecto no los redistribuye con fines
comerciales.
