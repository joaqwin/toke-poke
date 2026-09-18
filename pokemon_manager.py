"""Lógica Pokémon (Kanto, IDs 1-151), cadenas evolutivas, sprites y persistencia.

Este módulo no depende de Qt: puede usarse desde tests o scripts sin GUI.
"""
from __future__ import annotations

import json
import os
import random
import shutil
import ssl
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Iterable

# ---------------------------------------------------------------------------
# Datos de la 1ª generación
# ---------------------------------------------------------------------------

KANTO_NAMES: dict[int, str] = {
    1: "Bulbasaur", 2: "Ivysaur", 3: "Venusaur", 4: "Charmander", 5: "Charmeleon",
    6: "Charizard", 7: "Squirtle", 8: "Wartortle", 9: "Blastoise", 10: "Caterpie",
    11: "Metapod", 12: "Butterfree", 13: "Weedle", 14: "Kakuna", 15: "Beedrill",
    16: "Pidgey", 17: "Pidgeotto", 18: "Pidgeot", 19: "Rattata", 20: "Raticate",
    21: "Spearow", 22: "Fearow", 23: "Ekans", 24: "Arbok", 25: "Pikachu",
    26: "Raichu", 27: "Sandshrew", 28: "Sandslash", 29: "Nidoran♀", 30: "Nidorina",
    31: "Nidoqueen", 32: "Nidoran♂", 33: "Nidorino", 34: "Nidoking", 35: "Clefairy",
    36: "Clefable", 37: "Vulpix", 38: "Ninetales", 39: "Jigglypuff", 40: "Wigglytuff",
    41: "Zubat", 42: "Golbat", 43: "Oddish", 44: "Gloom", 45: "Vileplume",
    46: "Paras", 47: "Parasect", 48: "Venonat", 49: "Venomoth", 50: "Diglett",
    51: "Dugtrio", 52: "Meowth", 53: "Persian", 54: "Psyduck", 55: "Golduck",
    56: "Mankey", 57: "Primeape", 58: "Growlithe", 59: "Arcanine", 60: "Poliwag",
    61: "Poliwhirl", 62: "Poliwrath", 63: "Abra", 64: "Kadabra", 65: "Alakazam",
    66: "Machop", 67: "Machoke", 68: "Machamp", 69: "Bellsprout", 70: "Weepinbell",
    71: "Victreebel", 72: "Tentacool", 73: "Tentacruel", 74: "Geodude", 75: "Graveler",
    76: "Golem", 77: "Ponyta", 78: "Rapidash", 79: "Slowpoke", 80: "Slowbro",
    81: "Magnemite", 82: "Magneton", 83: "Farfetch'd", 84: "Doduo", 85: "Dodrio",
    86: "Seel", 87: "Dewgong", 88: "Grimer", 89: "Muk", 90: "Shellder",
    91: "Cloyster", 92: "Gastly", 93: "Haunter", 94: "Gengar", 95: "Onix",
    96: "Drowzee", 97: "Hypno", 98: "Krabby", 99: "Kingler", 100: "Voltorb",
    101: "Electrode", 102: "Exeggcute", 103: "Exeggutor", 104: "Cubone", 105: "Marowak",
    106: "Hitmonlee", 107: "Hitmonchan", 108: "Lickitung", 109: "Koffing", 110: "Weezing",
    111: "Rhyhorn", 112: "Rhydon", 113: "Chansey", 114: "Tangela", 115: "Kangaskhan",
    116: "Horsea", 117: "Seadra", 118: "Goldeen", 119: "Seaking", 120: "Staryu",
    121: "Starmie", 122: "Mr. Mime", 123: "Scyther", 124: "Jynx", 125: "Electabuzz",
    126: "Magmar", 127: "Pinsir", 128: "Tauros", 129: "Magikarp", 130: "Gyarados",
    131: "Lapras", 132: "Ditto", 133: "Eevee", 134: "Vaporeon", 135: "Jolteon",
    136: "Flareon", 137: "Porygon", 138: "Omanyte", 139: "Omastar", 140: "Kabuto",
    141: "Kabutops", 142: "Aerodactyl", 143: "Snorlax", 144: "Articuno", 145: "Zapdos",
    146: "Moltres", 147: "Dratini", 148: "Dragonair", 149: "Dragonite", 150: "Mewtwo",
    151: "Mew",
}

