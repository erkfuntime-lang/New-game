"""
AI Multiplayer Space Shooter — Pygame Port
Converted from Swift/SwiftUI (iOS) to Python/Pygame.
Single-player vs AI enemies with all 9 ships and special abilities.
"""

import pygame
import math
import random
import uuid
import time
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from enum import Enum, auto

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

SCREEN_W, SCREEN_H = 1280, 720
FPS = 60
WORLD_SCALE = 1.0   # pixel units match Swift's CGFloat units

# Sprite display sizes (2× scale from Swift originals for better visibility)
SPRITE_SIZES = {
    "playerSprite1":  (80, 48), "playerSprite2": (70, 48), "playerSprite3": (52, 48),
    "player2Sprite1": (80, 56), "player2Sprite2":(72, 56), "player2Sprite3":(60, 56),
    "furos1":  (64, 64), "furos2": (72, 64), "furos3": (56, 64),
    "3_9":     (52, 72), "costume13": (70, 72), "costume14": (60, 72),
    "3_6":     (60, 64), "costume1":  (80, 64), "costume10": (72, 64),
    "opressor":(72, 84), "shade":     (60, 64),
    "3_13":    (68, 64), "3_5":       (60, 64),
    "ship":    (64, 68), "blizzard1": (72, 56), "blizzard2": (84, 56),
}

# ═════════════════════════════════════════════════════════════════════════════
# EASY CUSTOMISATION CONFIG — change these values to tweak gameplay
# ═════════════════════════════════════════════════════════════════════════════

class CFG:
    # ── Player ────────────────────────────────────────────────────────────────
    PLAYER_PASSIVE_REGEN    = 2.0    # HP/s passive regen (all ships)
    PLAYER_HEAL_TICK_HP     = 4      # HP restored each heal tick
    PLAYER_BULLET_SPEED     = 1000.0 # pixels/s
    PLAYER_MISSILE_SPEED    = 1200   # homing missile target speed
    PLAYER_FROST_MISS_SPEED = 1800

    # ── AI ────────────────────────────────────────────────────────────────────
    AI_FIRE_RANGE           = 700    # range at which AI enters combat mode
    AI_ORBIT_RADIUS         = 350    # preferred combat distance
    AI_ORBIT_STRAFE         = 0.6    # strafe bias (0=face, 1=pure strafe)
    AI_AIM_TOL_DEG          = 20.0   # aim tolerance before shooting
    AI_RESPAWN_DELAY        = 4.0    # seconds between AI death and respawn
    AI_PASSIVE_REGEN        = 2.0    # HP/s passive regen for AI
    AI_HEAL_TICK_HP         = 4

    # ── Boss ──────────────────────────────────────────────────────────────────
    BOSS_HEALTH_MULT        = 3.5    # HP multiplier vs normal AI
    BOSS_DAMAGE_MULT        = 1.8    # damage multiplier for boss weapons
    BOSS_SPEED_MULT         = 0.85   # movement speed multiplier (<1 = slower)
    BOSS_FIRE_RATE_MULT     = 0.6    # fire interval multiplier (<1 = faster)
    BOSS_SCALE_DISPLAY      = 1.4    # visual size scale of boss sprite
    BOSS_EVERY_N_WAVES      = 5      # boss fight every N waves

    # ── Waves ─────────────────────────────────────────────────────────────────
    WAVE_ENEMIES_START      = 2      # enemies in wave 1
    WAVE_ENEMIES_GROWTH     = 2      # add 1 enemy every N waves (e.g. 2 = every other wave)
    WAVE_ENEMIES_MAX        = 8      # cap on enemies per wave
    WAVE_CLEAR_DELAY        = 2.5    # seconds between wave clear and next spawn
    WAVE_ENEMY_SPREAD       = 900    # spawn radius around origin

    # ── Normal AI handicap (makes bots weaker than the player) ───────────────
    AI_HEALTH_MULT          = 0.55   # fraction of ship's base HP  (< 1 = weaker)
    AI_DAMAGE_MULT          = 0.60   # fraction of ship's base damage (< 1 = weaker)
    AI_FIRE_RATE_MULT       = 1.45   # multiplier on fire interval  (> 1 = slower fire)

    # ── Powerups ──────────────────────────────────────────────────────────────
    POWERUP_SPAWN_INTERVAL  = 12.0   # seconds between auto-spawns
    POWERUP_LIFETIME        = 18.0   # seconds a powerup stays on map
    POWERUP_COLLECT_RADIUS  = 55     # pick-up radius (pixels, world space)
    POWERUP_MAX_ON_MAP      = 4      # maximum simultaneous powerups

    POWERUP_SHIELD_RESTORE  = 120    # HP restored by shield orb
    POWERUP_FIRERATE_DUR    = 6.0    # seconds of fire-rate boost
    POWERUP_SPEED_DUR       = 6.0    # seconds of speed boost
    POWERUP_SPEED_MULT      = 1.6    # thrust multiplier during speed boost
    POWERUP_DAMAGE_DUR      = 8.0    # seconds of damage boost
    POWERUP_DAMAGE_MULT     = 1.75   # damage multiplier during damage boost
    POWERUP_SHIELD_MAX_DUR  = 5.0    # seconds of damage immunity (max-shield)

# ─────────────────────────────────────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────────────────────────────────────

class SpecialType(Enum):
    DASH    = auto()
    MISSILE = auto()
    ALIEN   = auto()
    FIRERATE= auto()
    HEAL    = auto()
    NONE    = auto()   # Oppressor barrage
    LASER   = auto()
    CLOAK   = auto()
    FROST   = auto()

class Screen(Enum):
    TITLE      = auto()
    SHIP_SELECT= auto()
    GAME       = auto()

class PowerupType(Enum):
    SHIELD    = auto()   # restore HP
    FIRERATE  = auto()   # faster shooting
    SPEED     = auto()   # movement boost
    DAMAGE    = auto()   # bullet damage boost
    INVINCIBLE= auto()   # brief invincibility

# ─────────────────────────────────────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ShipType:
    name: str
    desc: str
    shield: float
    thrust: float
    turn: float           # radians/s² lerp factor
    special: SpecialType
    special_cooldown: float
    idle_sprite: str
    moving_sprites: List[str]
    fire_interval: float
    spread_amt: float     # degrees
    bullet_dmg: float
    drag_amt: float

@dataclass
class Bullet:
    id: str
    x: float; y: float
    vx: float; vy: float
    damage: float
    lifetime: float = 3.0
    owner_name: str = ""
    is_frost_sphere: bool = False
    has_burst: bool = False
    burst_timer: float = 0.4
    curve_dir: float = 0.0

@dataclass
class Missile:
    id: str
    owner_id: str
    x: float; y: float
    angle: float
    damage: float
    lifetime: float = 10.0
    speed: float = 0.0
    owner_name: str = ""
    is_frost: bool = False

@dataclass
class Laser:
    id: str
    x: float; y: float
    angle: float
    lifetime: float = 0.08
    special: bool = False
    owner_name: str = ""
    mine: bool = False

@dataclass
class MuzzleFlash:
    x: float; y: float
    frame: int = 0
    attached: bool = False
    is_laser: bool = False

@dataclass
class Explosion:
    x: float; y: float
    size: float
    frame: int = 0

@dataclass
class Afterimage:
    x: float; y: float
    angle: float
    sprite: str
    alpha: float = 0.8
    lifetime: float = 1.0

@dataclass
class Star:
    x: float; y: float; size: float

@dataclass
class KillEntry:
    text: str
    timer: float = 4.0

@dataclass
class Powerup:
    id: str
    x: float
    y: float
    kind: PowerupType
    lifetime: float = CFG.POWERUP_LIFETIME
    pulse: float = 0.0  # animation phase

# ─────────────────────────────────────────────────────────────────────────────
# SHIPS
# ─────────────────────────────────────────────────────────────────────────────

SHIPS = [
    ShipType("Raider MKII",
             "Versatile combat craft.\nWeapon: XML-40 Autocannon\nSpecial: Phase Drive (Dash)",
             350, 800, 6, SpecialType.DASH, 1,
             "playerSprite3", ["playerSprite1","playerSprite2"],
             0.2, 3, 25, 0.7),
    ShipType("TI-X Interceptor",
             "Agile threat-disposal ship.\nWeapon: XD-44 Minigun\nSpecial: V-6 Cruise Missile",
             250, 1200, 7, SpecialType.MISSILE, 4,
             "player2Sprite3", ["player2Sprite1","player2Sprite2"],
             0.15, 2.5, 23, 0.8),
    ShipType("Furos V",
             "Heavy assault ship.\nWeapon: KD-56 Chaingun\nSpecial: BU-42 Overdrive (Fire Rate)",
             300, 700, 5, SpecialType.FIRERATE, 15,
             "furos3", ["furos2","furos1"],
             0.12, 5, 20, 0.65),
    ShipType("Wraith CO-025",
             "Hybrid alien-human technology.\nWeapon: K-90 Wave-split Cannon\nE: Blink Strike (hold+aim+release)  F: Melee Slash (combo up to x3)",
             300, 750, 5, SpecialType.ALIEN, 3,
             "3_9", ["costume13","costume14"],
             0.3, 0, 25, 0.7),
    ShipType("Titan CS-M1",
             "Military durable armor craft.\nWeapon: XML-35 Autocannon\nSpecial: DCS-5 Repair System (Heal)",
             500, 750, 6, SpecialType.HEAL, 10,
             "3_6", ["costume1","costume10"],
             0.2, 3, 30, 0.7),
    ShipType("Oppressor IX",
             "Superheavy warship.\nWeapon: MX-99 Siege Missile\nSpecial: DS-102 Burst Cannon",
             500, 280, 3, SpecialType.NONE, 6,
             "opressor", ["opressor"],
             2, 0, 40, 0.5),
    ShipType("X-11 Shade Fighter",
             "Stealth infiltration craft.\nWeapon: KR-35 Burst Cannon\nSpecial: OD-52 Optical Cloak",
             260, 1000, 7, SpecialType.CLOAK, 15,
             "shade", ["3_5","3_13"],
             0.8, 2, 25, 0.9),
    ShipType("Blizzard AC-7",
             "Cryogenic assault craft.\nWeapon: CX-9 Frost Sphere Launcher\nSpecial: ICE-2 Dual Frost Missile",
             320, 680, 5, SpecialType.FROST, 6,
             "blizzard1", ["blizzard2"],
             0.7, 0, 28, 0.65),
    ShipType("Sentinel",
             "Long-range laser platform.\nWeapon: A-7 Fury Pulse Laser\nSpecial: B-3 Laser Catalyst",
             300, 500, 2, SpecialType.LASER, 8,
             "ship", ["ship"],
             0.2, 0, 20, 0.5),
]

AI_SHIP_ROSTER = SHIPS[:]

# ─────────────────────────────────────────────────────────────────────────────
# ASSET MANAGER
# ─────────────────────────────────────────────────────────────────────────────

class Assets:
    def __init__(self):
        self.sprites: Dict[str, pygame.Surface] = {}
        self.font_title = None
        self.font_body  = None
        self.font_small = None
        self.font_hud   = None

    def load(self, asset_dir: str):
        import os
        # Load sprites
        for fname in os.listdir(asset_dir):
            if fname.endswith(".png"):
                key = fname[:-4]
                raw = pygame.image.load(os.path.join(asset_dir, fname)).convert_alpha()
                self.sprites[key] = raw

        # Font
        font_path = os.path.join(asset_dir, "Orbitron-Medium.ttf")
        try:
            self.font_title = pygame.font.Font(font_path, 48)
            self.font_body  = pygame.font.Font(font_path, 22)
            self.font_small = pygame.font.Font(font_path, 14)
            self.font_hud   = pygame.font.Font(font_path, 13)
        except Exception:
            self.font_title = pygame.font.SysFont("monospace", 48, bold=True)
            self.font_body  = pygame.font.SysFont("monospace", 22, bold=True)
            self.font_small = pygame.font.SysFont("monospace", 14)
            self.font_hud   = pygame.font.SysFont("monospace", 13)

    def get_sprite(self, name: str, size: Optional[Tuple[int,int]] = None) -> Optional[pygame.Surface]:
        s = self.sprites.get(name)
        if s is None:
            return None
        if size:
            return pygame.transform.smoothscale(s, size)
        return s

    def get_sprite_scaled(self, name: str) -> Optional[pygame.Surface]:
        """Return sprite at the standard display size for that sprite name."""
        sz = SPRITE_SIZES.get(name)
        if sz:
            return self.get_sprite(name, sz)
        return self.sprites.get(name)

# ─────────────────────────────────────────────────────────────────────────────
# MATH HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def shortest_angle_diff(a: float, b: float) -> float:
    diff = b - a
    while diff >  math.pi: diff -= 2*math.pi
    while diff < -math.pi: diff += 2*math.pi
    return diff

def rotated_offset(ox: float, oy: float, angle: float) -> Tuple[float, float]:
    c, s = math.cos(angle), math.sin(angle)
    return ox*c - oy*s, ox*s + oy*c

def draw_rotated_sprite(surf: pygame.Surface, sprite: pygame.Surface,
                        cx: float, cy: float, angle: float,
                        alpha: int = 255):
    """Draw sprite centred at (cx,cy) rotated by angle (radians)."""
    deg = -math.degrees(angle)
    rot = pygame.transform.rotate(sprite, deg)
    if alpha < 255:
        rot = rot.copy()
        rot.set_alpha(alpha)
    rect = rot.get_rect(center=(int(cx), int(cy)))
    surf.blit(rot, rect)

def draw_glow(surf: pygame.Surface, x: float, y: float, color: Tuple[int,int,int], radius: int, alpha: int = 80):
    """Draw a glowing circle. Safe against zero/negative radius and bad alpha."""
    if radius <= 0:
        return
    alpha = max(0, min(255, int(alpha)))
    glow = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    pygame.draw.circle(glow, (*color, alpha), (radius, radius), radius)
    surf.blit(glow, (int(x) - radius, int(y) - radius), special_flags=pygame.BLEND_RGBA_ADD)
# ─────────────────────────────────────────────────────────────────────────────
# BACKGROUND RENDERER
# ─────────────────────────────────────────────────────────────────────────────

