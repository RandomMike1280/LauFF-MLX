"""Strict, bounded wire types. Neuron IDs never cross the game boundary."""
from __future__ import annotations
import math
import re

VERSION = 1
TTL_SECONDS = 45
POLL_SECONDS = 3
SESSION = re.compile(r"^[A-Za-z0-9-]{8,64}$")
MOVES = ("MOVE_NORTH", "MOVE_EAST", "MOVE_SOUTH", "MOVE_WEST")
ACTIONS = ("HARVEST", "WAIT") + MOVES
OFFSETS = ((0, 0), (0, -1), (1, 0), (0, 1), (-1, 0))
OUTCOMES = {"NONE", "HARVEST_CONFIRMED", "HARVEST_UNCONFIRMED", "WAIT", "REJECTED", "PAUSED", "MOVED", "MOVE_UNCONFIRMED", "CAPACITY", "ERROR"}


def integer(value, name, low=-10000, high=10000):
    if type(value) not in (int, float) or not math.isfinite(value) or int(value) != value or not low <= value <= high:
        raise ValueError(f"invalid {name}")
    return int(value)


def observation(value):
    if not isinstance(value, dict) or value.get("v") != VERSION:
        raise ValueError("unsupported observation")
    if not isinstance(value.get("session"), str) or not SESSION.fullmatch(value["session"]):
        raise ValueError("invalid session")
    integer(value.get("seq"), "sequence", 1, 1_000_000_000)
    x, z = integer(value.get("x"), "x"), integer(value.get("z"), "z")
    if type(value.get("can_harvest")) is not bool:
        raise ValueError("can_harvest must be boolean")
    if type(value.get("autonomous", False)) is not bool:
        raise ValueError("autonomous must be boolean")
    count = integer(value.get("fruit_count"), "fruit_count", 0, 1_000_000)
    cap = integer(value.get("fruit_capacity"), "fruit_capacity", 1, 1_000_000)
    if value.get("previous_outcome") not in OUTCOMES:
        raise ValueError("invalid previous outcome")
    tiles = value.get("tiles")
    if not isinstance(tiles, list) or len(tiles) != 5:
        raise ValueError("exactly five local tile records required")
    for tile, (dx, dz) in zip(tiles, OFFSETS):
        if not isinstance(tile, dict) or tile.get("x") != x + dx or tile.get("z") != z + dz:
            raise ValueError("tile order must be current, north, east, south, west")
        integer(tile.get("x"), "tile x", -10001, 10001)
        integer(tile.get("z"), "tile z", -10001, 10001)
        if type(tile.get("known")) is not bool or type(tile.get("has_fruit")) is not bool:
            raise ValueError("invalid tile flags")
        if not isinstance(tile.get("plant"), str) or len(tile["plant"]) > 80:
            raise ValueError("invalid plant name")
        p = tile.get("fruit_percent")
        if type(p) not in (int, float) or not math.isfinite(p) or not -1 <= p <= 10000:
            raise ValueError("invalid raw fruit percentage")
    return value


def command_text(obs, action, remaining_ms):
    observation(obs)
    if action not in ACTIONS:
        raise ValueError("invalid action")
    remaining_ms = integer(remaining_ms, "remaining_ms", 1, TTL_SECONDS * 1000)
    return f"C|{obs['session']}|{int(obs['seq'])}|{int(obs['x'])}|{int(obs['z'])}|{remaining_ms}|{action}"


def parse_command(text, obs, *, age_s, roundtrip_s=0):
    """Reference for the Lau checks; never accept a late response on receipt."""
    observation(obs)
    fields = text.split("|")
    if len(fields) != 7 or fields[0] != "C" or fields[1] != obs["session"]:
        raise ValueError("command identity mismatch")
    if not all(re.fullmatch(r"-?[0-9]+", x) for x in fields[2:6]):
        raise ValueError("malformed integer")
    if any(str(int(x)) != x for x in fields[2:6]):
        raise ValueError("noncanonical integer")
    seq, x, z, remaining = map(int, fields[2:6])
    if (seq, x, z) != (obs["seq"], obs["x"], obs["z"]):
        raise ValueError("stale command")
    if not 0 < remaining <= TTL_SECONDS * 1000 or remaining <= roundtrip_s * 1000 or age_s >= TTL_SECONDS:
        raise ValueError("expired command")
    if fields[6] not in ACTIONS:
        raise ValueError("unknown action")
    if fields[6] in MOVES and obs.get('autonomous') is not True:
        raise ValueError('movement requires autonomous observation')
    return fields[6]