# pre-evolución -> (posibles evoluciones, nivel acumulado al que evoluciona).
# Las evoluciones por piedra o intercambio reciben un nivel equivalente.
EVOLUTIONS: dict[int, tuple[tuple[int, ...], int]] = {
    1: ((2,), 16), 2: ((3,), 32),
    4: ((5,), 16), 5: ((6,), 36),
    7: ((8,), 16), 8: ((9,), 36),
    10: ((11,), 7), 11: ((12,), 10),
    13: ((14,), 7), 14: ((15,), 10),
    16: ((17,), 18), 17: ((18,), 36),
    19: ((20,), 20),
    21: ((22,), 20),
    23: ((24,), 22),
    25: ((26,), 30),
    27: ((28,), 22),
    29: ((30,), 16), 30: ((31,), 36),
    32: ((33,), 16), 33: ((34,), 36),
    35: ((36,), 30),
    37: ((38,), 30),
    39: ((40,), 30),
    41: ((42,), 22),
    43: ((44,), 21), 44: ((45,), 36),
    46: ((47,), 24),
    48: ((49,), 31),
    50: ((51,), 26),
    52: ((53,), 28),
    54: ((55,), 33),
    56: ((57,), 28),
    58: ((59,), 36),
    60: ((61,), 25), 61: ((62,), 36),
    63: ((64,), 16), 64: ((65,), 36),
    66: ((67,), 28), 67: ((68,), 36),
    69: ((70,), 21), 70: ((71,), 36),
    72: ((73,), 30),
    74: ((75,), 25), 75: ((76,), 36),
    77: ((78,), 40),
    79: ((80,), 37),
    81: ((82,), 30),
    84: ((85,), 31),
    86: ((87,), 34),
    88: ((89,), 38),
    90: ((91,), 36),
    92: ((93,), 25), 93: ((94,), 36),
    96: ((97,), 26),
    98: ((99,), 28),
    100: ((101,), 30),
    102: ((103,), 36),
    104: ((105,), 28),
    109: ((110,), 35),
    111: ((112,), 42),
    116: ((117,), 32),
    118: ((119,), 33),
    120: ((121,), 36),
    129: ((130,), 20),
    133: ((134, 135, 136), 30),
    138: ((139,), 40),
    140: ((141,), 40),
    147: ((148,), 30), 148: ((149,), 55),
}

STARTERS: tuple[int, ...] = (1, 4, 7, 25)
DEFAULT_TOKENS_PER_LEVEL = 100_000
MIN_ID, MAX_ID = 1, 151

SPRITE_URL = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{id}.png"


def is_kanto(pid: int) -> bool:
    return MIN_ID <= int(pid) <= MAX_ID


def name_of(pid: int) -> str:
    return KANTO_NAMES.get(int(pid), f"#{pid}")


def next_evolution(pid: int) -> tuple[tuple[int, ...], int] | None:
    """Devuelve (evoluciones posibles, nivel) o None si es forma final."""
    return EVOLUTIONS.get(int(pid))


def evolution_chain(pid: int) -> list[int]:
    """Cadena hacia adelante desde `pid` (toma la primera rama en bifurcaciones)."""
    chain = [int(pid)]
    seen = {int(pid)}
    while True:
        nxt = next_evolution(chain[-1])
        if not nxt or nxt[0][0] in seen:
            return chain
        chain.append(nxt[0][0])
        seen.add(nxt[0][0])


def pre_evolution(pid: int) -> int | None:
    for pre, (targets, _lvl) in EVOLUTIONS.items():
        if int(pid) in targets:
            return pre
    return None


def base_form(pid: int) -> int:
    cur = int(pid)
    while (pre := pre_evolution(cur)) is not None:
        cur = pre
    return cur


def format_tokens(n: int) -> str:
    n = int(n)
    if n < 1_000:
        return str(n)
    if n < 1_000_000:
        return f"{n / 1_000:.1f}k"
    return f"{n / 1_000_000:.2f}M"


# ---------------------------------------------------------------------------
# Sprites
# ---------------------------------------------------------------------------


def _ssl_context() -> ssl.SSLContext:
    """Contexto SSL usando el almacén de certificados de Windows si `truststore` está disponible."""
    try:
        import truststore  # type: ignore

        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except Exception:  # pragma: no cover - depende del entorno
        return ssl.create_default_context()