class Background:
    def __init__(self, assets: Assets):
        raw = assets.sprites.get("backgroundSprite")
        if raw:
            tw, th = 1024*2, 512*2
            self.tile = pygame.transform.smoothscale(raw, (tw, th))
            self.tw, self.th = tw, th
        else:
            self.tile = None
            self.tw = self.th = 512

    def draw(self, surf: pygame.Surface, cam_x: float, cam_y: float):
        if self.tile is None:
            surf.fill((10, 10, 30))
            return
        tw, th = self.tw, self.th
        cx, cy = SCREEN_W//2, SCREEN_H//2
        # parallax: camera moves at half speed for bg
        off_x = (-cam_x * 0.5) % tw
        off_y = (-cam_y * 0.5) % th
        for ix in range(-1, SCREEN_W//tw + 2):
            for iy in range(-1, SCREEN_H//th + 2):
                x = off_x + ix * tw
                y = off_y + iy * th
                surf.blit(self.tile, (int(x), int(y)))

# ─────────────────────────────────────────────────────────────────────────────
# GAME ENGINE  (local player physics + state)
# ─────────────────────────────────────────────────────────────────────────────

class GameEngine:
    # Constants
    MISSILE_TURN_RATE        = 2.5
    MISSILE_TARGET_SPEED     = 1200
    MISSILE_ACCEL            = 1.0
    FROST_MISSILE_SPEED      = 1800
    FROST_MISSILE_ACCEL      = 0.35
    ALIEN_PHASE_DURATION     = 0.2
    ALIEN_PHASE_DISTANCE     = 500

    # Wraith Blink-Strike constants
    WRAITH_BLINK_DAMAGE      = 90.0   # damage on arrival
    WRAITH_BLINK_AIM_WINDOW  = 35.0   # degrees: must face target within this cone
    WRAITH_BLINK_CHARGE_TIME = 0.35   # seconds key must be held before release fires
    WRAITH_BLINK_RANGE       = 1200.0 # max teleport range

    # Wraith Melee constants
    WRAITH_MELEE_RANGE       = 130.0  # melee reach radius
    WRAITH_MELEE_DAMAGE      = 55.0   # base damage per hit
    WRAITH_MELEE_STUN_DUR    = 1.2    # seconds enemy is stunned
    WRAITH_MELEE_COOLDOWN    = 0.55   # seconds between melee swings
    WRAITH_MELEE_COMBO_WINDOW= 0.8    # seconds to land next hit for combo
    WRAITH_MELEE_COMBO_MULT  = 1.5    # damage multiplier per combo step (caps at 3)
    WRAITH_MELEE_AIM_DEG     = 50.0   # must be facing within this cone to land hit

    CLOAK_REVEAL_DURATION    = 0.1
    CLOAK_DURATION           = 5.0
    DASH_DURATION            = 0.2
    FIRE_RATE_DURATION       = 5.0
    HEAL_DURATION            = 1.0
    HEAL_TICK_INTERVAL       = 0.1
    AFTERIMAGE_INTERVAL      = 0.02
    CAMERA_LOOKAHEAD         = 0.1
    CAMERA_DAMP              = 15
    MAX_JOYSTICK_RADIUS      = 80

    def __init__(self, ship: ShipType, player_id: str):
        self.ship = ship
        self.player_id = player_id

        # Config from ship
        self.max_shield      = ship.shield
        self.thrust          = ship.thrust
        self.rotation_lerp   = ship.turn
        self.dash_cd_time    = ship.special_cooldown
        self.type_special    = ship.special
        self.fire_interval   = ship.fire_interval
        self.spread_amt      = ship.spread_amt
        self.bullet_dmg      = ship.bullet_dmg
        self.drag_amt        = ship.drag_amt
        self.moving_sprites  = ship.moving_sprites
        self.idle_sprite     = ship.idle_sprite

        # State
        self.shield       = self.max_shield
        self.x = self.y   = 0.0
        self.angle        = 0.0
        self.cam_x = self.cam_y = 0.0
        self.vx = self.vy = 0.0
        self.target_angle = 0.0
        self.is_dead      = False
        self.death_timer  = 0.0

        self.bullets:     List[Bullet]     = []
        self.missiles:    List[Missile]    = []
        self.lasers:      List[Laser]      = []
        self.flashes:     List[MuzzleFlash]= []
        self.explosions:  List[Explosion]  = []
        self.afterimages: List[Afterimage] = []
        self.kill_feed:   List[KillEntry]  = []
        self.stars:       List[Star]       = []

        self.frame_count  = 0
        self.sprite_inc   = 0
        self.anim_timer   = 0.0

        # Ability state
        self.dash_cooldown         = 0.0
        self.dash_active           = False
        self.dash_time_remaining   = 0.0
        self.dash_acceleration     = 10000.0
        self.fire_rate_active      = False
        self.fire_rate_remaining   = 0.0
        self.heal_active           = False
        self.heal_remaining        = 0.0
        self.heal_accumulator      = 0.0
        self.cloak_active          = False
        self.cloak_remaining       = 0.0
        self.cloak_reveal_remaining= 0.0
        self.alien_phase_active    = False
        self.alien_elapsed         = 0.0
        self.alien_start_x         = 0.0
        self.alien_start_y         = 0.0
        self.alien_target_x        = 0.0
        self.alien_target_y        = 0.0

        # Wraith blink-strike charge state
        self.wraith_charging       = False   # True while E/Shift held
        self.wraith_charge_timer   = 0.0     # how long key has been held
        self.wraith_charge_locked  = False   # threshold met, waiting for key release
        self.wraith_blink_fx_timer = 0.0     # brief after-blink visual effect
        self.wraith_aim_ok         = False   # True when a valid target is in the aim cone
        self.wraith_nearest_id     = None    # id of nearest live enemy (set externally)
        self.wraith_nearest_x      = 0.0     # position of that enemy
        self.wraith_nearest_y      = 0.0

        # Wraith melee state
        self.wraith_melee_cooldown   = 0.0   # time until next swing allowed
        self.wraith_melee_anim_timer = 0.0   # visual slash effect timer
        self.wraith_combo_count      = 0     # current combo streak (0-3)
        self.wraith_combo_window     = 0.0   # time remaining to land next combo hit
        self.wraith_melee_hit_fx: List[Tuple[float,float,float]] = []  # [(x,y,timer)]

        self.laser_special_active    = False
        self.laser_special_timer   = 0.0
        self.frost_slow_timer      = 0.0
        self.drag_coefficient      = ship.drag_amt

        # Burst fire helpers
        self.burst_schedule:  List[Tuple[float, str]] = []  # (time, type)

        # Powerup active buffs
        self.powerup_firerate_timer  = 0.0   # seconds remaining
        self.powerup_speed_timer     = 0.0
        self.powerup_damage_timer    = 0.0
        self.powerup_invincible_timer= 0.0
        self.powerup_damage_mult     = 1.0   # live multiplier
        self.powerup_speed_active    = False

        # Last known position (used by AI when player is cloaked)
        self.last_known_x = self.x
        self.last_known_y = self.y

        # Input
        self.thrust_active = False
        self.fire_active   = False
        self.joystick_dx   = 0.0
        self.joystick_dy   = 0.0

        self.time_since_shot = 0.0
        self.fps = 60.0

        # Stars
        smw = SCREEN_W * 4
        smh = SCREEN_H * 4
        self.star_map_w = smw
        self.star_map_h = smh
        self.stars = [Star(random.uniform(0, smw), random.uniform(0, smh),
                           random.uniform(2, 5)) for _ in range(200)]

    # ── Input setters ──────────────────────────────────────────────────────

    def set_joystick(self, dx: float, dy: float, mag: float):
        self.joystick_dx   = dx
        self.joystick_dy   = dy
        self.thrust_active = True
        self.target_angle  = math.atan2(dy, dx)

    def end_joystick(self):
        self.thrust_active = False
        self.joystick_dx   = 0.0
        self.joystick_dy   = 0.0

    @property
    def joystick_mag(self) -> float:
        return min(math.hypot(self.joystick_dx, self.joystick_dy), 1.0)

    # ── Main tick ──────────────────────────────────────────────────────────

    def tick(self, dt: float):
        if self.is_dead:
            self._tick_particles(dt)
            return
        if self.shield <= 0:
            self._die()
        self._update(dt)

    def _update(self, dt: float):
        self.frame_count += 1

        # Ability timers
        if self.cloak_reveal_remaining > 0:
            self.cloak_reveal_remaining -= dt
        if self.cloak_active:
            self.cloak_remaining -= dt
            if self.cloak_remaining <= 0:
                self.cloak_active = False
        if self.fire_rate_active:
            self.fire_rate_remaining -= dt
            if self.fire_rate_remaining <= 0:
                self.fire_rate_active = False
        if self.heal_active:
            self.heal_remaining   -= dt
            self.heal_accumulator += dt
            while self.heal_accumulator >= self.HEAL_TICK_INTERVAL:
                self.heal_accumulator -= self.HEAL_TICK_INTERVAL
                self.shield = min(self.shield + CFG.PLAYER_HEAL_TICK_HP, self.max_shield)
            if self.heal_remaining <= 0:
                self.heal_active = False
        if self.laser_special_active:
            self.laser_special_timer -= dt
            if self.laser_special_timer <= 0:
                self.laser_special_active = False
        if self.frost_slow_timer > 0:
            self.frost_slow_timer -= dt

        # Wraith charge-up tick
        if self.type_special == SpecialType.ALIEN and self.wraith_charging:
            self.wraith_charge_timer += dt
            if self.wraith_charge_timer >= self.WRAITH_BLINK_CHARGE_TIME:
                self.wraith_charge_locked = True   # ready to fire on key-release
        if self.wraith_blink_fx_timer > 0:
            self.wraith_blink_fx_timer -= dt

        # Wraith melee timers
        if self.wraith_melee_cooldown > 0:
            self.wraith_melee_cooldown -= dt
        if self.wraith_melee_anim_timer > 0:
            self.wraith_melee_anim_timer -= dt
        if self.wraith_combo_window > 0:
            self.wraith_combo_window -= dt
            if self.wraith_combo_window <= 0:
                self.wraith_combo_count = 0   # combo dropped
        self.wraith_melee_hit_fx = [(x, y, t - dt) for x, y, t in self.wraith_melee_hit_fx if t - dt > 0]

        # Update aim-cone indicator for Wraith
        if self.type_special == SpecialType.ALIEN and self.wraith_nearest_id is not None:
            dx = self.wraith_nearest_x - self.x
            dy = self.wraith_nearest_y - self.y
            angle_to = math.atan2(dy, dx)
            diff = abs(shortest_angle_diff(self.angle, angle_to)) * 180.0 / math.pi
            dist  = math.hypot(dx, dy)
            self.wraith_aim_ok = (diff <= self.WRAITH_BLINK_AIM_WINDOW
                                  and dist <= self.WRAITH_BLINK_RANGE)

        # Passive regeneration (all ships): 2 HP/s, does not stack with active heal
        if not self.heal_active:
            self.shield = min(self.shield + CFG.PLAYER_PASSIVE_REGEN * dt, self.max_shield)

        # Track last known position for AI (only update when not fully cloaked)
        if not (self.cloak_active and self.cloak_reveal_remaining <= 0):
            self.last_known_x = self.x
            self.last_known_y = self.y

        # Powerup timers
        if self.powerup_firerate_timer > 0:  self.powerup_firerate_timer -= dt
        if self.powerup_speed_timer > 0:
            self.powerup_speed_timer -= dt
            self.powerup_speed_active = True
        else:
            self.powerup_speed_active = False
        if self.powerup_damage_timer > 0:
            self.powerup_damage_timer -= dt
            self.powerup_damage_mult  = CFG.POWERUP_DAMAGE_MULT
        else:
            self.powerup_damage_mult  = 1.0
        if self.powerup_invincible_timer > 0: self.powerup_invincible_timer -= dt

        # Burst scheduled shots
        self._process_burst(dt)

        # Shooting
        self.time_since_shot += dt
        eff_interval = self.fire_interval * (0.5 if (self.fire_rate_active or self.laser_special_active or self.powerup_firerate_timer > 0) else 1.0)
        if self.fire_active and self.time_since_shot >= eff_interval:
            self._fire()
            self.time_since_shot = 0.0

        # Animation
        self.anim_timer += dt
        if self.thrust_active and self.anim_timer > 0.1:
            self.sprite_inc += 1
            self.anim_timer  = 0.0

        # Rotation
        self.angle += shortest_angle_diff(self.angle, self.target_angle) * self.rotation_lerp * dt

        # Movement
        if self.alien_phase_active:
            self.alien_elapsed += dt
            t = min(self.alien_elapsed / self.ALIEN_PHASE_DURATION, 1.0)
            st = t*t*(3-2*t)
            self.x = self.alien_start_x + (self.alien_target_x - self.alien_start_x)*st
            self.y = self.alien_start_y + (self.alien_target_y - self.alien_start_y)*st
            if t >= 1.0:
                self.alien_phase_active = False
        else:
            if self.thrust_active:
                speed_mult = CFG.POWERUP_SPEED_MULT if self.powerup_speed_active else 1.0
                self.vx += math.cos(self.angle) * self.thrust * self.joystick_mag * dt * speed_mult
                self.vy += math.sin(self.angle) * self.thrust * self.joystick_mag * dt * speed_mult

            speed = math.hypot(self.vx, self.vy)
            drag_c = self.drag_amt if self.frost_slow_timer <= 0 else self.drag_amt * 12
            if speed > 0:
                drag_force = drag_c * speed * speed * 0.001
                self.vx -= (self.vx/speed) * drag_force * dt
                self.vy -= (self.vy/speed) * drag_force * dt

            if self.type_special == SpecialType.DASH:
                self._update_dash(dt)
            if self.dash_cooldown > 0:
                self.dash_cooldown -= dt

            self.x += self.vx * dt
            self.y += self.vy * dt

        # Camera
        self.cam_x -= (self.cam_x - (self.x + self.vx * self.CAMERA_LOOKAHEAD)) * self.CAMERA_DAMP * dt
        self.cam_y -= (self.cam_y - (self.y + self.vy * self.CAMERA_LOOKAHEAD)) * self.CAMERA_DAMP * dt

        self._tick_particles(dt)

    # ── Abilities ──────────────────────────────────────────────────────────

    def activate_special(self):
        if self.is_dead: return
        sp = self.type_special
        if sp == SpecialType.DASH:
            self._dash()
        elif sp == SpecialType.MISSILE:
            if self.dash_cooldown <= 0:
                self._fire_missile()
                self.dash_cooldown = self.dash_cd_time
        elif sp == SpecialType.FIRERATE:
            if self.dash_cooldown <= 0:
                self.fire_rate_active    = True
                self.fire_rate_remaining = self.FIRE_RATE_DURATION
                self.dash_cooldown       = self.dash_cd_time
        elif sp == SpecialType.ALIEN:
            # Wraith: begin charging on key press (fires on release)
            if self.dash_cooldown <= 0 and not self.wraith_charging:
                self.wraith_charging     = True
                self.wraith_charge_timer = 0.0
                self.wraith_charge_locked= False
        elif sp == SpecialType.HEAL:
            if self.dash_cooldown <= 0:
                self.heal_active      = True
                self.heal_remaining   = self.HEAL_DURATION
                self.heal_accumulator = 0.0
                self.dash_cooldown    = self.dash_cd_time
        elif sp == SpecialType.NONE:   # Oppressor barrage
            self._fire_barrage()
        elif sp == SpecialType.CLOAK:
            if self.dash_cooldown <= 0:
                self.cloak_active    = True
                self.cloak_remaining = self.CLOAK_DURATION
                self.dash_cooldown   = self.dash_cd_time
        elif sp == SpecialType.LASER:
            if self.dash_cooldown <= 0:
                self.laser_special_active = True
                self.laser_special_timer  = 3.0
                self.dash_cooldown        = self.dash_cd_time
        elif sp == SpecialType.FROST:
            if self.dash_cooldown <= 0:
                self._fire_frost_missile()
                self.burst_schedule.append((0.5, "frost_missile"))
                self.dash_cooldown = self.dash_cd_time

    def release_special(self, wave_enemies=None):
        """Called on key-up. For Wraith: fires the blink if fully charged and aim is good."""
        if self.type_special != SpecialType.ALIEN:
            return
        if self.wraith_charging and self.wraith_charge_locked:
            # Fire only if aim cone is satisfied
            if self.wraith_aim_ok and wave_enemies is not None:
                self._wraith_blink_execute(wave_enemies)
            else:
                # Whiff — no teleport, short penalty cooldown (half the normal cd)
                self.dash_cooldown = self.dash_cd_time * 0.5
        # Reset charge regardless
        self.wraith_charging     = False
        self.wraith_charge_timer = 0.0
        self.wraith_charge_locked= False

    def _wraith_blink_execute(self, wave_enemies):
        """Teleport to nearest alive enemy, deal damage, heal for same amount."""
        alive = [e for e in wave_enemies if not e.is_dead]
        if not alive:
            return
        # Find nearest enemy within range
        best = None
        best_dist = self.WRAITH_BLINK_RANGE + 1
        for e in alive:
            d = math.hypot(e.x - self.x, e.y - self.y)
            if d < best_dist:
                best_dist = d
                best = e
        if best is None or best_dist > self.WRAITH_BLINK_RANGE:
            return

        # Skill check: must be facing target within aim window
        dx = best.x - self.x
        dy = best.y - self.y
        angle_to = math.atan2(dy, dx)
        diff_deg = abs(shortest_angle_diff(self.angle, angle_to)) * 180.0 / math.pi
        if diff_deg > self.WRAITH_BLINK_AIM_WINDOW:
            return  # missed the cone

        # Spawn afterimages at origin for visual flair
        for _ in range(6):
            self.afterimages.append(Afterimage(
                self.x + random.uniform(-10, 10),
                self.y + random.uniform(-10, 10),
                self.angle, self.current_sprite(), alpha=0.9
            ))

        # Teleport to just behind the enemy
        offset = 55.0
        self.x = best.x - math.cos(angle_to) * offset
        self.y = best.y - math.sin(angle_to) * offset

        # Velocity inherits a forward burst toward target
        self.vx = math.cos(angle_to) * 300
        self.vy = math.sin(angle_to) * 300

        # Deal damage
        dmg = self.WRAITH_BLINK_DAMAGE * self.powerup_damage_mult
        best.shield -= dmg

        # Lifesteal: heal for 100% of damage dealt
        heal_amt = min(dmg, self.max_shield - self.shield)
        self.shield = min(self.shield + heal_amt, self.max_shield)

        # Visual FX
        self.wraith_blink_fx_timer = 0.4
        self._spawn_explosion(self.x, self.y)
        for _ in range(4):
            self.afterimages.append(Afterimage(
                self.x + random.uniform(-15, 15),
                self.y + random.uniform(-15, 15),
                self.angle, self.current_sprite(), alpha=0.7
            ))

        # Kill feed notification
        self.kill_feed.insert(0, KillEntry(
            f"BLINK STRIKE  -{int(dmg)} dmg  +{int(heal_amt)} HP"
        ))

        # Successful blink: instantly refresh cooldown
        self.dash_cooldown = 0.0

    def activate_melee(self, wave_enemies=None):
        """Wraith F-key melee slash. Deals damage + stun if facing an enemy in range."""
        if self.type_special != SpecialType.ALIEN:
            return
        if self.wraith_melee_cooldown > 0:
            return  # still on cooldown

        # Trigger swing animation regardless of hit
        self.wraith_melee_anim_timer = 0.25
        self.wraith_melee_cooldown   = self.WRAITH_MELEE_COOLDOWN

        if wave_enemies is None:
            return

        # Check for enemies in melee cone
        hit_any = False
        for e in wave_enemies:
            if e.is_dead:
                continue
            dx = e.x - self.x
            dy = e.y - self.y
            dist = math.hypot(dx, dy)
            if dist > self.WRAITH_MELEE_RANGE:
                continue
            # Must be roughly facing
            angle_to = math.atan2(dy, dx)
            diff_deg = abs(shortest_angle_diff(self.angle, angle_to)) * 180.0 / math.pi
            if diff_deg > self.WRAITH_MELEE_AIM_DEG:
                continue

            # Combo multiplier
            combo_mult = min(self.WRAITH_MELEE_COMBO_MULT ** self.wraith_combo_count, 3.0)
            dmg = self.WRAITH_MELEE_DAMAGE * combo_mult * self.powerup_damage_mult
            e.shield -= dmg

            # Stun
            e.stun_timer       = self.WRAITH_MELEE_STUN_DUR
            e.stun_flash_timer = 0.3

            # Lifesteal: heal 40% of melee damage
            heal_amt = min(dmg * 0.4, self.max_shield - self.shield)
            self.shield = min(self.shield + heal_amt, self.max_shield)

            # Advance combo
            self.wraith_combo_count  = min(self.wraith_combo_count + 1, 3)
            self.wraith_combo_window = self.WRAITH_MELEE_COMBO_WINDOW

            # Hit FX at midpoint between player and enemy
            hx = self.x + dx * 0.5
            hy = self.y + dy * 0.5
            self.wraith_melee_hit_fx.append((hx, hy, 0.25))
            self._spawn_explosion(hx, hy)

            combo_str = f" x{self.wraith_combo_count} COMBO!" if self.wraith_combo_count > 1 else ""
            self.kill_feed.insert(0, KillEntry(
                f"MELEE HIT{combo_str}  -{int(dmg)} dmg  STUNNED  +{int(heal_amt)} HP"
            ))
            hit_any = True

        if not hit_any:
            # Whiff — no penalty, just the cooldown already set
            pass

    def _dash(self):
        if self.dash_cooldown > 0: return
        fwd = self.vx*math.cos(self.angle) + self.vy*math.sin(self.angle)
        dv  = max(0, 800 - fwd)
        self.dash_acceleration   = dv / self.DASH_DURATION
        self.dash_active         = True
        self.dash_time_remaining = self.DASH_DURATION
        self.dash_cooldown       = self.dash_cd_time

    def _update_dash(self, dt: float):
        if not self.dash_active: return
        self.drag_coefficient    = 0
        self.dash_time_remaining -= dt
        if self.dash_time_remaining > self.DASH_DURATION/2:
            self.vx += math.cos(self.angle) * (self.dash_acceleration + 1100) * dt
            self.vy += math.sin(self.angle) * (self.dash_acceleration + 1100) * dt
        # afterimage
        if not hasattr(self, '_dash_ai_timer'):
            self._dash_ai_timer = 0.0
        self._dash_ai_timer += dt
        if self._dash_ai_timer >= self.AFTERIMAGE_INTERVAL:
            self._dash_ai_timer = 0.0
            self.afterimages.append(Afterimage(self.x, self.y, self.angle, self.current_sprite()))
        if self.dash_time_remaining <= 0:
            self.dash_active = False

    # ── Firing ─────────────────────────────────────────────────────────────

    def _fire(self):
        sp = self.type_special
        if sp == SpecialType.LASER:
            self._fire_laser()
        elif sp == SpecialType.FROST:
            self._fire_frost_sphere()
        elif sp == SpecialType.NONE:
            self._fire_missile()
        elif sp == SpecialType.CLOAK:
            self._fire_burst_single()
        elif sp == SpecialType.ALIEN:
            self._fire_alien()
        else:
            self._fire_bullet()

    def _world_pos(self, lx: float, ly: float) -> Tuple[float,float]:
        return (self.x + math.cos(self.angle)*ly - math.sin(self.angle)*lx,
                self.y + math.sin(self.angle)*ly + math.cos(self.angle)*lx)

    def _fire_bullet(self):
        spread = random.uniform(-self.spread_amt, self.spread_amt) * math.pi/180
        a = self.angle + spread
        speed = 1000.0
        bx, by = self._world_pos(0, 30)
        self._spawn_bullet(bx, by, math.cos(a)*speed + self.vx, math.sin(a)*speed + self.vy)

    def _fire_alien(self):
        speed = 1000.0
        shots = [(10,30,self.angle),(-10,30,self.angle),(0,30,self.angle+math.pi/4),(0,30,self.angle-math.pi/4)]
        for lx,ly,a in shots:
            bx,by = self._world_pos(lx, ly)
            self._spawn_bullet(bx, by, math.cos(a)*speed+self.vx, math.sin(a)*speed+self.vy)

    def _fire_laser(self):
        lx, ly = self._world_pos(0, 30)
        laser = Laser(str(uuid.uuid4()), lx, ly, self.angle,
                      special=self.laser_special_active, mine=True)
        self.lasers.append(laser)
        self.flashes.append(MuzzleFlash(lx, ly, attached=True, is_laser=True))

    def _fire_frost_sphere(self):
        speed = 800.0
        bx = self.x + math.cos(self.angle)*30
        by = self.y + math.sin(self.angle)*30
        vx = math.cos(self.angle)*speed + self.vx
        vy = math.sin(self.angle)*speed + self.vy
        orig_angle = math.atan2(vy, vx)
        orig_speed = math.hypot(vx, vy)
        for d in [-2,-1,0,1,2]:
            sa = orig_angle + d*(20*math.pi/180)
            b = Bullet(str(uuid.uuid4()), bx, by,
                       vx, vy, self.bullet_dmg,
                       owner_name="player",
                       is_frost_sphere=True, has_burst=False,
                       burst_timer=0.4, curve_dir=float(d))
            self.bullets.append(b)
        self.flashes.append(MuzzleFlash(bx, by, attached=True))

    def _fire_burst_single(self):
        speed = 1000.0
        bx, by = self._world_pos(0, 30)
        self._spawn_bullet(bx, by, math.cos(self.angle)*speed+self.vx, math.sin(self.angle)*speed+self.vy)
        self._reveal_cloak_briefly()

    def _fire_missile(self):
        mx = self.x + math.cos(self.angle)*40
        my = self.y + math.sin(self.angle)*40
        fwd = max(0, self.vx*math.cos(self.angle)+self.vy*math.sin(self.angle))
        m = Missile(str(uuid.uuid4()), self.player_id,
                    mx, my, self.angle, 65, speed=fwd+500, owner_name="player")
        self.missiles.append(m)
        self.flashes.append(MuzzleFlash(mx, my, attached=True))

    def _fire_frost_missile(self):
        mx = self.x + math.cos(self.angle)*40
        my = self.y + math.sin(self.angle)*40
        fwd = max(0, self.vx*math.cos(self.angle)+self.vy*math.sin(self.angle))
        m = Missile(str(uuid.uuid4()), self.player_id,
                    mx, my, self.angle, 15, speed=fwd+200, owner_name="player", is_frost=True)
        self.missiles.append(m)
        self.flashes.append(MuzzleFlash(mx, my, attached=True))

    def _fire_barrage(self):
        if self.dash_cooldown > 0: return
        self.dash_cooldown = self.dash_cd_time
        # schedule 16 shots over 0.8s
        for i in range(16):
            self.burst_schedule.append((i * 0.05, "barrage"))

    def _process_burst(self, dt: float):
        remaining = []
        for timer, kind in self.burst_schedule:
            new_t = timer - dt
            if new_t <= 0:
                if kind == "barrage":
                    speed = 1000.0
                    for lx in [10, -10]:
                        bx, by = self._world_pos(lx, 30)
                        self._spawn_bullet(bx, by, math.cos(self.angle)*speed+self.vx,
                                           math.sin(self.angle)*speed+self.vy)
                elif kind == "frost_missile":
                    self._fire_frost_missile()
            else:
                remaining.append((new_t, kind))
        self.burst_schedule = remaining

    def _spawn_bullet(self, x: float, y: float, vx: float, vy: float):
        dmg = self.bullet_dmg * self.powerup_damage_mult
        b = Bullet(str(uuid.uuid4()), x, y, vx, vy, dmg, owner_name="player")
        self.bullets.append(b)
        self.flashes.append(MuzzleFlash(x, y, attached=True))

    # ── Particles & physics ────────────────────────────────────────────────

    def _tick_particles(self, dt: float):
        # Afterimages
        self.afterimages = [a for a in self.afterimages if a.lifetime > 0]
        for a in self.afterimages:
            a.lifetime -= dt
            a.alpha = max(0, a.lifetime * 0.8)

        # Lasers
        for l in self.lasers: l.lifetime -= dt
        self.lasers = [l for l in self.lasers if l.lifetime > 0]

        # Flashes
        for f in self.flashes: f.frame += 1
        self.flashes = [f for f in self.flashes if f.frame < 4]

        # Explosions
        for e in self.explosions: e.frame += 1
        self.explosions = [e for e in self.explosions if e.frame < 6]

        self._update_bullets(dt)
        self._update_missiles(dt)

        # Kill feed
        for kf in self.kill_feed: kf.timer -= dt
        self.kill_feed = [kf for kf in self.kill_feed if kf.timer > -1.0]

    def _update_bullets(self, dt: float):
        player_radius = 30 if self.type_special == SpecialType.NONE else 24
        surviving = []
        for b in self.bullets:
            # Pre-burst frost sphere
            if b.is_frost_sphere and not b.has_burst:
                b.burst_timer -= dt
                if b.burst_timer <= 0:
                    orig_a = math.atan2(b.vy, b.vx)
                    orig_s = math.hypot(b.vx, b.vy)
                    sa = orig_a + b.curve_dir*(20*math.pi/180)
                    b2 = Bullet(b.id, b.x, b.y, math.cos(sa)*orig_s, math.sin(sa)*orig_s,
                                b.damage, owner_name=b.owner_name,
                                is_frost_sphere=True, has_burst=True, curve_dir=b.curve_dir)
                    surviving.append(b2)
                    continue
                b.x += b.vx*dt; b.y += b.vy*dt; b.lifetime -= dt
                if b.lifetime > 0: surviving.append(b)
                continue

            # Post-burst frost curve
            if b.is_frost_sphere and b.has_burst and b.curve_dir != 0:
                ba = math.atan2(b.vy, b.vx)
                cf = 180.0
                b.vx += -math.sin(ba)*b.curve_dir*cf*dt
                b.vy +=  math.cos(ba)*b.curve_dir*cf*dt

            b.x += b.vx*dt; b.y += b.vy*dt; b.lifetime -= dt
            if b.lifetime <= 0:
                self.flashes.append(MuzzleFlash(b.x, b.y))
                continue
            surviving.append(b)
        self.bullets = surviving

    def _update_missiles(self, dt: float):
        surviving = []
        for m in self.missiles:
            if m.owner_id == self.player_id:
                m.lifetime -= dt
                if m.lifetime <= 0:
                    self._spawn_explosion(m.x, m.y)
                    continue
                # No remote players to home into in single-player context
                # (AI handles its own missiles; player missiles target AI enemy)
                target_speed = self.FROST_MISSILE_SPEED if m.is_frost else self.MISSILE_TARGET_SPEED
                accel        = self.FROST_MISSILE_ACCEL  if m.is_frost else self.MISSILE_ACCEL
                m.speed += (target_speed - m.speed) * accel * dt
                m.x += math.cos(m.angle) * m.speed * dt
                m.y += math.sin(m.angle) * m.speed * dt
            surviving.append(m)
        self.missiles = surviving

    def _spawn_explosion(self, x: float, y: float, big: bool = False):
        count = random.randint(4, 6) if big else random.randint(3, 5)
        for _ in range(count):
            self.explosions.append(Explosion(
                x + random.uniform(-15,15), y + random.uniform(-15,15),
                random.uniform(200,250) if big else random.uniform(150,200),
                random.randint(-4, 0)
            ))

    # ── Damage ─────────────────────────────────────────────────────────────

    def receive_damage(self, damage: float, killer: str, weapon: str):
        if self.is_dead: return
        if self.alien_phase_active: return
        if self.powerup_invincible_timer > 0: return   # powerup invincibility
        if self.cloak_active and self.cloak_reveal_remaining <= 0: return  # cloak immunity
        actual = damage * (0.5 if self.fire_rate_active else 1.0)
        self.shield -= actual
        self.shield  = max(self.shield, 0)
        self._reveal_cloak_briefly()
        if self.shield <= 0:
            self.kill_feed.insert(0, KillEntry(f"{killer} killed you with {weapon}"))
            self._die()

    def _die(self):
        if self.is_dead: return
        self.is_dead   = True
        self.death_timer = 3.0
        self._spawn_explosion(self.x, self.y, big=True)

    def _reveal_cloak_briefly(self):
        if self.cloak_active:
            self.cloak_reveal_remaining = self.CLOAK_REVEAL_DURATION

    def current_sprite(self) -> str:
        if self.cloak_active and self.cloak_reveal_remaining <= 0:
            return "empty"
        if self.dash_active and self.type_special == SpecialType.DASH:
            return "playerSprite1"
        if not self.thrust_active:
            return self.idle_sprite
        return self.moving_sprites[self.sprite_inc % len(self.moving_sprites)]

    def collect_powerup(self, kind: PowerupType):
        """Apply the effect of collecting a powerup."""
        if kind == PowerupType.SHIELD:
            self.shield = min(self.shield + CFG.POWERUP_SHIELD_RESTORE, self.max_shield)
            self.kill_feed.insert(0, KillEntry("⚡ Shield restored!"))
        elif kind == PowerupType.FIRERATE:
            self.powerup_firerate_timer = CFG.POWERUP_FIRERATE_DUR
            self.kill_feed.insert(0, KillEntry("⚡ Rapid fire!"))
        elif kind == PowerupType.SPEED:
            self.powerup_speed_timer = CFG.POWERUP_SPEED_DUR
            self.kill_feed.insert(0, KillEntry("⚡ Speed boost!"))
        elif kind == PowerupType.DAMAGE:
            self.powerup_damage_timer = CFG.POWERUP_DAMAGE_DUR
            self.kill_feed.insert(0, KillEntry("⚡ Damage boost!"))
        elif kind == PowerupType.INVINCIBLE:
            self.powerup_invincible_timer = CFG.POWERUP_SHIELD_MAX_DUR
            self.kill_feed.insert(0, KillEntry("⚡ Invincible!"))

    # ── Missile targeting (called from game loop with AI position) ─────────

    def home_missiles(self, targets: List[Tuple[float,float,str]], dt: float):
        """Update homing on player missiles toward given targets [(x, y, id)]."""
        for m in self.missiles:
            if m.owner_id != self.player_id: continue
            if not targets: continue
            tx, ty, _ = min(targets, key=lambda t: (t[0]-m.x)**2+(t[1]-m.y)**2)
            desired = math.atan2(ty-m.y, tx-m.x)
            diff = shortest_angle_diff(m.angle, desired)
            max_turn = self.MISSILE_TURN_RATE * dt * m.speed / 1500
            m.angle += max(-max_turn, min(max_turn, diff))


# ─────────────────────────────────────────────────────────────────────────────
# AI ENEMY
# ─────────────────────────────────────────────────────────────────────────────

# AI constants
AI_FIRE_RANGE    = CFG.AI_FIRE_RANGE
AI_SPECIAL_RANGE = CFG.AI_ORBIT_RADIUS
AI_WANDER_INTV   = 3.0
AI_ORBIT_RADIUS  = CFG.AI_ORBIT_RADIUS
AI_ORBIT_STRAFE  = CFG.AI_ORBIT_STRAFE
AI_MIN_RETREAT   = 100
AI_RETREAT_THRUST= 1.2
AI_AIM_TOL_DEG   = CFG.AI_AIM_TOL_DEG
AI_DODGE_FLIP    = (1.5, 3.0)
AI_RESPAWN_DELAY = CFG.AI_RESPAWN_DELAY

class AIEnemy:
    MISSILE_TURN_RATE        = 2.5
    MISSILE_TARGET_SPEED     = 1200
    MISSILE_ACCEL            = 1.0
    FROST_MISSILE_SPEED      = 1800
    FROST_MISSILE_ACCEL      = 0.35
    ALIEN_PHASE_DURATION     = 0.2
    ALIEN_PHASE_DISTANCE     = 500
    CLOAK_DURATION           = 5.0
    DASH_DURATION            = 0.2
    FIRE_RATE_DURATION       = 5.0
    HEAL_DURATION            = 1.0
    HEAL_TICK_INTERVAL       = 0.1

    def __init__(self, previous_ship_name: str = ""):
        self.id = str(uuid.uuid4())
        # Pick ship avoiding the previous one
        candidates = [s for s in AI_SHIP_ROSTER if s.name != previous_ship_name]
        self.ship = random.choice(candidates if candidates else AI_SHIP_ROSTER)
        # Apply handicap: normal AIs are weaker than the player
        self.shield      = self.ship.shield * CFG.AI_HEALTH_MULT
        self._max_shield = self.shield
        self._dmg_mult   = CFG.AI_DAMAGE_MULT    # applied when firing
        self._fr_mult    = CFG.AI_FIRE_RATE_MULT  # applied to fire interval

        self.x = float(random.randint(-600, 600))
        self.y = float(random.randint(-600, 600))
        self.angle     = random.uniform(-math.pi, math.pi)
        self.aim_angle = self.angle
        self.vx = self.vy = 0.0
        self.is_dead = False
        self.respawn_timer = 0.0
        self.previous_ship_name = ""

        self.bullets:  List[Bullet]  = []
        self.missiles: List[Missile] = []
        self.lasers:   List[Laser]   = []
        self.flashes:  List[MuzzleFlash] = []
        self.explosions: List[Explosion] = []
        self.kill_feed: List[KillEntry] = []

        self.frame_count = 0
        self.time_since_shot = 0.0
        self.dash_cooldown = 0.0

        self.fire_rate_active     = False; self.fire_rate_remaining = 0.0
        self.heal_active          = False; self.heal_remaining = 0.0; self.heal_accumulator = 0.0
        self.cloak_active         = False; self.cloak_remaining = 0.0
        self.alien_phase_active   = False; self.alien_elapsed = 0.0
        self.alien_start_x = self.alien_start_y = 0.0
        self.alien_target_x = self.alien_target_y = 0.0
        self.laser_special_active = False; self.laser_special_timer = 0.0
        self.frost_slow_timer     = 0.0
        self.burst_schedule: List[Tuple[float,str]] = []

        # Stun state (applied by Wraith melee)
        self.stun_timer           = 0.0   # > 0 means stunned
        self.stun_flash_timer     = 0.0   # visual flash on stun

        self.wander_timer = AI_WANDER_INTV
        self.wander_angle = random.uniform(-math.pi, math.pi)
        self.dodge_sign   = 1.0
        self.dodge_timer  = random.uniform(*AI_DODGE_FLIP)

        self.prev_target_pos: Optional[Tuple[float,float]] = None
        self.est_vel: Tuple[float,float] = (0.0, 0.0)

        self.sprite_inc = 0
        self.anim_timer = 0.0
        self.thrust_active = False

    # ── Tick ───────────────────────────────────────────────────────────────

    def tick(self, dt: float, player_x: float, player_y: float,
             player_bullets: List[Bullet], player_missiles: List[Missile]):
        if self.is_dead:
            self.respawn_timer -= dt
            self._tick_particles(dt)
            return

        self.frame_count += 1

        self._update_velocity_estimate(player_x, player_y, dt)
        self._update_timers(dt)
        self._update_behaviour(dt, player_x, player_y)
        self._update_missiles_owned(dt, player_x, player_y)
        # Note: bullet hit detection is done externally by check_player_attacks_ai
        self._process_burst(dt)

        # Particle updates
        self._tick_particles(dt)

    def _tick_particles(self, dt: float):
        for f in self.flashes: f.frame += 1
        self.flashes = [f for f in self.flashes if f.frame < 4]
        for e in self.explosions: e.frame += 1
        self.explosions = [e for e in self.explosions if e.frame < 6]
        for l in self.lasers: l.lifetime -= dt
        self.lasers = [l for l in self.lasers if l.lifetime > 0]
        # Bullet movement
        surviving = []
        for b in self.bullets:
            if b.is_frost_sphere and not b.has_burst:
                b.burst_timer -= dt
                if b.burst_timer <= 0:
                    orig_a = math.atan2(b.vy, b.vx)
                    orig_s = math.hypot(b.vx, b.vy)
                    sa = orig_a + b.curve_dir*(20*math.pi/180)
                    surviving.append(Bullet(b.id, b.x, b.y,
                                            math.cos(sa)*orig_s, math.sin(sa)*orig_s,
                                            b.damage, owner_name="AI",
                                            is_frost_sphere=True, has_burst=True, curve_dir=b.curve_dir))
                    continue
                b.x += b.vx*dt; b.y += b.vy*dt; b.lifetime -= dt
                if b.lifetime > 0: surviving.append(b)
                continue
            b.x += b.vx*dt; b.y += b.vy*dt; b.lifetime -= dt
            if b.lifetime > 0: surviving.append(b)
        self.bullets = surviving

    def _update_velocity_estimate(self, px: float, py: float, dt: float):
        if dt > 0 and self.prev_target_pos:
            raw_vx = (px - self.prev_target_pos[0]) / dt
            raw_vy = (py - self.prev_target_pos[1]) / dt
            alpha  = 0.3
            self.est_vel = (self.est_vel[0] + alpha*(raw_vx - self.est_vel[0]),
                            self.est_vel[1] + alpha*(raw_vy - self.est_vel[1]))
        self.prev_target_pos = (px, py)

    def _predictive_aim(self, tx: float, ty: float, bullet_speed: float) -> Optional[float]:
        tvx, tvy = self.est_vel
        dx, dy = tx-self.x, ty-self.y
        s = bullet_speed
        a = tvx*tvx + tvy*tvy - s*s
        b = 2*(dx*tvx + dy*tvy)
        c = dx*dx + dy*dy
        if abs(a) < 1e-4:
            if abs(b) < 1e-4: return None
            t0 = -c/b
            if t0 <= 0: return None
            t = t0
        else:
            disc = b*b - 4*a*c
            if disc < 0: return None
            sq = math.sqrt(disc)
            candidates = [x for x in [(-b-sq)/(2*a), (-b+sq)/(2*a)] if x > 0]
            if not candidates: return None
            t = min(candidates)
        if t >= 3: return None
        return math.atan2(ty+tvy*t-self.y, tx+tvx*t-self.x)

    def _update_timers(self, dt: float):
        if self.dash_cooldown > 0:   self.dash_cooldown   -= dt
        if self.frost_slow_timer > 0: self.frost_slow_timer -= dt
        # Stun tick
        if self.stun_timer > 0:
            self.stun_timer -= dt
        if self.stun_flash_timer > 0:
            self.stun_flash_timer -= dt
        self.dodge_timer -= dt
        if self.dodge_timer <= 0:
            self.dodge_timer = random.uniform(*AI_DODGE_FLIP)
            self.dodge_sign  = random.choice([-1.0, 1.0])
        if self.fire_rate_active:
            self.fire_rate_remaining -= dt
            if self.fire_rate_remaining <= 0: self.fire_rate_active = False
        if self.heal_active:
            self.heal_remaining   -= dt; self.heal_accumulator += dt
            while self.heal_accumulator >= self.HEAL_TICK_INTERVAL:
                self.heal_accumulator -= self.HEAL_TICK_INTERVAL
                self.shield = min(self.shield + CFG.AI_HEAL_TICK_HP, self._max_shield)
            if self.heal_remaining <= 0: self.heal_active = False
        if self.cloak_active:
            self.cloak_remaining -= dt
            if self.cloak_remaining <= 0: self.cloak_active = False
        if self.laser_special_active:
            self.laser_special_timer -= dt
            if self.laser_special_timer <= 0: self.laser_special_active = False

        # Passive regeneration (all ships): 2 HP/s, does not stack with active heal
        if not self.heal_active:
            self.shield = min(self.shield + CFG.AI_PASSIVE_REGEN * dt, self._max_shield)

    def _update_behaviour(self, dt: float, px: float, py: float):
        # Stunned: freeze movement and firing
        if self.stun_timer > 0:
            # Decelerate but don't move intentionally
            self.vx *= max(0.0, 1.0 - 4.0 * dt)
            self.vy *= max(0.0, 1.0 - 4.0 * dt)
            self.x  += self.vx * dt
            self.y  += self.vy * dt
            return

        dx, dy = px-self.x, py-self.y
        dist   = math.hypot(dx, dy)

        self.aim_angle = self._predictive_aim(px, py, 1000.0) or math.atan2(dy, dx)
        aim_error = abs(shortest_angle_diff(self.angle, self.aim_angle))
        tol_rad   = AI_AIM_TOL_DEG * math.pi/180

        if dist > AI_FIRE_RANGE:
            # Approach / orbit
            if dist < AI_MIN_RETREAT:
                target_a = math.atan2(-dy, -dx)
            elif dist < AI_ORBIT_RADIUS:
                facing_a = math.atan2(dy, dx)
                perp_a   = facing_a + math.pi/2
                target_a = facing_a*(1-AI_ORBIT_STRAFE) + perp_a*AI_ORBIT_STRAFE
            else:
                target_a = math.atan2(dy, dx)
            self.angle += shortest_angle_diff(self.angle, target_a) * self.ship.turn * dt
            thrust_scale = 1.0 if dist > AI_ORBIT_RADIUS else 0.4
            self._apply_physics(self.angle, thrust_scale, dt)
        else:
            # Combat mode
            self.angle += shortest_angle_diff(self.angle, self.aim_angle) * self.ship.turn * dt
            bearing    = math.atan2(dy, dx)
            strafe_a   = bearing + self.dodge_sign * math.pi/2
            fwd_bias   = 0.0
            if dist < AI_MIN_RETREAT:
                fwd_bias = -AI_RETREAT_THRUST
            elif dist > AI_ORBIT_RADIUS:
                fwd_bias = 0.3
            thrust_x = math.cos(strafe_a) + math.cos(bearing)*fwd_bias
            thrust_y = math.sin(strafe_a) + math.sin(bearing)*fwd_bias
            mag = math.hypot(thrust_x, thrust_y)
            if mag > 0:
                thrust_x /= mag; thrust_y /= mag
            self.vx += thrust_x * self.ship.thrust * dt
            self.vy += thrust_y * self.ship.thrust * dt

            # Shoot if aimed
            if aim_error < tol_rad:
                self.time_since_shot += dt
                eff_int = self.ship.fire_interval * self._fr_mult * (0.5 if self.fire_rate_active else 1.0)
                if self.time_since_shot >= eff_int:
                    self._ai_fire()
                    self.time_since_shot = 0.0

            # Use special
            if dist < AI_SPECIAL_RANGE and self.dash_cooldown <= 0:
                self._use_special(px, py)

        # Drag
        speed = math.hypot(self.vx, self.vy)
        drag_c = self.ship.drag_amt * (12 if self.frost_slow_timer > 0 else 1)
        if speed > 0:
            df = drag_c * speed * speed * 0.001
            self.vx -= (self.vx/speed)*df*dt
            self.vy -= (self.vy/speed)*df*dt

        self.x += self.vx*dt
        self.y += self.vy*dt

        # Sprite animation
        self.thrust_active = True
        self.anim_timer += dt
        if self.anim_timer > 0.1:
            self.sprite_inc += 1
            self.anim_timer  = 0.0

    def _apply_physics(self, thrust_angle: float, scale: float, dt: float):
        self.vx += math.cos(thrust_angle) * self.ship.thrust * scale * dt
        self.vy += math.sin(thrust_angle) * self.ship.thrust * scale * dt

    def _ai_fire(self):
        sp = self.ship.special
        if sp == SpecialType.LASER:
            self._ai_fire_laser()
        elif sp == SpecialType.FROST:
            self._ai_fire_frost_sphere()
        elif sp == SpecialType.NONE:
            self._ai_fire_missile()
        elif sp == SpecialType.ALIEN:
            self._ai_fire_alien()
        else:
            self._ai_fire_bullet()

    def _ai_fire_bullet(self):
        spread = random.uniform(-self.ship.spread_amt, self.ship.spread_amt)*math.pi/180
        a = self.aim_angle + spread
        speed = 1000.0
        bx = self.x + math.cos(self.aim_angle)*30
        by = self.y + math.sin(self.aim_angle)*30
        b = Bullet(str(uuid.uuid4()), bx, by,
                   math.cos(a)*speed+self.vx, math.sin(a)*speed+self.vy,
                   self.ship.bullet_dmg * self._dmg_mult, owner_name="AI")
        self.bullets.append(b)
        self.flashes.append(MuzzleFlash(bx, by))

    def _ai_fire_alien(self):
        speed = 1000.0
        for da in [0, 0, math.pi/4, -math.pi/4]:
            a = self.aim_angle + da
            bx = self.x + math.cos(self.aim_angle)*30
            by = self.y + math.sin(self.aim_angle)*30
            b = Bullet(str(uuid.uuid4()), bx, by,
                       math.cos(a)*speed+self.vx, math.sin(a)*speed+self.vy,
                       self.ship.bullet_dmg * self._dmg_mult, owner_name="AI")
            self.bullets.append(b)
        self.flashes.append(MuzzleFlash(self.x, self.y))

    def _ai_fire_laser(self):
        lx = self.x + math.cos(self.aim_angle)*30
        ly = self.y + math.sin(self.aim_angle)*30
        laser = Laser(str(uuid.uuid4()), lx, ly, self.aim_angle,
                      special=self.laser_special_active, owner_name="AI")
        self.lasers.append(laser)
        self.flashes.append(MuzzleFlash(lx, ly, is_laser=True))

    def _ai_fire_frost_sphere(self):
        speed = 800.0
        bx = self.x + math.cos(self.aim_angle)*30
        by = self.y + math.sin(self.aim_angle)*30
        vx = math.cos(self.aim_angle)*speed + self.vx
        vy = math.sin(self.aim_angle)*speed + self.vy
        for d in [-2,-1,0,1,2]:
            b = Bullet(str(uuid.uuid4()), bx, by, vx, vy,
                       self.ship.bullet_dmg * self._dmg_mult, owner_name="AI",
                       is_frost_sphere=True, has_burst=False, burst_timer=0.4, curve_dir=float(d))
            self.bullets.append(b)
        self.flashes.append(MuzzleFlash(bx, by))

    def _ai_fire_missile(self):
        mx = self.x + math.cos(self.aim_angle)*40
        my = self.y + math.sin(self.aim_angle)*40
        fwd = max(0, self.vx*math.cos(self.angle)+self.vy*math.sin(self.angle))
        m = Missile(str(uuid.uuid4()), self.id, mx, my, self.aim_angle,
                    65 * self._dmg_mult, speed=fwd+500, owner_name="AI")
        self.missiles.append(m)
        self.flashes.append(MuzzleFlash(mx, my))

    def _use_special(self, px: float, py: float):
        sp = self.ship.special
        if sp == SpecialType.FIRERATE:
            self.fire_rate_active    = True
            self.fire_rate_remaining = self.FIRE_RATE_DURATION
            self.dash_cooldown       = self.ship.special_cooldown
        elif sp == SpecialType.HEAL:
            self.heal_active      = True
            self.heal_remaining   = self.HEAL_DURATION
            self.heal_accumulator = 0.0
            self.dash_cooldown    = self.ship.special_cooldown
        elif sp == SpecialType.MISSILE:
            self._ai_fire_missile()
            self.dash_cooldown = self.ship.special_cooldown
        elif sp == SpecialType.LASER:
            self.laser_special_active = True
            self.laser_special_timer  = 3.0
            self.dash_cooldown        = self.ship.special_cooldown
        elif sp == SpecialType.FROST:
            self._ai_fire_frost_missile(px, py)
            self.burst_schedule.append((0.5, "frost_missile"))
            self.dash_cooldown = self.ship.special_cooldown
        elif sp == SpecialType.ALIEN:
            self.alien_phase_active = True
            self.alien_elapsed      = 0.0
            self.alien_start_x      = self.x
            self.alien_start_y      = self.y
            self.alien_target_x     = self.x + math.cos(self.angle)*self.ALIEN_PHASE_DISTANCE
            self.alien_target_y     = self.y + math.sin(self.angle)*self.ALIEN_PHASE_DISTANCE
            self.dash_cooldown      = self.ship.special_cooldown
        elif sp == SpecialType.CLOAK:
            self.cloak_active    = True
            self.cloak_remaining = self.CLOAK_DURATION
            self.dash_cooldown   = self.ship.special_cooldown
        elif sp == SpecialType.NONE:
            for i in range(16):
                self.burst_schedule.append((i*0.05, "barrage"))
            self.dash_cooldown = self.ship.special_cooldown

    def _ai_fire_frost_missile(self, tx: float, ty: float):
        mx = self.x + math.cos(self.angle)*40
        my = self.y + math.sin(self.angle)*40
        fwd = max(0, self.vx*math.cos(self.angle)+self.vy*math.sin(self.angle))
        m = Missile(str(uuid.uuid4()), self.id, mx, my, self.angle, 15,
                    speed=fwd+200, owner_name="AI", is_frost=True)
        self.missiles.append(m)

    def _update_missiles_owned(self, dt: float, px: float, py: float):
        surviving = []
        for m in self.missiles:
            if m.owner_id != self.id:
                surviving.append(m); continue
            m.lifetime -= dt
            if m.lifetime <= 0:
                self._spawn_explosion(m.x, m.y); continue
            # Home toward player
            desired = math.atan2(py-m.y, px-m.x)
            diff = shortest_angle_diff(m.angle, desired)
            max_turn = self.MISSILE_TURN_RATE * dt * m.speed / 1500
            m.angle += max(-max_turn, min(max_turn, diff))
            ts = self.FROST_MISSILE_SPEED if m.is_frost else self.MISSILE_TARGET_SPEED
            ac = self.FROST_MISSILE_ACCEL  if m.is_frost else self.MISSILE_ACCEL
            m.speed += (ts - m.speed)*ac*dt
            m.x += math.cos(m.angle)*m.speed*dt
            m.y += math.sin(m.angle)*m.speed*dt
            surviving.append(m)
        self.missiles = surviving

    def _check_bullet_hits(self, player_bullets: List[Bullet]):
        """Check if any player bullet hits the AI."""
        if self.is_dead: return
        hit_ids = set()
        for b in player_bullets:
            dx, dy = self.x-b.x, self.y-b.y
            if dx*dx+dy*dy < (28+5)**2:
                self.shield -= b.damage
                hit_ids.add(b.id)
                if b.is_frost_sphere:
                    spd = math.hypot(self.vx, self.vy)
                    if spd > 0:
                        ns = max(0, spd-100)
                        self.vx = self.vx/spd*ns
                        self.vy = self.vy/spd*ns
        if self.shield <= 0 and not self.is_dead:
            self.is_dead = True
            self._spawn_explosion(self.x, self.y, big=True)
            self.respawn_timer = AI_RESPAWN_DELAY
            self.previous_ship_name = self.ship.name
        return hit_ids  # so caller can remove bullets

    def _process_burst(self, dt: float):
        remaining = []
        for timer, kind in self.burst_schedule:
            new_t = timer - dt
            if new_t <= 0:
                if kind == "barrage":
                    speed = 1000.0
                    for lx in [10, -10]:
                        bx = self.x + math.cos(self.aim_angle)*30 - math.sin(self.aim_angle)*lx
                        by = self.y + math.sin(self.aim_angle)*30 + math.cos(self.aim_angle)*lx
                        b = Bullet(str(uuid.uuid4()), bx, by,
                                   math.cos(self.aim_angle)*speed, math.sin(self.aim_angle)*speed,
                                   self.ship.bullet_dmg * self._dmg_mult, owner_name="AI")
                        self.bullets.append(b)
                elif kind == "frost_missile":
                    if self.prev_target_pos:
                        self._ai_fire_frost_missile(*self.prev_target_pos)
            else:
                remaining.append((new_t, kind))
        self.burst_schedule = remaining

    def respawn(self):
        """Properly reset AI with a new ship."""
        prev_name = self.ship.name
        new_ai = AIEnemy(previous_ship_name=prev_name)
        # Copy only the necessary fields, keep position logic clean
        for key in ['x', 'y', 'vx', 'vy', 'angle', 'previous_ship_name']:
            if hasattr(self, key):
                setattr(new_ai, key, getattr(self, key))
                self.__dict__.update(new_ai.__dict__)
    def _spawn_explosion(self, x: float, y: float, big: bool = False):
        count = random.randint(4,6) if big else random.randint(3,5)
        for _ in range(count):
            self.explosions.append(Explosion(
                x+random.uniform(-15,15), y+random.uniform(-15,15),
                random.uniform(200,250) if big else random.uniform(150,200),
                random.randint(-4,0)
            ))

    def current_sprite(self) -> str:
        if self.is_dead: return self.ship.idle_sprite
        return self.ship.moving_sprites[self.sprite_inc % len(self.ship.moving_sprites)]


# ─────────────────────────────────────────────────────────────────────────────
# BOSS AI  (inherits AIEnemy, boosted stats)
# ─────────────────────────────────────────────────────────────────────────────

class BossAI(AIEnemy):
    def __init__(self, previous_ship_name: str = ""):
        super().__init__(previous_ship_name)
        self.is_boss = True
        # Override the normal-AI handicap with boss-specific multipliers
        self.shield      = self.ship.shield * CFG.BOSS_HEALTH_MULT
        self._max_shield = self.shield
        self._dmg_mult   = CFG.BOSS_DAMAGE_MULT
        self._fr_mult    = CFG.BOSS_FIRE_RATE_MULT   # < 1 = faster than normal
        self._spd_mult   = CFG.BOSS_SPEED_MULT
        self.display_scale = CFG.BOSS_SCALE_DISPLAY

    # Override fire methods to scale damage
    def _ai_fire_bullet(self):
        spread = random.uniform(-self.ship.spread_amt, self.ship.spread_amt)*math.pi/180
        a = self.aim_angle + spread
        speed = 1000.0
        bx = self.x + math.cos(self.aim_angle)*30
        by = self.y + math.sin(self.aim_angle)*30
        b = Bullet(str(uuid.uuid4()), bx, by,
                   math.cos(a)*speed+self.vx, math.sin(a)*speed+self.vy,
                   self.ship.bullet_dmg * self._dmg_mult, owner_name="AI")
        self.bullets.append(b)
        self.flashes.append(MuzzleFlash(bx, by))

    def _ai_fire_missile(self):
        mx = self.x + math.cos(self.aim_angle)*40
        my = self.y + math.sin(self.aim_angle)*40
        fwd = max(0, self.vx*math.cos(self.angle)+self.vy*math.sin(self.angle))
        m = Missile(str(uuid.uuid4()), self.id, mx, my, self.aim_angle,
                    65 * self._dmg_mult, speed=fwd+500, owner_name="AI")
        self.missiles.append(m)
        self.flashes.append(MuzzleFlash(mx, my))

    def _apply_physics(self, thrust_angle: float, scale: float, dt: float):
        self.vx += math.cos(thrust_angle) * self.ship.thrust * scale * dt * self._spd_mult
        self.vy += math.sin(thrust_angle) * self.ship.thrust * scale * dt * self._spd_mult


# ─────────────────────────────────────────────────────────────────────────────
# POWERUP MANAGER
# ─────────────────────────────────────────────────────────────────────────────

class PowerupManager:
    _KINDS = list(PowerupType)
    _COLORS = {
        PowerupType.SHIELD:    (0, 220, 100),
        PowerupType.FIRERATE:  (255, 80, 200),
        PowerupType.SPEED:     (80, 200, 255),
        PowerupType.DAMAGE:    (255, 160, 0),
        PowerupType.INVINCIBLE:(220, 220, 50),
    }
    _LABELS = {
        PowerupType.SHIELD:    "HP",
        PowerupType.FIRERATE:  "FIRE",
        PowerupType.SPEED:     "SPD",
        PowerupType.DAMAGE:    "DMG",
        PowerupType.INVINCIBLE:"INV",
    }

    def __init__(self):
        self.powerups: List[Powerup] = []
        self.spawn_timer = CFG.POWERUP_SPAWN_INTERVAL * 0.4  # first one sooner

    def update(self, dt: float, engine: 'GameEngine', kill_positions: List[Tuple[float,float]]):
        """Update timers, auto-spawn, and check collection. Call each frame."""
        # Tick lifetimes
        self.powerups = [p for p in self.powerups if p.lifetime > 0]
        for p in self.powerups:
            p.lifetime -= dt
            p.pulse    += dt * 3.0

        # Auto-spawn on timer
        self.spawn_timer -= dt
        if self.spawn_timer <= 0 and len(self.powerups) < CFG.POWERUP_MAX_ON_MAP:
            self.spawn_timer = CFG.POWERUP_SPAWN_INTERVAL
            self._spawn_random(engine.x, engine.y)

        # Spawn on enemy kills
        for kx, ky in kill_positions:
            if len(self.powerups) < CFG.POWERUP_MAX_ON_MAP and random.random() < 0.65:
                self._spawn_at(kx, ky)

        # Collection check
        for p in self.powerups[:]:
            dx = engine.x - p.x
            dy = engine.y - p.y
            if dx*dx + dy*dy < CFG.POWERUP_COLLECT_RADIUS**2:
                engine.collect_powerup(p.kind)
                self.powerups.remove(p)

    def _spawn_random(self, near_x: float, near_y: float):
        angle = random.uniform(0, 2*math.pi)
        dist  = random.uniform(250, 550)
        self._spawn_at(near_x + math.cos(angle)*dist,
                       near_y + math.sin(angle)*dist)

    def _spawn_at(self, x: float, y: float):
        kind = random.choice(self._KINDS)
        self.powerups.append(Powerup(str(uuid.uuid4()), x, y, kind))

    def draw(self, surf: pygame.Surface, cam_x: float, cam_y: float, font):
        for p in self.powerups:
            sx = int(SCREEN_W//2 + p.x - cam_x)
            sy = int(SCREEN_H//2 + p.y - cam_y)
            # skip off-screen
            if not (-60 < sx < SCREEN_W+60 and -60 < sy < SCREEN_H+60):
                continue
            col = self._COLORS[p.kind]
            pulse_r = 18 + int(4 * math.sin(p.pulse))
            # outer glow
            draw_glow(surf, sx, sy, col, pulse_r + 14, 55)
            # main orb
            orb = pygame.Surface((pulse_r*2, pulse_r*2), pygame.SRCALPHA)
            pygame.draw.circle(orb, (*col, 200), (pulse_r, pulse_r), pulse_r)
            pygame.draw.circle(orb, (255,255,255,60), (pulse_r-4, pulse_r-4), pulse_r//3)
            surf.blit(orb, (sx - pulse_r, sy - pulse_r))
            # label
            lbl = self._LABELS[p.kind]
            t = font.render(lbl, True, (255,255,255))
            surf.blit(t, (sx - t.get_width()//2, sy - t.get_height()//2))
            # fading ring when about to expire
            if p.lifetime < 4.0:
                fade_a = int(200 * (p.lifetime / 4.0))
                ring_surf = pygame.Surface((80, 80), pygame.SRCALPHA)
                pygame.draw.circle(ring_surf, (*col, fade_a), (40,40), 38, 2)
                surf.blit(ring_surf, (sx-40, sy-40))


# ─────────────────────────────────────────────────────────────────────────────
# WAVE MANAGER
# ─────────────────────────────────────────────────────────────────────────────

class WaveManager:
    def __init__(self):
        self.wave_number    = 0
        self.enemies: List[AIEnemy] = []
        self.state          = "spawning"   # spawning | fighting | clear_delay | boss_intro
        self.clear_delay    = 0.0
        self.boss_intro_timer = 0.0
        self.is_boss_wave   = False
        self.kills_this_wave= 0
        self.total_kills    = 0
        self._kill_positions: List[Tuple[float,float]] = []  # positions of kills this frame

    @property
    def kill_positions_this_frame(self) -> List[Tuple[float,float]]:
        pos = self._kill_positions[:]
        self._kill_positions.clear()
        return pos

    def _enemy_count_for_wave(self, wave: int) -> int:
        if wave % CFG.BOSS_EVERY_N_WAVES == 0:
            return 1  # boss fight = 1 powerful enemy
        extra = (wave - 1) // CFG.WAVE_ENEMIES_GROWTH
        return min(CFG.WAVE_ENEMIES_MAX, CFG.WAVE_ENEMIES_START + extra)

    def _spawn_wave(self):
        self.wave_number += 1
        self.kills_this_wave = 0
        self.is_boss_wave = (self.wave_number % CFG.BOSS_EVERY_N_WAVES == 0)
        count = self._enemy_count_for_wave(self.wave_number)
        self.enemies = []
        prev = ""
        for i in range(count):
            r     = CFG.WAVE_ENEMY_SPREAD
            angle = 2*math.pi * i / count + random.uniform(-0.3, 0.3)
            dist  = random.uniform(r * 0.5, r)
            ex    = math.cos(angle) * dist
            ey    = math.sin(angle) * dist
            if self.is_boss_wave:
                e = BossAI(prev)
            else:
                e = AIEnemy(prev)
            e.x, e.y = ex, ey
            self.enemies.append(e)
            prev = e.ship.name
        self.state = "fighting"

    def update(self, dt: float, engine: 'GameEngine'):
        """Tick wave logic. Returns list of (x,y) kill positions this frame."""
        self._kill_positions.clear()

        if self.state == "spawning":
            self._spawn_wave()
            return

        if self.state == "clear_delay":
            self.clear_delay -= dt
            if self.clear_delay <= 0:
                self.state = "spawning"
            return

        if self.state == "boss_intro":
            self.boss_intro_timer -= dt
            if self.boss_intro_timer <= 0:
                self.state = "fighting"
            return

        # state == "fighting"
        fully_cloaked = engine.cloak_active and engine.cloak_reveal_remaining <= 0
        # When cloaked, give AI the last known position so they stop tracking
        target_x = engine.last_known_x if fully_cloaked else engine.x
        target_y = engine.last_known_y if fully_cloaked else engine.y

        all_dead = True
        for e in self.enemies:
            if not e.is_dead:
                all_dead = False
            # Tick each enemy — use last known pos when player is cloaked
            e.tick(dt, target_x, target_y, engine.bullets, engine.missiles)
            # Missile homing: freeze on last known position when cloaked
            for m in e.missiles:
                if m.owner_id == e.id:
                    if not fully_cloaked:
                        desired = math.atan2(engine.y - m.y, engine.x - m.x)
                        diff = shortest_angle_diff(m.angle, desired)
                        max_turn = 2.5 * dt * m.speed / 1500
                        m.angle += max(-max_turn, min(max_turn, diff))
                    # else: missile keeps flying straight — no longer homes

        # Check fresh deaths (use a flag to detect the transition)
        for e in self.enemies:
            if e.is_dead and not getattr(e, '_death_counted', False):
                e._death_counted = True
                self._kill_positions.append((e.x, e.y))
                self.kills_this_wave += 1
                self.total_kills     += 1
                engine.kill_feed.insert(0, KillEntry(
                    f"Enemy destroyed! Wave {self.wave_number} — {self.kills_this_wave} kills"
                ))

        if all_dead and self.enemies:
            self.state       = "clear_delay"
            self.clear_delay = CFG.WAVE_CLEAR_DELAY

    def check_collisions(self, engine: 'GameEngine'):
        """Run all player↔enemy collision checks."""
        for e in self.enemies:
            check_ai_attacks_player(engine, e)
            check_player_attacks_ai(engine, e)

    def home_player_missiles(self, engine: 'GameEngine', dt: float):
        targets = [(e.x, e.y, e.id) for e in self.enemies if not e.is_dead]
        engine.home_missiles(targets, dt)
        # Feed Wraith nearest-enemy info for blink aim indicator
        if engine.type_special == SpecialType.ALIEN:
            alive = [e for e in self.enemies if not e.is_dead]
            if alive:
                nearest = min(alive, key=lambda e: math.hypot(e.x - engine.x, e.y - engine.y))
                engine.wraith_nearest_id = nearest.id
                engine.wraith_nearest_x  = nearest.x
                engine.wraith_nearest_y  = nearest.y
            else:
                engine.wraith_nearest_id = None


# ─────────────────────────────────────────────────────────────────────────────
# RENDERER
# ─────────────────────────────────────────────────────────────────────────────

class Renderer:
    def __init__(self, screen: pygame.Surface, assets: Assets):
        self.screen = screen
        self.assets = assets
        self.bg = Background(assets)
        # Pre-scale bullet sprites
        self._bullet_surf  = assets.get_sprite("bulletSprite-1",  (25,25))
        self._frost_b_surf = assets.get_sprite("frostBulletSprite-1", (25,25))
        self._miss_surf    = assets.get_sprite("missileSprite-1",  (40,40))
        self._frost_m_surf = assets.get_sprite("frostMissileSprite-1", (40,40))

    def world_to_screen(self, wx: float, wy: float, cam_x: float, cam_y: float) -> Tuple[int,int]:
        return (int(SCREEN_W//2 + wx - cam_x),
                int(SCREEN_H//2 + wy - cam_y))
    def _draw_direction_arrow(self, surf, wx, wy, angle, cam_x, cam_y, color, size=18):
        """Draw a small arrow indicating ship direction."""
        sx, sy = self.world_to_screen(wx, wy, cam_x, cam_y)
        # Arrow tip offset forward
        tip_x = sx + math.cos(angle) * size
        tip_y = sy + math.sin(angle) * size
        # Base points
        base_x = sx + math.cos(angle + math.pi) * (size * 0.4)
        base_y = sy + math.sin(angle + math.pi) * (size * 0.4)

        left_x = base_x + math.cos(angle + 2.3) * (size * 0.35)
        left_y = base_y + math.sin(angle + 2.3) * (size * 0.35)
        right_x = base_x + math.cos(angle - 2.3) * (size * 0.35)
        right_y = base_y + math.sin(angle - 2.3) * (size * 0.35)

    # Draw arrow with glow for visibility
        draw_glow(surf, (tip_x + base_x)/2, (tip_y + base_y)/2, color, 12, 40)
        pygame.draw.polygon(surf, color, [
            (int(tip_x), int(tip_y)),
            (int(left_x), int(left_y)),
            (int(right_x), int(right_y))
        ])
    def draw_frame(self, engine: 'GameEngine', wave_mgr: 'WaveManager',
                   powerup_mgr: 'PowerupManager', fps: float,
                   time_scale: float = 1.0, time_scale_notify: float = 0.0):
        s = self.screen
        cam_x, cam_y = engine.cam_x, engine.cam_y
        enemies = wave_mgr.enemies

        # Background
        self.bg.draw(s, cam_x, cam_y)

        # Stars
        smw, smh = engine.star_map_w, engine.star_map_h
        for star in engine.stars:
            wx = (star.x - cam_x) % smw - smw//2 + SCREEN_W//2
            wy = (star.y - cam_y) % smh - smh//2 + SCREEN_H//2
            pygame.draw.rect(s, (255,255,255,128), (int(wx), int(wy), int(star.size), int(star.size)))

        # Powerups
        powerup_mgr.draw(s, cam_x, cam_y, self.assets.font_hud)

        # Player afterimages
        for ai_img in engine.afterimages:
            sp = self.assets.get_sprite_scaled(ai_img.sprite)
            if sp:
                sx, sy = self.world_to_screen(ai_img.x, ai_img.y, cam_x, cam_y)
                draw_rotated_sprite(s, sp, sx, sy, ai_img.angle, int(ai_img.alpha * 100))

        # Enemy ships
        for ai in enemies:
            if not ai.is_dead:
                boss_scale = getattr(ai, 'display_scale', 1.0)
                self._draw_ship(s, ai.x, ai.y, ai.angle, ai.current_sprite(),
                                cam_x, cam_y,
                                cloak=ai.cloak_active,
                                heal_active=ai.heal_active,
                                fire_rate=ai.fire_rate_active,
                                boss_scale=boss_scale,
                                is_boss=isinstance(ai, BossAI))
                # Stun visual: spinning yellow stars above ship
                if ai.stun_timer > 0:
                    ex_s, ey_s = self.world_to_screen(ai.x, ai.y, cam_x, cam_y)
                    flash_a = int(200 * min(ai.stun_timer / 0.3, 1.0))
                    pulse = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() * 0.018)
                    stun_r = int(34 + 6 * pulse)
                    stun_surf = pygame.Surface((120, 120), pygame.SRCALPHA)
                    pygame.draw.circle(stun_surf, (255, 230, 0, min(flash_a, 120)),
                                       (60, 60), stun_r, 3)
                    s.blit(stun_surf, (int(ex_s) - 60, int(ey_s) - 60))
                    # "STUNNED" label
                    stun_lbl = self.assets.font_hud.render("STUNNED", True, (255, 230, 0))
                    s.blit(stun_lbl, (int(ex_s) - stun_lbl.get_width() // 2, int(ey_s) - 52))
                    # Spinning star dots
                    for i in range(4):
                        ang = pygame.time.get_ticks() * 0.005 + i * math.pi / 2
                        sx2 = int(ex_s + math.cos(ang) * 28)
                        sy2 = int(ey_s - 24 + math.sin(ang) * 10)
                        pygame.draw.circle(s, (255, 240, 60), (sx2, sy2), 4)

        # Player ship
        if not engine.is_dead:
            cloaked = engine.cloak_active and engine.cloak_reveal_remaining <= 0
            self._draw_ship(s, engine.x, engine.y, engine.angle,
                            engine.current_sprite(), cam_x, cam_y,
                            cloak=cloaked,
                            heal_active=engine.heal_active,
                            fire_rate=engine.fire_rate_active or engine.powerup_firerate_timer > 0,
                            is_player=True,
                            invincible=engine.powerup_invincible_timer > 0)
            # Wraith charge glow on ship
            if engine.type_special == SpecialType.ALIEN and engine.wraith_charging:
                charge_prog = min(engine.wraith_charge_timer / engine.WRAITH_BLINK_CHARGE_TIME, 1.0)
                if engine.wraith_charge_locked:
                    pulse_a = 80 + int(60 * math.sin(pygame.time.get_ticks() * 0.015))
                    draw_glow(s, SCREEN_W//2, SCREEN_H//2, (160, 0, 255), int(50 + 20 * math.sin(pygame.time.get_ticks() * 0.015)), pulse_a)
                else:
                    draw_glow(s, SCREEN_W//2, SCREEN_H//2, (100, 0, 200), int(20 + 30 * charge_prog), int(60 * charge_prog))

        # ── Enemy tracker arrows ──
        for ai in enemies:
            if ai.is_dead: continue
            dx_ai = ai.x - engine.x
            dy_ai = ai.y - engine.y
            dist_to_ai = math.hypot(dx_ai, dy_ai)
            angle_to_ai = math.atan2(dy_ai, dx_ai)
            if dist_to_ai > 350:
                orbit_r = 90
                px_c = SCREEN_W // 2
                py_c = SCREEN_H // 2
                ax = px_c + math.cos(angle_to_ai) * orbit_r
                ay = py_c + math.sin(angle_to_ai) * orbit_r
                pulse = 180 + int(60 * math.sin(engine.frame_count * 0.12))
                tri_size = 13
                tip_x = ax + math.cos(angle_to_ai) * tri_size
                tip_y = ay + math.sin(angle_to_ai) * tri_size
                l_x = ax + math.cos(angle_to_ai + 2.4) * tri_size * 0.7
                l_y = ay + math.sin(angle_to_ai + 2.4) * tri_size * 0.7
                r_x = ax + math.cos(angle_to_ai - 2.4) * tri_size * 0.7
                r_y = ay + math.sin(angle_to_ai - 2.4) * tri_size * 0.7
                boss_col = (255, 200, 0) if isinstance(ai, BossAI) else (255, 80, 80)
                draw_glow(s, ax, ay, boss_col, 18, pulse // 3)
                tri_surf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
                pygame.draw.polygon(tri_surf, (*boss_col, pulse), [
                    (int(tip_x), int(tip_y)), (int(l_x), int(l_y)), (int(r_x), int(r_y))
                ])
                s.blit(tri_surf, (0, 0))
                dist_label = self.assets.font_hud.render(f"{int(dist_to_ai)}u", True, (255, 140, 140))
                s.blit(dist_label, (int(ax) - dist_label.get_width() // 2, int(ay) + 16))

        # ── Combined bullet draw (player + all enemies) ──
        all_bullets = engine.bullets[:]
        for ai in enemies: all_bullets += ai.bullets
        for b in all_bullets:
            bx, by = self.world_to_screen(b.x, b.y, cam_x, cam_y)
            if b.is_frost_sphere:
                draw_glow(s, bx, by, (0,200,255), 22)
                if b.has_burst and self._frost_b_surf:
                    s.blit(self._frost_b_surf, (bx-12, by-12))
                else:
                    draw_glow(s, bx, by, (0,200,255), 55, 60)
                    draw_glow(s, bx, by, (255,255,255), 28, 30)
                    if self._frost_b_surf:
                        orbit_r2 = 14
                        phase = engine.frame_count * 0.07
                        for i in range(5):
                            theta = phase + i*(2*math.pi/5)
                            ox = bx + math.cos(theta)*orbit_r2
                            oy = by + math.sin(theta)*orbit_r2
                            s.blit(self._frost_b_surf, (int(ox)-8, int(oy)-8))
            else:
                # Refined rectangular bullet
                b_angle = math.atan2(b.vy, b.vx)
                bw, bh = 14, 5  # length × width
                bullet_surf = pygame.Surface((bw, bh), pygame.SRCALPHA)
                is_player_b = b.owner_name == "player"
                core_col = (180, 230, 255) if is_player_b else (255, 160, 80)
                rim_col  = (60, 160, 255)  if is_player_b else (255, 80, 20)
                pygame.draw.rect(bullet_surf, rim_col,  (0, 0, bw, bh), border_radius=2)
                pygame.draw.rect(bullet_surf, core_col, (2, 1, bw-4, bh-2), border_radius=1)
                deg = -math.degrees(b_angle)
                rot_b = pygame.transform.rotate(bullet_surf, deg)
                s.blit(rot_b, rot_b.get_rect(center=(bx, by)))
                glow_col = (100, 200, 255) if is_player_b else (255, 160, 60)
                draw_glow(s, bx, by, glow_col, 14, 55)

        # ── Missiles (player + all enemies) ──
        all_missiles = engine.missiles[:]
        for ai in enemies: all_missiles += ai.missiles
        for m in all_missiles:
            mx, my = self.world_to_screen(m.x, m.y, cam_x, cam_y)
            is_frost = m.is_frost
            # Refined rectangular missile body
            mw, mh = 26, 7
            miss_surf = pygame.Surface((mw, mh), pygame.SRCALPHA)
            if is_frost:
                body_col = (140, 220, 255)
                rim_col  = (0, 160, 220)
                tip_col  = (220, 240, 255)
                glow_col = (0, 200, 255)
            else:
                body_col = (255, 200, 80)
                rim_col  = (220, 100, 20)
                tip_col  = (255, 240, 180)
                glow_col = (255, 140, 0)
            pygame.draw.rect(miss_surf, rim_col,  (0, 0, mw, mh), border_radius=3)
            pygame.draw.rect(miss_surf, body_col, (2, 1, mw-4, mh-2), border_radius=2)
            # Bright nose tip
            pygame.draw.rect(miss_surf, tip_col, (mw-5, 1, 4, mh-2), border_radius=2)
            deg = -math.degrees(m.angle)
            rot_m = pygame.transform.rotate(miss_surf, deg)
            draw_glow(s, mx, my, glow_col, 22, 60)
            s.blit(rot_m, rot_m.get_rect(center=(mx, my)))
            # Exhaust trail glow at tail
            tail_x = mx - math.cos(m.angle) * 14
            tail_y = my - math.sin(m.angle) * 14
            draw_glow(s, tail_x, tail_y, glow_col, 12, 90)

        # ── Lasers (player + all enemies) ──
        all_lasers = engine.lasers[:]
        for ai in enemies: all_lasers += ai.lasers
        for laser in all_lasers:
            if laser.mine:
                ox = SCREEN_W//2 + (engine.x + math.cos(engine.angle)*30 - cam_x)
                oy = SCREEN_H//2 + (engine.y + math.sin(engine.angle)*30 - cam_y)
                la = engine.angle
            else:
                ox, oy = self.world_to_screen(laser.x, laser.y, cam_x, cam_y)
                la = laser.angle
            ex = ox + math.cos(la)*6000
            ey = oy + math.sin(la)*6000
            color = (255,50,50) if laser.special else (80,255,255)
            for width, alpha in [(40,8),(24,15),(14,30),(7,75),(3,178),(1,255)]:
                c = (*color[:3], min(255, int(alpha*2)))
                pygame.draw.line(s, c, (int(ox),int(oy)), (int(ex),int(ey)), width)

        # ── Muzzle flashes ──
        flash_sources = [(engine.flashes, engine.x, engine.y, engine.angle)]
        for ai in enemies:
            flash_sources.append((ai.flashes, ai.x, ai.y, ai.angle))
        for fl_list, cx_ref, cy_ref, ang_ref in flash_sources:
            for f in fl_list:
                if f.attached:
                    fx = SCREEN_W//2 + (cx_ref + math.cos(ang_ref)*30 - cam_x)
                    fy = SCREEN_H//2 + (cy_ref + math.sin(ang_ref)*30 - cam_y)
                else:
                    fx, fy = self.world_to_screen(f.x, f.y, cam_x, cam_y)
                if f.is_laser:
                    draw_glow(s, fx, fy, (20,200,255), 22, 60)
                else:
                    draw_glow(s, fx, fy, (200,200,200), 20, 80)
                    inner = (0,0,0) if f.frame < 2 else (255,255,255)
                    pygame.draw.circle(s, inner, (int(fx),int(fy)), 12)

        # ── Explosions ──
        all_exp_lists = [engine.explosions] + [e.explosions for e in enemies]
        for exp_list in all_exp_lists:
                for e in exp_list:
                    ex, ey = self.world_to_screen(e.x, e.y, cam_x, cam_y)
                    scale = (1 + e.frame * 0.15)
                    r = max(1, int(e.size / 2 * scale))   # prevent zero radius
                    alpha = max(0, 180 - e.frame * 40)
                    draw_glow(s, ex, ey, (255, 200, 100), r, alpha)

        if engine.wraith_blink_fx_timer > 0:
            fx_a = int(140 * engine.wraith_blink_fx_timer / 0.4)
            draw_glow(s, SCREEN_W//2, SCREEN_H//2, (160, 0, 255), 70, fx_a)

        # Wraith melee swing arc
        if engine.type_special == SpecialType.ALIEN and engine.wraith_melee_anim_timer > 0:
            arc_prog = 1.0 - engine.wraith_melee_anim_timer / 0.25
            arc_alpha = int(220 * (1.0 - arc_prog))
            arc_r = int(engine.WRAITH_MELEE_RANGE * 0.75)
            arc_surf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            combo_col = {0: (180, 80, 255), 1: (220, 120, 255), 2: (255, 80, 80), 3: (255, 180, 0)}
            col = (*combo_col.get(engine.wraith_combo_count, (180, 80, 255))[:3], arc_alpha)
            half_arc = int(engine.WRAITH_MELEE_AIM_DEG)
            start_deg = int(math.degrees(engine.angle) - half_arc)
            stop_deg  = int(math.degrees(engine.angle) + half_arc)
            cx, cy = SCREEN_W//2, SCREEN_H//2
            rect = pygame.Rect(cx - arc_r, cy - arc_r, arc_r*2, arc_r*2)
            pygame.draw.arc(arc_surf, col, rect,
                            math.radians(start_deg), math.radians(stop_deg), 6)
            s.blit(arc_surf, (0, 0))
            draw_glow(s, SCREEN_W//2, SCREEN_H//2, combo_col.get(engine.wraith_combo_count, (180, 80, 255)), arc_r // 2, arc_alpha // 3)

        # Melee hit FX (world-space sparks)
        for hx, hy, ht in engine.wraith_melee_hit_fx:
            hsx, hsy = self.world_to_screen(hx, hy, cam_x, cam_y)
            hit_a = int(255 * ht / 0.25)
            draw_glow(s, hsx, hsy, (255, 200, 0), 28, hit_a // 2)
            pygame.draw.circle(s, (255, 240, 80), (int(hsx), int(hsy)), 8)

        # Wraith aim-cone line to nearest enemy
        if engine.type_special == SpecialType.ALIEN and engine.wraith_nearest_id is not None:
            ex_s, ey_s = self.world_to_screen(engine.wraith_nearest_x, engine.wraith_nearest_y, cam_x, cam_y)
            cone_col = (0, 255, 80, 120) if engine.wraith_aim_ok else (255, 80, 80, 80)
            line_surf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            pygame.draw.line(line_surf, cone_col,
                             (SCREEN_W//2, SCREEN_H//2),
                             (int(ex_s), int(ey_s)), 2)
            s.blit(line_surf, (0, 0))
            # Target reticle
            r_col = (0, 255, 80) if engine.wraith_aim_ok else (255, 80, 80)
            pygame.draw.circle(s, r_col, (int(ex_s), int(ey_s)), 18, 2)

        # ── HUD ──
        self._draw_hud(s, engine, wave_mgr, fps, time_scale, time_scale_notify)

    def _draw_ship(self, surf, wx, wy, angle, sprite_name, cam_x, cam_y, cloak=False, heal_active=False, fire_rate=False, is_player=False, boss_scale=1.0, is_boss=False, invincible=False):
        """Draw ship using real sprite with glows, cloak effect, and direction arrow."""
        sp = self.assets.get_sprite_scaled(sprite_name)
        sx, sy = self.world_to_screen(wx, wy, cam_x, cam_y)

        # Scale sprite for boss
        if sp is not None and boss_scale != 1.0:
            new_w = int(sp.get_width() * boss_scale)
            new_h = int(sp.get_height() * boss_scale)
            sp = pygame.transform.smoothscale(sp, (new_w, new_h))

        if sp is None:
            # Fallback rectangle if sprite somehow fails
            ship_surf = pygame.Surface((50, 30), pygame.SRCALPHA)
            color = (80, 180, 255) if is_player else (255, 80, 80)
            pygame.draw.rect(ship_surf, color, (0, 0, 50, 30), border_radius=4)
            pygame.draw.polygon(ship_surf, (255, 255, 100), [(40, 8), (50, 15), (40, 22)])
            deg = -math.degrees(angle)
            rotated = pygame.transform.rotate(ship_surf, deg)
            rect = rotated.get_rect(center=(int(sx), int(sy)))
            surf.blit(rotated, rect)
            draw_glow(surf, sx, sy, color, 35, 70)
            self._draw_direction_arrow(surf, wx, wy, angle, cam_x, cam_y,
                (100, 220, 255) if is_player else (255, 100, 100), size=25)
            return

        # Cloak makes ship semi-transparent
        alpha = 60 if cloak else 255

        # Glow effects (independent of each other)
        if heal_active:
            draw_glow(surf, sx, sy, (0, 255, 100), 45, 80)
        if fire_rate:
            draw_glow(surf, sx, sy, (255, 100, 0), 45, 80)
        if is_boss:
            draw_glow(surf, sx, sy, (255, 200, 0), 60, 50)
        if invincible:
            pulse_a = 80 + int(40 * math.sin(pygame.time.get_ticks() * 0.01))
            draw_glow(surf, sx, sy, (220, 220, 50), 55, pulse_a)

        # === MAIN SHIP DRAWING ===
        draw_rotated_sprite(surf, sp, sx, sy, angle, alpha)

        # Extra glow for player during fire rate boost
        if is_player and fire_rate:
            draw_glow(surf, sx, sy, (0, 150, 255), 35, 40)

        # Direction arrow for visibility
        arrow_color = (80, 200, 255) if is_player else (255, 80, 80)
        self._draw_direction_arrow(surf, wx, wy, angle, cam_x, cam_y, arrow_color, size=22)
    def _draw_hud(self, surf: pygame.Surface, engine: 'GameEngine', wave_mgr: 'WaveManager',
                  fps: float, time_scale: float = 1.0, time_scale_notify: float = 0.0):
        a = self.assets

        # ── Layout constants ──────────────────────────────────────────────────
        LEFT       = 20          # left edge of all HUD bars
        BAR_W      = 220         # width of all bars
        BAR_H      = 14          # standard bar height
        LBL_H      = 16          # pixel height of font_hud text (~13px + 3 padding)
        ROW_GAP    = 6           # gap between bar bottom and next label top
        SECTION_GAP= 14          # extra gap between logical sections

        # Build bottom-up: start from the screen bottom and stack upward.
        # Each slot is: label (LBL_H) + bar (BAR_H) + ROW_GAP
        SLOT = LBL_H + BAR_H + ROW_GAP   # 36px per bar slot

        # Row positions (y of the bar itself), bottom-to-top:
        # Row 0 — Shield bar (always present)
        shield_bar_y = SCREEN_H - 18 - BAR_H          # 8px from bottom edge
        # Row 1 — Special [E] bar
        special_bar_y = shield_bar_y - SLOT - SECTION_GAP
        # Row 2 — Melee [F] bar (Wraith only, otherwise skip)
        melee_bar_y   = special_bar_y - SLOT
        # Row 3 — Blink charge bar (Wraith only, only shown while charging)
        charge_bar_y  = melee_bar_y - SLOT

        # ── Shield bar ────────────────────────────────────────────────────────
        ratio = max(0.0, engine.shield / engine.max_shield)
        pygame.draw.rect(surf, (30,30,50), (LEFT, shield_bar_y, BAR_W, BAR_H), border_radius=4)
        if ratio > 0:
            sc = (0,200,255) if ratio > 0.5 else (255,200,0) if ratio > 0.25 else (255,60,60)
            pygame.draw.rect(surf, sc, (LEFT, shield_bar_y, int(BAR_W*ratio), BAR_H), border_radius=4)
        pygame.draw.rect(surf, (100,200,255), (LEFT, shield_bar_y, BAR_W, BAR_H), 2, border_radius=4)
        shield_lbl = a.font_hud.render(f"SHIELD  {int(engine.shield)}/{int(engine.max_shield)}", True, (200,230,255))
        surf.blit(shield_lbl, (LEFT, shield_bar_y - LBL_H))

        # ── Special [E] cooldown bar ──────────────────────────────────────────
        sp_names = {
            SpecialType.DASH:    "PHASE DRIVE  [E]",
            SpecialType.MISSILE: "CRUISE MISSILE  [E]",
            SpecialType.FIRERATE:"OVERDRIVE  [E]",
            SpecialType.ALIEN:   "BLINK STRIKE  [E]",
            SpecialType.HEAL:    "REPAIR  [E]",
            SpecialType.NONE:    "BARRAGE  [E]",
            SpecialType.CLOAK:   "CLOAK  [E]",
            SpecialType.LASER:   "LASER CATALYST  [E]",
            SpecialType.FROST:   "FROST MISSILES  [E]",
        }
        sp_label = sp_names.get(engine.type_special, "SPECIAL  [E]")
        cd_ratio = min(1.0, max(0.0, 1.0 - engine.dash_cooldown / engine.dash_cd_time)) if engine.dash_cd_time > 0 else 1.0
        pygame.draw.rect(surf, (30,30,50), (LEFT, special_bar_y, BAR_W, BAR_H), border_radius=3)
        if cd_ratio > 0:
            cd_col = (0,255,180) if cd_ratio >= 1.0 else (180,100,255)
            pygame.draw.rect(surf, cd_col, (LEFT, special_bar_y, int(BAR_W*cd_ratio), BAR_H), border_radius=3)
        pygame.draw.rect(surf, (150,100,255), (LEFT, special_bar_y, BAR_W, BAR_H), 1, border_radius=3)
        # Label: name on left, aim status on right (Wraith only)
        sp_lbl_surf = a.font_hud.render(sp_label, True, (200,200,255))
        surf.blit(sp_lbl_surf, (LEFT, special_bar_y - LBL_H))
        if engine.type_special == SpecialType.ALIEN and engine.wraith_nearest_id is not None:
            aim_col  = (0, 255, 80) if engine.wraith_aim_ok else (255, 100, 80)
            aim_txt  = "● AIM OK" if engine.wraith_aim_ok else "○ OFF-AIM"
            aim_surf = a.font_hud.render(aim_txt, True, aim_col)
            surf.blit(aim_surf, (LEFT + BAR_W - aim_surf.get_width(), special_bar_y - LBL_H))

        # ── Wraith-only bars ──────────────────────────────────────────────────
        if engine.type_special == SpecialType.ALIEN:

            # — Melee [F] cooldown bar —
            melee_ready  = engine.wraith_melee_cooldown <= 0
            melee_ratio  = min(1.0, 1.0 - max(0.0, engine.wraith_melee_cooldown / engine.WRAITH_MELEE_COOLDOWN))
            melee_col    = (255, 200, 0) if melee_ready else (160, 70, 70)
            pygame.draw.rect(surf, (30,20,10), (LEFT, melee_bar_y, BAR_W, BAR_H), border_radius=3)
            if melee_ratio > 0:
                pygame.draw.rect(surf, melee_col, (LEFT, melee_bar_y, int(BAR_W*melee_ratio), BAR_H), border_radius=3)
            pygame.draw.rect(surf, melee_col, (LEFT, melee_bar_y, BAR_W, BAR_H), 1, border_radius=3)
            melee_txt = "MELEE  [F]  READY" if melee_ready else "MELEE  [F]"
            melee_lbl_surf = a.font_hud.render(melee_txt, True, melee_col)
            surf.blit(melee_lbl_surf, (LEFT, melee_bar_y - LBL_H))
            # Combo pip dots on the right of the melee label row
            if engine.wraith_combo_count > 0:
                combo_cols = [(180,80,255),(220,120,255),(255,80,80),(255,180,0)]
                for pip_i in range(3):
                    filled  = pip_i < engine.wraith_combo_count
                    pip_col = combo_cols[min(engine.wraith_combo_count - 1, 3)] if filled else (60,60,80)
                    pip_x   = LEFT + BAR_W - (3 - pip_i) * 18
                    pip_y   = melee_bar_y - LBL_H + 4
                    pygame.draw.circle(surf, pip_col, (pip_x, pip_y), 6)
                    if filled:
                        pygame.draw.circle(surf, (255,255,255), (pip_x, pip_y), 3)

            # — Blink charge bar (only while actively charging) —
            if engine.wraith_charging:
                ch_ratio = min(1.0, engine.wraith_charge_timer / engine.WRAITH_BLINK_CHARGE_TIME)
                ch_col   = (0, 255, 140) if engine.wraith_charge_locked else (120, 80, 255)
                pygame.draw.rect(surf, (20,20,40), (LEFT, charge_bar_y, BAR_W, BAR_H), border_radius=3)
                if ch_ratio > 0:
                    pygame.draw.rect(surf, ch_col, (LEFT, charge_bar_y, int(BAR_W*ch_ratio), BAR_H), border_radius=3)
                pygame.draw.rect(surf, ch_col, (LEFT, charge_bar_y, BAR_W, BAR_H), 1, border_radius=3)
                charge_txt = "CHARGED — RELEASE!" if engine.wraith_charge_locked else "CHARGING..."
                ch_lbl     = a.font_hud.render(charge_txt, True, ch_col)
                surf.blit(ch_lbl, (LEFT, charge_bar_y - LBL_H))

        # ── Active ability / powerup indicators (right side, top-right) ──────
        # Placed top-right to avoid clashing with kill feed or bottom bars
        indicators = []
        if engine.fire_rate_active:
            indicators.append(("OVERDRIVE",    (255,100,0)))
        if engine.heal_active:
            indicators.append(("REPAIRING",    (0,255,100)))
        if engine.cloak_active:
            indicators.append(("CLOAKED",      (180,100,255)))
        if engine.laser_special_active:
            indicators.append(("LASER BOOST",  (0,200,255)))
        if engine.type_special == SpecialType.ALIEN and engine.wraith_charge_locked and engine.wraith_aim_ok:
            indicators.append(("⚡ BLINK READY — RELEASE E!", (0, 255, 140)))
        elif engine.type_special == SpecialType.ALIEN and engine.wraith_charging:
            indicators.append(("CHARGING...",   (120, 60, 220)))
        if engine.powerup_firerate_timer > 0:
            indicators.append((f"RAPID FIRE  {engine.powerup_firerate_timer:.1f}s", (255,80,200)))
        if engine.powerup_speed_timer > 0:
            indicators.append((f"SPEED BOOST  {engine.powerup_speed_timer:.1f}s",   (80,200,255)))
        if engine.powerup_damage_timer > 0:
            indicators.append((f"DAMAGE x{CFG.POWERUP_DAMAGE_MULT}  {engine.powerup_damage_timer:.1f}s", (255,160,0)))
        if engine.powerup_invincible_timer > 0:
            indicators.append((f"INVINCIBLE  {engine.powerup_invincible_timer:.1f}s", (220,220,50)))
        for i, (itxt, col) in enumerate(indicators):
            t = a.font_hud.render(itxt, True, col)
            surf.blit(t, (SCREEN_W - t.get_width() - 20, 100 + i * 22))

        # ── Wraith combo counter — centre-screen flash ────────────────────────
        if engine.type_special == SpecialType.ALIEN and engine.wraith_combo_count > 0 and engine.wraith_combo_window > 0:
            combo_cols = [(180,80,255),(220,120,255),(255,80,80),(255,180,0)]
            ccol = combo_cols[min(engine.wraith_combo_count - 1, 3)]
            combo_txt = f"COMBO  x{engine.wraith_combo_count}!"
            ct2 = a.font_body.render(combo_txt, True, ccol)
            pulse_s = 1.0 + 0.12 * math.sin(pygame.time.get_ticks() * 0.02)
            scaled  = pygame.transform.scale(ct2, (int(ct2.get_width()*pulse_s), int(ct2.get_height()*pulse_s)))
            surf.blit(scaled, (SCREEN_W//2 - scaled.get_width()//2, SCREEN_H//2 - 120))

        # ── Wave info (top-left) ──
        wave_col = (255, 200, 0) if wave_mgr.is_boss_wave else (0, 220, 255)
        wave_label = f"⚔ BOSS WAVE {wave_mgr.wave_number}" if wave_mgr.is_boss_wave else f"WAVE  {wave_mgr.wave_number}"
        wt = a.font_body.render(wave_label, True, wave_col)
        surf.blit(wt, (SCREEN_W//2 - wt.get_width()//2, 5))

        if wave_mgr.state == "clear_delay":
            ct = a.font_hud.render(f"WAVE CLEAR!  Next wave in {wave_mgr.clear_delay:.1f}s", True, (0,255,150))
            surf.blit(ct, (SCREEN_W//2 - ct.get_width()//2, 38))
        elif wave_mgr.state == "spawning":
            ct = a.font_hud.render("Spawning enemies...", True, (200,200,100))
            surf.blit(ct, (SCREEN_W//2 - ct.get_width()//2, 38))

        # ── Enemy health bars (top-center area) ──
        alive_enemies = [e for e in wave_mgr.enemies if not e.is_dead]
        if alive_enemies:
            bar_start_y = 45
            bar_w_e, bar_h_e = 220, 12
            total_w = len(alive_enemies) * (bar_w_e + 8) - 8
            start_x = SCREEN_W//2 - total_w//2
            for idx, ai in enumerate(alive_enemies):
                ebx = start_x + idx * (bar_w_e + 8)
                eby = bar_start_y
                max_hp = getattr(ai, '_max_shield', ai.ship.shield)
                ar = max(0, ai.shield / max_hp)
                pygame.draw.rect(surf, (40,40,60), (ebx, eby, bar_w_e, bar_h_e), border_radius=3)
                if ar > 0:
                    acol = (255,200,0) if isinstance(ai, BossAI) else ((255,80,80) if ar < 0.5 else (255,180,0))
                    pygame.draw.rect(surf, acol, (ebx, eby, int(bar_w_e*ar), bar_h_e), border_radius=3)
                border_c = (255,200,0) if isinstance(ai, BossAI) else (255,100,100)
                pygame.draw.rect(surf, border_c, (ebx, eby, bar_w_e, bar_h_e), 1, border_radius=3)
                name_lbl = "⚠ BOSS" if isinstance(ai, BossAI) else ai.ship.name[:12]
                ai_name = a.font_hud.render(f"{name_lbl}  {int(ai.shield)}", True, border_c)
                surf.blit(ai_name, (ebx, eby - 16))

        # ── Kill feed ──
        for i, kf in enumerate(engine.kill_feed[:5]):
            alpha = min(255, int(kf.timer * 80))
            t = a.font_hud.render(kf.text, True, (255,220,80))
            surf.blit(t, (SCREEN_W - t.get_width() - 20, 60 + i*22))

        # ── Score / kills ──
        score_t = a.font_hud.render(f"KILLS  {wave_mgr.total_kills}", True, (100,200,140))
        surf.blit(score_t, (SCREEN_W - score_t.get_width() - 20, SCREEN_H - 40))

        # Controls reminder
        ctrl_lines = [
            "WASD / Arrows — Move",
            "SPACE — Fire",
            "E / Shift — Special",
            "[ / ] — Slow / Fast",
            "P — Pause",
            "ESC — Menu",
        ]
        if engine.type_special == SpecialType.ALIEN:
            ctrl_lines[2] = "E — Hold+Aim+Release (Blink)"
            ctrl_lines.insert(3, "F — Melee Strike / Combo")
        for i, line in enumerate(ctrl_lines):
            t = a.font_hud.render(line, True, (120,140,160))
            surf.blit(t, (SCREEN_W - t.get_width() - 20, SCREEN_H - 20 - (len(ctrl_lines)-i)*18))

        # ── Time scale indicator (bottom-centre) ─────────────────────────────
        if time_scale == 0.0:
            spd_txt = "⏸  PAUSED"
            spd_col = (255, 220, 60)
        elif time_scale == 1.0:
            spd_txt = None   # don't clutter at normal speed unless notify active
        elif time_scale < 1.0:
            spd_txt = f"◀◀  {time_scale:.2g}x  SLOW-MO"
            spd_col = (80, 200, 255)
        else:
            spd_txt = f"▶▶  {time_scale:.4g}x  FAST"
            spd_col = (255, 140, 40)

        # Always show when notify timer is running (includes the moment it snaps back to 1x)
        if time_scale_notify > 0 and spd_txt is None:
            spd_txt = "▶  1x  NORMAL"
            spd_col = (160, 200, 160)

        if spd_txt:
            # Semi-transparent pill background
            spd_surf = a.font_body.render(spd_txt, True, spd_col)
            pill_w = spd_surf.get_width() + 24
            pill_h = spd_surf.get_height() + 10
            pill_x = SCREEN_W // 2 - pill_w // 2
            pill_y = SCREEN_H - 44
            # Fade out as notify expires (but stay solid while paused / non-normal speed)
            if time_scale == 0.0 or time_scale != 1.0:
                pill_a = 200
            else:
                pill_a = int(200 * min(time_scale_notify, 1.0))
            pill_bg = pygame.Surface((pill_w, pill_h), pygame.SRCALPHA)
            pygame.draw.rect(pill_bg, (0, 0, 0, pill_a), (0, 0, pill_w, pill_h), border_radius=8)
            pygame.draw.rect(pill_bg, (*spd_col, pill_a), (0, 0, pill_w, pill_h), 2, border_radius=8)
            surf.blit(pill_bg, (pill_x, pill_y))
            # Render text with matching alpha
            spd_surf.set_alpha(pill_a)
            surf.blit(spd_surf, (pill_x + 12, pill_y + 5))

        # Slow-mo vignette (dark edges when slowed down)
        if time_scale < 1.0 and time_scale > 0.0:
            vign_a = int(90 * (1.0 - time_scale))
            vign = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            # Dark corners
            for r, a_val in [(260, vign_a), (180, vign_a // 2)]:
                pygame.draw.rect(vign, (0, 0, 0, 0), (r, r, SCREEN_W - r*2, SCREEN_H - r*2))
                pygame.draw.rect(vign, (0, 30, 60, a_val), (0, 0, SCREEN_W, SCREEN_H), r)
            surf.blit(vign, (0, 0))
        elif time_scale > 2.0:
            # Red tint overlay at very high speed
            tint_a = int(20 * min((time_scale - 2.0), 3.0))
            tint = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            tint.fill((80, 0, 0, tint_a))
            surf.blit(tint, (0, 0))

        # FPS
        fps_t = a.font_hud.render(f"FPS {int(fps)}", True, (80,100,120))
        surf.blit(fps_t, (SCREEN_W-70, SCREEN_H-20))

        # Ship name bottom left
        name_t = a.font_hud.render(engine.ship.name.upper(), True, (100,150,200))
        surf.blit(name_t, (30, SCREEN_H - 70))


# ─────────────────────────────────────────────────────────────────────────────
# TITLE SCREEN
# ─────────────────────────────────────────────────────────────────────────────

class TitleScreen:
    def __init__(self, assets: Assets):
        self.assets = assets
        self.alpha  = 0.0
        self.stars  = [Star(random.uniform(0,SCREEN_W), random.uniform(0,SCREEN_H),
                            random.uniform(1,4)) for _ in range(150)]

    def update(self, dt: float):
        self.alpha = min(1.0, self.alpha + dt*0.8)

    def draw(self, surf: pygame.Surface):
        surf.fill((5, 8, 20))
        for star in self.stars:
            pygame.draw.rect(surf, (200,200,255), (int(star.x),int(star.y), int(star.size),int(star.size)))

        a = self.assets
        title = a.font_title.render("SPACE SHOOTER", True, (0,220,255))
        sub   = a.font_body.render("PRESS  ENTER  TO  BEGIN", True, (100,180,255))
        # Glow behind title
        glow_surf = pygame.Surface((title.get_width()+80, title.get_height()+40), pygame.SRCALPHA)
        pygame.draw.rect(glow_surf, (0,80,120,60), glow_surf.get_rect(), border_radius=12)
        surf.blit(glow_surf, (SCREEN_W//2 - glow_surf.get_width()//2, SCREEN_H//2 - 80))
        surf.blit(title, (SCREEN_W//2 - title.get_width()//2, SCREEN_H//2 - 70))
        surf.blit(sub,   (SCREEN_W//2 - sub.get_width()//2,   SCREEN_H//2 + 20))

        ver = a.font_hud.render("PYGAME PORT  —  v1.0", True, (60,80,100))
        surf.blit(ver, (SCREEN_W//2 - ver.get_width()//2, SCREEN_H - 30))


# ─────────────────────────────────────────────────────────────────────────────
# SHIP SELECTOR
# ─────────────────────────────────────────────────────────────────────────────

class ShipSelectorScreen:
    CARDS_PER_ROW = 3

    def __init__(self, assets: Assets):
        self.assets   = assets
        self.selected = 0
        self.scroll   = 0
        self._build_card_rects()

    def _build_card_rects(self):
        self.rects = []
        card_w, card_h = 360, 180
        pad_x, pad_y = 30, 20
        start_x = (SCREEN_W - (self.CARDS_PER_ROW * card_w + (self.CARDS_PER_ROW-1)*pad_x)) // 2
        start_y = 110
        for i in range(len(SHIPS)):
            row, col = divmod(i, self.CARDS_PER_ROW)
            rx = start_x + col*(card_w+pad_x)
            ry = start_y + row*(card_h+pad_y) - self.scroll
            self.rects.append(pygame.Rect(rx, ry, card_w, card_h))

    def handle_event(self, event) -> Optional[ShipType]:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_LEFT, pygame.K_a):
                self.selected = max(0, self.selected-1)
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self.selected = min(len(SHIPS)-1, self.selected+1)
            elif event.key in (pygame.K_UP, pygame.K_w):
                self.selected = max(0, self.selected - self.CARDS_PER_ROW)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.selected = min(len(SHIPS)-1, self.selected + self.CARDS_PER_ROW)
            elif event.key == pygame.K_RETURN:
                return SHIPS[self.selected]
        if event.type == pygame.MOUSEBUTTONDOWN:
            self._build_card_rects()
            for i, rect in enumerate(self.rects):
                if rect.collidepoint(event.pos):
                    if i == self.selected:
                        return SHIPS[self.selected]
                    self.selected = i
        if event.type == pygame.MOUSEWHEEL:
            self.scroll = max(0, self.scroll - event.y * 30)
        return None

    def draw(self, surf: pygame.Surface):
        a = self.assets
        surf.fill((5, 8, 20))
        self._build_card_rects()

        header = a.font_body.render("SELECT YOUR SHIP", True, (0,220,255))
        surf.blit(header, (SCREEN_W//2 - header.get_width()//2, 20))
        sub = a.font_hud.render("Arrow keys or click to select  •  Enter to launch", True, (80,100,140))
        surf.blit(sub, (SCREEN_W//2 - sub.get_width()//2, 60))

        for i, (ship, rect) in enumerate(zip(SHIPS, self.rects)):
            if rect.bottom < 0 or rect.top > SCREEN_H: continue
            is_sel = (i == self.selected)
            border_col = (0,220,255) if is_sel else (40,60,90)
            bg_col     = (0,30,50,200) if is_sel else (10,15,25,180)
            bg = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
            bg.fill(bg_col)
            surf.blit(bg, rect)
            pygame.draw.rect(surf, border_col, rect, 2, border_radius=8)

            # Ship sprite preview
            sp = a.get_sprite_scaled(ship.idle_sprite)
            if sp:
                scaled = pygame.transform.smoothscale(sp, (72, 72))
                rot    = pygame.transform.rotate(scaled, -90)
                surf.blit(rot, (rect.x+10, rect.y + rect.h//2 - rot.get_height()//2))

            # Text info
            tx = rect.x + 95
            name_t = a.font_small.render(ship.name.upper(), True, (0,220,255) if is_sel else (150,180,200))
            surf.blit(name_t, (tx, rect.y+12))
            stats = [
                f"SHIELD  {int(ship.shield)}",
                f"THRUST  {int(ship.thrust)}",
                f"TURN    {ship.turn:.0f}",
                f"DMG     {int(ship.bullet_dmg)}",
            ]
            for j, stat in enumerate(stats):
                st = a.font_hud.render(stat, True, (130,160,190))
                surf.blit(st, (tx, rect.y + 38 + j*20))
            # Special label
            sp_name = ship.special.name.replace("_"," ")
            sp_t = a.font_hud.render(f"SPECIAL: {sp_name}", True, (150,100,255) if is_sel else (90,60,140))
            surf.blit(sp_t, (tx, rect.y+rect.h-22))

        # Description box for selected ship
        sel = SHIPS[self.selected]
        desc_y = SCREEN_H - 80
        pygame.draw.rect(surf, (0,20,35), (20, desc_y, SCREEN_W-40, 75), border_radius=6)
        pygame.draw.rect(surf, (0,100,150), (20, desc_y, SCREEN_W-40, 75), 1, border_radius=6)
        lines = sel.desc.split("\n")
        for i, line in enumerate(lines[:3]):
            t = a.font_hud.render(line, True, (180,210,240))
            surf.blit(t, (35, desc_y + 8 + i*20))


# ─────────────────────────────────────────────────────────────────────────────
# DEATH SCREEN OVERLAY
# ─────────────────────────────────────────────────────────────────────────────

class DeathOverlay:
    def __init__(self, assets: Assets):
        self.assets = assets
        self.alpha  = 0.0
        self.done   = False
        self.timer  = 3.0

    def update(self, dt: float) -> bool:
        """Returns True when the overlay should transition back to ship select."""
        self.timer -= dt
        self.alpha  = min(1.0, self.alpha + dt * 0.5)
        if self.timer <= 0:
            return True
        return False

    def draw(self, surf: pygame.Surface):
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, int(self.alpha * 180)))
        surf.blit(overlay, (0,0))
        a = self.assets
        t1 = a.font_body.render("YOU WERE DESTROYED", True, (255,80,80))
        t2 = a.font_hud.render("Returning to ship select...", True, (200,100,100))
        surf.blit(t1, (SCREEN_W//2 - t1.get_width()//2, SCREEN_H//2 - 30))
        surf.blit(t2, (SCREEN_W//2 - t2.get_width()//2, SCREEN_H//2 + 20))


# ─────────────────────────────────────────────────────────────────────────────
# COLLISION DETECTION (player ↔ AI bullets/missiles/lasers)
# ─────────────────────────────────────────────────────────────────────────────

def check_ai_attacks_player(engine: GameEngine, ai: AIEnemy):
    if engine.is_dead or engine.alien_phase_active: return
    if engine.cloak_active and engine.cloak_reveal_remaining <= 0: return  # untargetable while cloaked

    player_r = 30 if engine.type_special == SpecialType.NONE else 24
    hit_r_sq  = (player_r + 5)**2

    # AI bullets → player
    surviving = []
    for b in ai.bullets:
        dx, dy = engine.x - b.x, engine.y - b.y
        if dx*dx + dy*dy < hit_r_sq:
            engine.receive_damage(b.damage, "AI", "bullet")
            if b.is_frost_sphere:
                spd = math.hypot(engine.vx, engine.vy)
                if spd > 0:
                    ns = max(0, spd-100)
                    engine.vx = engine.vx/spd*ns
                    engine.vy = engine.vy/spd*ns
        else:
            surviving.append(b)
    ai.bullets = surviving

    # AI missiles → player
    surviving = []
    for m in ai.missiles:
        dx, dy = engine.x - m.x, engine.y - m.y
        if dx*dx + dy*dy < (player_r+10)**2:
            engine.receive_damage(m.damage, "AI", "missile")
            if m.is_frost:
                engine.vx *= 0.15; engine.vy *= 0.15
                engine.frost_slow_timer = 3.0
            ai._spawn_explosion(m.x, m.y)
        else:
            surviving.append(m)
    ai.missiles = surviving

    # AI lasers → player
    for laser in ai.lasers:
        dx = math.cos(laser.angle); dy = math.sin(laser.angle)
        ox = engine.x - laser.x;   oy = engine.y - laser.y
        t  = ox*dx + oy*dy
        if t < 0: continue
        px = engine.x - (laser.x + dx*t)
        py = engine.y - (laser.y + dy*t)
        if px*px + py*py < (player_r+10)**2:
            dmg = 20 if laser.special else 15
            engine.receive_damage(dmg, "AI", "laser")


def check_player_attacks_ai(engine: GameEngine, ai: AIEnemy):
    if ai.is_dead: return

    ai_r = 28
    hit_r_sq = (ai_r + 5)**2

    # Player bullets → AI
    hit_ids = set()
    for b in engine.bullets:
        dx, dy = ai.x - b.x, ai.y - b.y
        if dx*dx + dy*dy < hit_r_sq:
            ai.shield -= b.damage
            hit_ids.add(b.id)
            if b.is_frost_sphere:
                spd = math.hypot(ai.vx, ai.vy)
                if spd > 0:
                    ns = max(0, spd-100)
                    ai.vx = ai.vx/spd*ns
                    ai.vy = ai.vy/spd*ns
    if hit_ids:
        engine.bullets = [b for b in engine.bullets if b.id not in hit_ids]

    # Player missiles → AI
    surviving = []
    for m in engine.missiles:
        dx, dy = ai.x - m.x, ai.y - m.y
        if dx*dx + dy*dy < (ai_r+12)**2:
            ai.shield -= m.damage
            engine._spawn_explosion(m.x, m.y)
        else:
            surviving.append(m)
    engine.missiles = surviving

    # Player lasers → AI
    for laser in engine.lasers:
        dx = math.cos(laser.angle); dy = math.sin(laser.angle)
        ox = ai.x - laser.x;        oy = ai.y - laser.y
        t  = ox*dx + oy*dy
        if t < 0: continue
        px = ai.x - (laser.x + dx*t)
        py = ai.y - (laser.y + dy*t)
        if px*px + py*py < (ai_r+10)**2:
            dmg = 20 if laser.special else 15
            ai.shield -= dmg

    # AI death check
    if ai.shield <= 0 and not ai.is_dead:
        ai.is_dead = True
        ai._spawn_explosion(ai.x, ai.y, big=True)
        ai.respawn_timer = AI_RESPAWN_DELAY
        label = "BOSS" if isinstance(ai, BossAI) else "enemy"
        engine.kill_feed.insert(0, KillEntry(f"You destroyed the {label}!"))


# ─────────────────────────────────────────────────────────────────────────────
# MAIN GAME
# ─────────────────────────────────────────────────────────────────────────────

def main():
    pygame.init()
    pygame.display.set_caption("AI Space Shooter")
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    clock  = pygame.time.Clock()

    assets = Assets()
    import os as _os
    asset_dir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "assets")
    assets.load(asset_dir)
    print("=== ASSET DEBUG ===")
    print("Loaded sprites:", list(assets.sprites.keys())[:20])
    print("playerSprite1 loaded?", "playerSprite1" in assets.sprites)
    print("SPRITE_SIZES has playerSprite1?", "playerSprite1" in SPRITE_SIZES)
    print("=====================")
    renderer = Renderer(screen, assets)
    title    = TitleScreen(assets)
    ship_sel = ShipSelectorScreen(assets)

    cur_screen = Screen.TITLE
    engine:      Optional[GameEngine]    = None
    wave_mgr:    Optional[WaveManager]   = None
    powerup_mgr: Optional[PowerupManager]= None
    death_overlay: Optional[DeathOverlay]= None

    keys_down  = set()
    player_id  = str(uuid.uuid4())

    # Time scale: 1.0 = normal, <1 = slow-mo, >1 = fast-forward, 0 = paused
    time_scale        = 1.0
    TIME_SCALE_STEPS  = [0.0, 0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0]
    time_scale_idx    = 5   # index of 1.0 in the list above
    time_scale_notify = 0.0 # seconds to show the speed-change toast

    fps_timer = 0.0
    fps_val   = 60.0

    running = True
    while running:
        raw_dt = min(clock.tick(FPS) / 1000.0, 0.05)
        dt = raw_dt * time_scale          # scaled dt drives all game logic
        if time_scale_notify > 0:
            time_scale_notify -= raw_dt   # notify timer runs at real time

        fps_timer += raw_dt
        if fps_timer >= 0.5:
            fps_val   = clock.get_fps()
            fps_timer = 0.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if cur_screen == Screen.GAME:
                        cur_screen  = Screen.SHIP_SELECT
                        engine      = wave_mgr = powerup_mgr = None
                    else:
                        running = False
                keys_down.add(event.key)

                # ── Time controls (game screen only) ──────────────────────
                if cur_screen == Screen.GAME:
                    if event.key == pygame.K_RIGHTBRACKET:          # ] → faster
                        time_scale_idx = min(time_scale_idx + 1, len(TIME_SCALE_STEPS) - 1)
                        time_scale = TIME_SCALE_STEPS[time_scale_idx]
                        time_scale_notify = 1.5
                    elif event.key == pygame.K_LEFTBRACKET:         # [ → slower
                        time_scale_idx = max(time_scale_idx - 1, 0)
                        time_scale = TIME_SCALE_STEPS[time_scale_idx]
                        time_scale_notify = 1.5
                    elif event.key in (pygame.K_p, pygame.K_BACKSLASH):  # P or \ → pause
                        if time_scale == 0.0:
                            time_scale = TIME_SCALE_STEPS[time_scale_idx] or 1.0
                            if time_scale == 0.0:
                                time_scale_idx = 5
                                time_scale = 1.0
                        else:
                            time_scale = 0.0
                        time_scale_notify = 1.5

                if cur_screen == Screen.TITLE and event.key == pygame.K_RETURN:
                    cur_screen = Screen.SHIP_SELECT
                    ship_sel   = ShipSelectorScreen(assets)

                if cur_screen == Screen.GAME and engine and not engine.is_dead:
                    if event.key in (pygame.K_e, pygame.K_LSHIFT, pygame.K_RSHIFT):
                        engine.activate_special()
                    # Wraith melee
                    if event.key == pygame.K_f and engine.type_special == SpecialType.ALIEN:
                        engine.activate_melee(wave_mgr.enemies if wave_mgr else None)

            if event.type == pygame.KEYUP:
                keys_down.discard(event.key)
                # Wraith: fire blink on key release
                if cur_screen == Screen.GAME and engine and wave_mgr:
                    if event.key in (pygame.K_e, pygame.K_LSHIFT, pygame.K_RSHIFT):
                        engine.release_special(wave_mgr.enemies)

            if cur_screen == Screen.SHIP_SELECT:
                chosen = ship_sel.handle_event(event)
                if chosen:
                    engine      = GameEngine(chosen, player_id)
                    wave_mgr    = WaveManager()
                    powerup_mgr = PowerupManager()
                    cur_screen  = Screen.GAME

        # ── Per-frame logic ──────────────────────────────────────────────

        if cur_screen == Screen.TITLE:
            title.update(dt)

        elif cur_screen == Screen.GAME and engine and wave_mgr and powerup_mgr:
            # Movement input
            dx = dy = 0.0
            if pygame.K_LEFT  in keys_down or pygame.K_a in keys_down: dx -= 1
            if pygame.K_RIGHT in keys_down or pygame.K_d in keys_down: dx += 1
            if pygame.K_UP    in keys_down or pygame.K_w in keys_down: dy -= 1
            if pygame.K_DOWN  in keys_down or pygame.K_s in keys_down: dy += 1
            if dx != 0 or dy != 0:
                mag = math.hypot(dx, dy)
                engine.set_joystick(dx/mag, dy/mag, 1.0)
            else:
                engine.end_joystick()

            engine.fire_active = pygame.K_SPACE in keys_down

            # Missile homing toward nearest alive enemy
            wave_mgr.home_player_missiles(engine, dt)

            # Tick engine
            engine.tick(dt)

            # Tick wave manager (ticks all enemies internally)
            wave_mgr.update(dt, engine)

            # Powerup update
            kill_pos = wave_mgr.kill_positions_this_frame
            powerup_mgr.update(dt, engine, kill_pos)

            engine.shield = max(0.0, engine.shield)

            # Collision checks (player ↔ all enemies)
            wave_mgr.check_collisions(engine)

            # Death handling
            if engine.is_dead:
                if death_overlay is None:
                    death_overlay = DeathOverlay(assets)
                done = death_overlay.update(dt)
                if done:
                    cur_screen    = Screen.SHIP_SELECT
                    engine        = wave_mgr = powerup_mgr = None
                    death_overlay = None
                    ship_sel      = ShipSelectorScreen(assets)

        # ── Draw ────────────────────────────────────────────────────────

        screen.fill((0,0,0))

        if cur_screen == Screen.TITLE:
            title.draw(screen)

        elif cur_screen == Screen.SHIP_SELECT:
            ship_sel.draw(screen)

        elif cur_screen == Screen.GAME and engine and wave_mgr and powerup_mgr:
            renderer.draw_frame(engine, wave_mgr, powerup_mgr, fps_val,
                                time_scale=time_scale, time_scale_notify=time_scale_notify)
            if death_overlay:
                death_overlay.draw(screen)

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
