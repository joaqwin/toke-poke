# Toke-Poke

Widget flotante para Windows 10 que rastrea los tokens que consumes con **Claude Code**
y hace evolucionar a tu Pokémon de Kanto en tiempo real.

![modo oscuro, siempre visible, arrastrable](https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/6.png)

## Uso

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

## Cómo funciona

| Archivo | Rol |
| --- | --- |
| `tracker.py` | Lee de forma incremental los transcripts `*.jsonl` de `%USERPROFILE%\.claude\projects` en un `QThread` y emite los tokens nuevos. Deduplica por `message.id` y solo cuenta líneas completas. |
| `pokemon_manager.py` | Nombres y cadenas evolutivas de los 151 Pokémon de Kanto, umbrales por nivel, descarga de sprites a `assets/pokemon/{id}.png` y persistencia en `state.json`. |
| `gui.py` | Widget frameless en modo oscuro: sprite, nivel, barra animada, contadores de sesión y total, menú de inicial, animación de evolución. |
| `main.py` | Punto de entrada. |
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

## Pruebas

```bash
python test_simulation.py
```

Añade `--visible` para ver el widget durante la simulación. El script crea sus propios
archivos temporales y los borra al terminar.