class SpriteStore:
    """Descarga y cachea sprites oficiales en `assets/pokemon/{id}.png`."""

    def __init__(self, assets_dir: Path | str = Path("assets") / "pokemon"):
        self.assets_dir = Path(assets_dir)

    def path(self, pid: int) -> Path:
        return self.assets_dir / f"{int(pid)}.png"

    def has(self, pid: int) -> bool:
        p = self.path(pid)
        return p.is_file() and p.stat().st_size > 0

    @staticmethod
    def url(pid: int) -> str:
        return SPRITE_URL.format(id=int(pid))

    def download(self, pid: int, timeout: float = 20.0) -> Path:
        """Descarga el sprite si no existe. Bloqueante: llamar desde un hilo secundario."""
        if not is_kanto(pid):
            raise ValueError(f"ID fuera de Kanto: {pid}")
        target = self.path(pid)
        if self.has(pid):
            return target
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        data = self._fetch(self.url(pid), timeout)
        if not data.startswith(b"\x89PNG"):
            raise RuntimeError(f"Respuesta inválida al descargar sprite {pid}")
        tmp = target.with_suffix(".part")
        tmp.write_bytes(data)
        os.replace(tmp, target)
        return target

    def ensure(self, pids: Iterable[int]) -> list[Path]:
        return [self.download(p) for p in pids]

    @staticmethod
    def _fetch(url: str, timeout: float) -> bytes:
        req = urllib.request.Request(url, headers={"User-Agent": "toke-poke/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
                return resp.read()
        except Exception as first_error:
            # Respaldo: curl.exe viene con Windows 10 y usa el almacén de certificados del sistema.
            curl = shutil.which("curl")
            if not curl:
                raise first_error
            with tempfile.TemporaryDirectory() as td:
                out = Path(td) / "sprite.png"
                proc = subprocess.run(
                    [curl, "-sSL", "--max-time", str(int(timeout)), "-o", str(out), url],
                    capture_output=True,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                if proc.returncode != 0 or not out.is_file():
                    raise first_error
                return out.read_bytes()


# ---------------------------------------------------------------------------
# Estado y evolución
# ---------------------------------------------------------------------------


class Evolution:
    __slots__ = ("source", "target", "threshold")

    def __init__(self, source: int, target: int, threshold: int):
        self.source, self.target, self.threshold = source, target, threshold

    def __repr__(self) -> str:  # pragma: no cover
        return f"Evolution({name_of(self.source)} -> {name_of(self.target)} @ {self.threshold})"


class PokemonManager:
    """Estado del Pokémon activo y su progreso, persistido en `state.json`."""

    def __init__(
        self,
        state_path: Path | str = Path("state.json"),
        assets_dir: Path | str = Path("assets") / "pokemon",
        tokens_per_level: int | None = None,
    ):
        self.state_path = Path(state_path)
        self.sprites = SpriteStore(assets_dir)
        self.state: dict = self._default_state()
        self.load()
        if tokens_per_level:
            self.state["tokens_per_level"] = int(tokens_per_level)

    # ---- persistencia --------------------------------------------------
    @staticmethod
    def _default_state() -> dict:
        return {
            "version": 1,
            "starter": None,
            "active_pokemon": None,
            "total_tokens": 0,
            "xp_tokens": 0,
            "stage_start_tokens": 0,
            "unlocked": [],
            "evolution_log": [],
            "tokens_per_level": DEFAULT_TOKENS_PER_LEVEL,
            "file_offsets": {},
            "window_pos": None,
            "always_on_top": True,
            "created_at": time.time(),
            "updated_at": time.time(),
        }

    def load(self) -> None:
        if not self.state_path.is_file():
            return
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if isinstance(data, dict):
            self.state.update(data)
        if self.state.get("active_pokemon") is not None and not is_kanto(self.state["active_pokemon"]):
            self.state["active_pokemon"] = None
            self.state["starter"] = None

    def save(self) -> None:
        self.state["updated_at"] = time.time()
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.state, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.state_path)

    # ---- propiedades ---------------------------------------------------
    @property
    def tokens_per_level(self) -> int:
        return max(1, int(self.state.get("tokens_per_level") or DEFAULT_TOKENS_PER_LEVEL))

    @property
    def active(self) -> int | None:
        pid = self.state.get("active_pokemon")
        return int(pid) if pid is not None else None

    @property
    def has_starter(self) -> bool:
        return self.state.get("starter") is not None and self.active is not None

    @property
    def total_tokens(self) -> int:
        return int(self.state.get("total_tokens") or 0)

    @property
    def xp_tokens(self) -> int:
        return int(self.state.get("xp_tokens") or 0)

    @property
    def unlocked(self) -> list[int]:
        return [int(p) for p in self.state.get("unlocked") or []]

    @property
    def level(self) -> int:
        return 1 + self.xp_tokens // self.tokens_per_level

    def next_threshold(self) -> int | None:
        """Tokens acumulados (XP) necesarios para la próxima evolución, o None si es final."""
        if self.active is None:
            return None
        nxt = next_evolution(self.active)
        if not nxt:
            return None
        threshold = nxt[1] * self.tokens_per_level
        stage_start = int(self.state.get("stage_start_tokens") or 0)
        return max(threshold, stage_start + self.tokens_per_level)

    def next_pokemon_candidates(self) -> tuple[int, ...]:
        if self.active is None:
            return ()
        nxt = next_evolution(self.active)
        return nxt[0] if nxt else ()

    def progress(self) -> tuple[int, int, float]:
        """(tokens en esta etapa, tokens necesarios en esta etapa, fracción 0..1)."""
        threshold = self.next_threshold()
        stage_start = int(self.state.get("stage_start_tokens") or 0)
        if threshold is None:
            return (self.xp_tokens - stage_start, 0, 1.0)
        needed = max(1, threshold - stage_start)
        done = max(0, min(needed, self.xp_tokens - stage_start))
        return (done, needed, done / needed)

    # ---- acciones ------------------------------------------------------
    def choose_starter(self, pid: int) -> None:
        pid = int(pid)
        if not is_kanto(pid):
            raise ValueError(f"ID fuera de Kanto: {pid}")
        self.state["starter"] = pid
        self.state["active_pokemon"] = pid
        self.state["xp_tokens"] = 0
        self.state["stage_start_tokens"] = 0
        self.state["unlocked"] = [pid]
        self.state["evolution_log"] = []
        self.save()

    def reset(self) -> None:
        keep = {k: self.state.get(k) for k in ("file_offsets", "window_pos", "always_on_top", "tokens_per_level", "total_tokens")}
        self.state = self._default_state()
        self.state.update({k: v for k, v in keep.items() if v is not None})
        self.save()

    def add_tokens(self, amount: int, count_xp: bool = True, rng: random.Random | None = None) -> list[Evolution]:
        """Suma tokens y devuelve las evoluciones desbloqueadas (puede ser más de una)."""
        amount = int(amount)
        if amount <= 0:
            return []
        self.state["total_tokens"] = self.total_tokens + amount
        events: list[Evolution] = []
        if count_xp and self.has_starter:
            self.state["xp_tokens"] = self.xp_tokens + amount
            events = self._apply_evolutions(rng or random)
        return events

    def _apply_evolutions(self, rng) -> list[Evolution]:
        events: list[Evolution] = []
        while True:
            threshold = self.next_threshold()
            if threshold is None or self.xp_tokens < threshold:
                break
            source = self.active
            target = int(rng.choice(self.next_pokemon_candidates()))
            self.state["active_pokemon"] = target
            self.state["stage_start_tokens"] = threshold
            if target not in self.unlocked:
                self.state.setdefault("unlocked", []).append(target)
            self.state.setdefault("evolution_log", []).append(
                {"from": source, "to": target, "at_tokens": threshold, "time": time.time()}
            )
            events.append(Evolution(source, target, threshold))
        return events

    # ---- sprites -------------------------------------------------------
    def sprite_path(self, pid: int) -> Path:
        return self.sprites.path(pid)

    def sprites_needed(self) -> list[int]:
        """IDs cuyos sprites conviene tener listos: activo, próximas evoluciones e iniciales."""
        ids: list[int] = []
        if self.active is not None:
            ids.append(self.active)
            ids.extend(self.next_pokemon_candidates())
        ids.extend(STARTERS)
        ids.extend(self.unlocked)
        out: list[int] = []
        for p in ids:
            if p not in out:
                out.append(p)
        return out
