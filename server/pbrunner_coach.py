"""
=============================================================================
  PBRunner — Coaching Intelligence Engine
  Version : 3.0  (IAAF Elite Template + Rules Engine + ML + Overlay + PDF)
=============================================================================
  Necesita: pbrunner_template.py in acelasi folder

  SETUP:
    pip install mediapipe==0.10.32 opencv-python numpy pandas matplotlib
        scikit-learn reportlab

  Rulare:
    python pbrunner_coach.py --video video1.mp4 --lang ro
    python pbrunner_coach.py --video video1.mp4 --lang en

  Output:
    video1_coached.mp4        — video cu overlay + instructiuni live IAAF
    video1_coach_report.pdf   — raport PDF cu comparatie elita
    video1_coach_data.csv     — date + feedback per frame
    video1_ml_profile.json    — profilul ML al atletului
=============================================================================
"""

import shutil
import subprocess
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from matplotlib.gridspec import GridSpec
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import cv2
import numpy as np
import pandas as pd
import json
import argparse
import os
import sys
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple
from collections import deque

import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

import matplotlib
matplotlib.use("Agg")

# ML skeleton — folosit acum pentru clustering de baza,
# extins cu date reale mai tarziu

# IAAF Elite Reference Template
try:
    from pbrunner_template import (
        AthleteProfile, IAAFCoachEngine,
        create_default_profile, IAAF_TOUCHDOWN, IAAF_KINEMATICS
    )
    IAAF_AVAILABLE = True
except ImportError:
    IAAF_AVAILABLE = False
    print("[WARN] pbrunner_template.py negasit — se folosesc regulile de baza")


# ─────────────────────────────────────────────────────────────────────────────
# REENCODE PENTRU MOBIL (ANDROID/iOS)
# OpenCV produce H264 cu profil High care nu e suportat pe multe telefoane.
# ffmpeg face conversia la H264 Baseline + yuv420p + faststart (incepe rapid).
# ─────────────────────────────────────────────────────────────────────────────


def reencode_for_mobile(input_path: str) -> str:
    """
    Re-encodeaza videoul output cu ffmpeg pentru compatibilitate maxima
    pe telefoane Android si iOS.

    Daca ffmpeg nu e instalat sau eșueaza, returneaza fisierul original
    si printeaza un warning (nu rupe pipeline-ul).
    """
    if not shutil.which("ffmpeg"):
        print("  [WARN] ffmpeg nu e instalat — video ramane in formatul OpenCV.")
        print("         Instaleaza: winget install ffmpeg  (apoi restart VS Code)")
        return input_path

    if not os.path.exists(input_path):
        return input_path

    # Output: acelasi nume dar cu sufix _mobile
    base, ext = os.path.splitext(input_path)
    tmp_path = base + "_tmp_mobile.mp4"

    cmd = [
        "ffmpeg",
        "-y",                          # suprascrie fara intrebari
        "-i", input_path,              # input
        "-c:v", "libx264",             # codec H264
        "-profile:v", "baseline",      # profil compatibil cu orice telefon
        "-level", "3.1",               # nivel 3.1 = max 1280x720@30fps
        # scale down la max 1280px latime
        "-vf", "scale='if(gt(iw,1280),1280,iw)':-2",
        "-pix_fmt", "yuv420p",         # format pixel cerut de Android
        "-preset", "fast",             # echilibru viteza/calitate
        "-crf", "23",                  # calitate buna (0=lossless, 51=worst)
        "-movflags", "+faststart",     # metadate la inceput → playback rapid
        "-an",                         # fara audio (videoul oricum nu are)
        "-loglevel", "error",          # doar erorile
        tmp_path,
    ]

    print(f"  [ffmpeg] Re-encodare pentru mobil...")
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            print(f"  [WARN] ffmpeg a esuat: {result.stderr[:200]}")
            return input_path

        # Inlocuim originalul cu cel re-encodat
        os.replace(tmp_path, input_path)
        size_mb = os.path.getsize(input_path) / (1024 * 1024)
        print(f"  [ffmpeg] OK — {size_mb:.1f} MB, compatibil mobil")
        return input_path

    except subprocess.TimeoutExpired:
        print("  [WARN] ffmpeg timeout (>5min). Pastram fisierul OpenCV.")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return input_path
    except Exception as e:
        print(f"  [WARN] ffmpeg eroare: {e}")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return input_path


# ─────────────────────────────────────────────────────────────────────────────
# CONFIG GLOBAL
# ─────────────────────────────────────────────────────────────────────────────
MODEL_PATH = "pose_landmarker.task"
PANEL_W = 300   # latime panou lateral (mai lat pentru instructiuni)

# Limbi disponibile
LANG = "ro"   # suprascris de --lang

# Profilul atletului — initializat in process_video()
ATHLETE_PROFILE = None
IAAF_COACH = None

# ─────────────────────────────────────────────────────────────────────────────
# BAZA DE CUNOASTINTE BIOMECANICE
# Surse: IAAF Biomechanics Research Project, World Athletics Technical Reports
# Format: (optim_min, optim_max, acceptable_min, acceptable_max)
# ─────────────────────────────────────────────────────────────────────────────
BIOMECH_RANGES = {
    # Blockstart
    "blockstart": {
        "knee_front":      (85,  100,  75,  115),
        "knee_rear":       (115, 135, 100,  150),
        "hip":             (35,   55,  25,   70),
        "trunk":           (10,   30,   5,   45),
        "ankle":           (60,   80,  50,   90),
        "elbow":           (85,  100,  70,  115),
    },
    # Acceleratie
    "acceleratie": {
        "knee_L":          (100, 150,  80,  165),
        "knee_R":          (100, 150,  80,  165),
        "hip_L":           (60, 110,  45,  130),
        "hip_R":           (60, 110,  45,  130),
        "trunk":           (25,  55,  15,   70),
        "elbow_L":         (80, 105,  65,  120),
        "elbow_R":         (80, 105,  65,  120),
        "ankle_L":         (65,  90,  50,  100),
        "ankle_R":         (65,  90,  50,  100),
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# INSTRUCTIUNI COACHING — bilingv
# Structura: {cheie_problema: {ro: "...", en: "..."}}
# ─────────────────────────────────────────────────────────────────────────────
COACHING_CUES = {
    # ── BLOCKSTART ───────────────────────────────────────────────────────────
    "bs_trunk_too_vertical": {
        "ro": "Apleca trunchiul mai mult inainte la start — vizezi ~20gr fata de orizontala",
        "en": "Lean your trunk further forward at start — aim for ~20deg from horizontal",
        "priority": 1, "phase": "BLOCKSTART",
        "arrow": "down-forward",
    },
    "bs_trunk_too_flat": {
        "ro": "Ridica putin trunchiul — esti prea aplecat, reduci forta de propulsie",
        "en": "Raise your trunk slightly — too flat reduces propulsion force",
        "priority": 2, "phase": "BLOCKSTART",
        "arrow": "up",
    },
    "bs_knee_front_too_open": {
        "ro": "Flecteaza mai mult genunchiul din fata — adanceste pozitia in block",
        "en": "Flex your front knee more — deepen your block position",
        "priority": 1, "phase": "BLOCKSTART",
        "arrow": "down",
    },
    "bs_knee_front_too_closed": {
        "ro": "Deschide genunchiul din fata — unghiul optim este 85-100gr",
        "en": "Open your front knee — optimal angle is 85-100deg",
        "priority": 2, "phase": "BLOCKSTART",
        "arrow": "up",
    },
    "bs_hip_too_high": {
        "ro": "Coboara soldurile — pozitia soldului trebuie sa fie sub linia umerilor",
        "en": "Lower your hips — hip position should be below shoulder line",
        "priority": 1, "phase": "BLOCKSTART",
        "arrow": "down",
    },
    "bs_ankle_too_open": {
        "ro": "Impinge piciorul mai ferm in block — flexia gleznei trebuie sa fie activa",
        "en": "Push foot firmer into block — ankle dorsiflexion must be active",
        "priority": 3, "phase": "BLOCKSTART",
        "arrow": "forward",
    },
    "bs_elbow_too_open": {
        "ro": "Strange cotul — bratele suporta greutatea, cotul la ~90gr",
        "en": "Close your elbow — arms support weight, elbow at ~90deg",
        "priority": 3, "phase": "BLOCKSTART",
        "arrow": "close",
    },

    # ── ACCELERATIE ──────────────────────────────────────────────────────────
    "acc_trunk_too_vertical": {
        "ro": "Mentine inclinatia trunchiului inainte — nu te ridica prea repede",
        "en": "Keep trunk inclined forward — do not rise too early",
        "priority": 1, "phase": "ACCELERATIE",
        "arrow": "forward",
    },
    "acc_knee_too_closed": {
        "ro": "Extinde mai complet genunchiul la propulsie — impinge pana la capat",
        "en": "Extend knee more fully at push-off — drive all the way through",
        "priority": 1, "phase": "ACCELERATIE",
        "arrow": "extend",
    },
    "acc_knee_recovery_low": {
        "ro": "Ridica genunchiul mai sus la recuperare — accelereaza ciclul pasului",
        "en": "Drive knee higher on recovery — accelerate stride cycle",
        "priority": 2, "phase": "ACCELERATIE",
        "arrow": "up",
    },
    "acc_hip_too_closed": {
        "ro": "Extinde soldul complet la fiecare pas — maximizeaza lungimea pasului",
        "en": "Fully extend hip each stride — maximize stride length",
        "priority": 1, "phase": "ACCELERATIE",
        "arrow": "extend",
    },
    "acc_elbow_too_open": {
        "ro": "Mentine cotul la ~90gr in miscare — bratele eficiente = viteza mai mare",
        "en": "Keep elbow at ~90deg throughout — efficient arms = higher speed",
        "priority": 2, "phase": "ACCELERATIE",
        "arrow": "close",
    },
    "acc_ankle_passive": {
        "ro": "Activeaza glezna la contactul cu solul — aterizeaza pe metatars, nu pe calcai",
        "en": "Activate ankle at ground contact — land on forefoot, not heel",
        "priority": 2, "phase": "ACCELERATIE",
        "arrow": "forward",
    },

    # ── UNIVERSAL ────────────────────────────────────────────────────────────
    "head_forward": {
        "ro": "Relaxeaza gatul — capul trebuie sa fie in prelungirea coloanei",
        "en": "Relax your neck — head should align with spine",
        "priority": 3, "phase": "ALL",
        "arrow": "neutral",
    },
    "asymmetry_knees": {
        "ro": "Asimetrie genunchi detectata — lucreaza la echilibrarea celor doua picioare",
        "en": "Knee asymmetry detected — work on balancing both legs",
        "priority": 2, "phase": "ALL",
        "arrow": "neutral",
    },
    "asymmetry_arms": {
        "ro": "Asimetrie brate detectata — sincronizeaza miscarea bratelor",
        "en": "Arm asymmetry detected — synchronize arm swing",
        "priority": 2, "phase": "ALL",
        "arrow": "neutral",
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# CULORI UI
# ─────────────────────────────────────────────────────────────────────────────


class C:
    HEAD = (200,  80, 255)
    SPINE = (0, 165, 255)
    HORIZ = (0, 240, 240)
    ARM = (255, 180,   0)
    LEG = (0, 210, 255)
    FOOT = (80, 255, 120)
    JT_SM = (200, 200, 200)
    JT_LG = (0, 200, 255)
    GOOD = (0, 210,   0)
    WARN = (0, 165, 255)
    BAD = (30,  30, 220)
    PANEL = (10,  10,  16)
    WHITE = (240, 240, 240)
    DIM = (120, 120, 130)
    PHASE = {
        "BLOCKSTART":  (255, 140,   0),
        "ACCELERATIE": (0, 210, 255),
        "ANALIZA...":  (140, 140, 140),
    }
    P1 = (30,  30, 220)   # prioritate 1 — critica
    P2 = (0, 165, 255)   # prioritate 2 — importanta
    P3 = (0, 160,   0)   # prioritate 3 — optimizare

# ─────────────────────────────────────────────────────────────────────────────
# MATEMATICA
# ─────────────────────────────────────────────────────────────────────────────


def angle_3pts(a, b, c):
    ba = a - b
    bc = c - b
    d = np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-8
    return round(float(np.degrees(np.arccos(np.clip(np.dot(ba, bc)/d, -1, 1)))), 1)


def angle_vertical(top, bot):
    v = bot - top
    return round(float(np.degrees(np.arccos(np.clip(v[1]/(np.linalg.norm(v)+1e-8), -1, 1)))), 1)


def lm_px(lms, i, W, H):
    p = lms[i]
    return np.array([p.x*W, p.y*H])


def quality_color(value, mn_o, mx_o, mn_a, mx_a):
    if mn_o <= value <= mx_o:
        return C.GOOD
    if mn_a <= value <= mx_a:
        return C.WARN
    return C.BAD

# ─────────────────────────────────────────────────────────────────────────────
# DETECTARE FAZA — State Machine biomecanic
# Functioneaza de la primul frame, fara minimum de history
#
# Conventie unghi trunchi (angle_vertical(msh, mhip), Y creste in jos):
#   0°       = trunchi perfect vertical (stat in picioare)
#   45°      = trunchi inclinat 45° fata de vertical
#   90°      = trunchi orizontal (culcat)
#   >90°     = sold mai sus decat umarul (SET position in blocuri)
#
# Faze sprint cu praguri corecte:
#   SET         : trunchi >55° (sold ridicat, maini pe sol)
#   BLOCKSTART  : trunchi 38-75° + miscare detectata
#   ACCELERATIE : trunchi 15-55°
# ─────────────────────────────────────────────────────────────────────────────


class PhaseDetector:
    """
    Detecteaza faza sprintului frame cu frame, fara minimum de history.
    Foloseste State Machine cu persistenta pentru a evita flickering.
    """

    # Ordinea progresiei fazelor (nu poti regresa)
    PHASE_ORDER = {"SET": 0, "BLOCKSTART": 1,
                   "ACCELERATIE": 2}
    # Cate frame-uri trebuie sa confirme o faza noua inainte de tranzitie
    CONFIRM_N = 3

    def __init__(self):
        self.state = "SET"          # faza curenta confirmata
        self.candidate = "SET"          # faza candidata (neconfirmata inca)
        self.candidate_n = 0              # cate frame-uri consecutive sugereaza candidatul
        self.state_frames = 0             # cate frame-uri suntem in starea curenta
        self.history = []             # ultimele N unghi-uri
        self.hip_x_hist = []             # pentru detectia miscarii CM
        self.ever_moved = False          # a inceput vreodata miscarea?

    def update(self, angles: dict, lms_pos: dict) -> str:
        """
        angles   : dict cu unghiuri calculate
        lms_pos  : dict de la compute_seg_lengths cu pozitii reale
        Returneaza faza display (string).
        """
        trunk = angles.get("trunk", 45.0)
        knee_avg = (angles.get("knee_L", 130) + angles.get("knee_R", 130)) / 2

        hip_c = lms_pos["hip_c"]
        sh_c = lms_pos["sh_c"]
        ground_y = lms_pos.get("ground_y", hip_c[1] + 100)

        # ── Viteza orizontala CM ────────────────────────────────────────
        self.hip_x_hist.append(float(hip_c[0]))
        if len(self.hip_x_hist) > 8:
            self.hip_x_hist.pop(0)
        h_vel = 0.0
        if len(self.hip_x_hist) >= 3:
            h_vel = abs(self.hip_x_hist[-1] -
                        self.hip_x_hist[0]) / len(self.hip_x_hist)
        if h_vel > 2.5:
            self.ever_moved = True

        # ── Wrist pe sol? ───────────────────────────────────────────────
        # body_h = distanta sold-umar in pixeli (referinta pentru corp)
        body_h = max(abs(float(hip_c[1]) - float(sh_c[1])), 20)
        lwr = lms_pos.get("lwr")
        rwr = lms_pos.get("rwr")
        wrist_on_ground = False
        if lwr is not None and rwr is not None:
            best_wrist_y = max(float(lwr[1]), float(rwr[1]))  # cel mai jos
            # Daca wrist e in ultimele 30% din distanta sold→sol → pe sol
            wrist_to_ground = abs(ground_y - best_wrist_y)
            wrist_on_ground = wrist_to_ground < body_h * 0.55

        # ── Clasifica faza curenta din semnale directe ──────────────────
        #
        # SET: sold ridicat, trunchi aproape orizontal (>55°),
        #      maini aproape de sol sau miscare mica
        if trunk > 55 and (wrist_on_ground or h_vel < 3.0):
            raw = "SET"
        # BLOCKSTART drive: trunchi foarte inclinat SI miscandu-se
        elif trunk > 38 and (self.ever_moved or h_vel > 1.5) and knee_avg < 155:
            raw = "BLOCKSTART"
        elif trunk <= 55:
            raw = "ACCELERATIE"
        else:
            raw = "BLOCKSTART"   # fallback

        # ── State machine: confirmare + fara regresie ───────────────────
        new_ord = self.PHASE_ORDER.get(raw, 0)
        cur_ord = self.PHASE_ORDER.get(self.state, 0)

        if raw == self.state:
            # Suntem deja in aceasta faza
            self.candidate = raw
            self.candidate_n = 0
            self.state_frames += 1
        elif new_ord >= cur_ord:
            # Candidat spre o faza progresiva (inainte in ordine)
            if raw == self.candidate:
                self.candidate_n += 1
            else:
                self.candidate = raw
                self.candidate_n = 1
            if self.candidate_n >= self.CONFIRM_N:
                self.state = raw
                self.state_frames = 0
                self.candidate_n = 0
        # Altfel: incercare de regresie → ignoram

        # Display: "SET" apare ca "BLOCKSTART" in panel
        return self.state

    def display_phase(self) -> str:
        """Returneaza faza pentru afisare pe ecran."""
        return self.state


# ── Instanta globala (reinitializata in process_video) ─────────────────────
_PHASE_DETECTOR: "PhaseDetector | None" = None


def detect_phase(history, lms_pos: dict = None, angles: dict = None) -> str:
    """
    Wrapper pentru compatibilitate cu codul existent.
    Daca are PhaseDetector global initializat, il foloseste.
    Altfel fallback la metoda veche (nu mai e folosit in mod normal).
    """
    global _PHASE_DETECTOR
    if _PHASE_DETECTOR is not None and lms_pos is not None and angles is not None:
        return _PHASE_DETECTOR.update(angles, lms_pos)
    # Fallback legacy (nu mai ajunge aici in mod normal)
    if not history:
        return "ANALIZA..."
    r = history[-min(len(history), 6):]
    trunk = np.mean([x.get("trunk", 45) for x in r])
    if trunk > 55:
        return "SET"
    if trunk > 38:
        return "BLOCKSTART"
    if trunk > 15:
        return "ACCELERATIE"

# ─────────────────────────────────────────────────────────────────────────────
# 1. DETECTIE MOMENTE CRITICE
# ─────────────────────────────────────────────────────────────────────────────


class CriticalMomentDetector:
    """
    Detecteaza automat momentele cheie din sprint si le timestampeaza.
    Ruleaza pe fiecare frame si semnalizeaza evenimentele detectate.
    """
    EVENTS = {
        "RELEASE_BLOCKS":    {"ro": "Release din blocuri",        "en": "Block release",           "col": (255, 140,  0)},
        "FIRST_CONTACT":     {"ro": "Primul contact sol",         "en": "First ground contact",    "col": (0, 210, 255)},
        "PHASE_BS_TO_ACC":   {"ro": "Start acceleratie",          "en": "Acceleration start",      "col": (0, 210, 255)},
        "ASYM_SPIKE":        {"ro": "Asimetrie critica detectata", "en": "Critical asymmetry",      "col": (30, 30, 220)},
        "OPTIMAL_FORM":      {"ro": "Forma optima IAAF",          "en": "IAAF optimal form",       "col": (0, 210,  0)},
    }

    def __init__(self, src_fps: float):
        self.fps = src_fps
        self.prev_phase = None
        self.detected = []          # lista {event, frame, time_s, details}
        self._bs_seen = False
        self._fc_seen = False
        self._knee_hist = []          # pentru detectie peak speed
        self._score_hist = []          # pentru detectie forma optima
        self._active_event = None      # evenimentul curent de afisat pe frame
        self._event_ttl = 0         # frames ramase pentru afisare

    def update(self, angles: dict, phase: str, frame_idx: int,
               ankle_y_L: float, ankle_y_R: float) -> Optional[dict]:
        """
        Apelat fiecare frame. Returneaza evenimentul detectat (sau None).
        ankle_y_L/R = coordonata Y a gleznei in pixeli (mai mare = mai jos).
        """
        t = frame_idx / self.fps
        event = None

        # ── Release din blocuri ───────────────────────────────────────────
        if not self._bs_seen and phase == "BLOCKSTART":
            self._bs_seen = True
        if self._bs_seen and not self._fc_seen and phase != "BLOCKSTART":
            self._fc_seen = True
            event = self._fire("RELEASE_BLOCKS", frame_idx, t,
                               f"Frame {frame_idx} | {t:.2f}s")

        # ── Primul contact sol (glezna coboara sub prag dupa release) ─────
        if self._bs_seen and not self._fc_seen:
            pass  # inca in blockstart
        if self._fc_seen and len(self.detected) == 1:
            # Prima aterizare: glezna la inaltime maxima (y mic in imagine)
            avg_ankle_y = (ankle_y_L + ankle_y_R) / 2
            if not hasattr(self, '_fc_fired'):
                self._fc_fired = False
            if not self._fc_fired and avg_ankle_y > 0:
                self._fc_fired = True
                event = event or self._fire("FIRST_CONTACT", frame_idx, t,
                                            f"Frame {frame_idx} | {t:.2f}s")

        # ── Tranzitii de faza ──────────────────────────────────────────────
        if self.prev_phase and phase != self.prev_phase:
            if self.prev_phase == "BLOCKSTART" and phase == "ACCELERATIE":
                event = event or self._fire("PHASE_BS_TO_ACC", frame_idx, t,
                                            f"Frame {frame_idx} | {t:.2f}s")

        # ── Asimetrie critica ──────────────────────────────────────────────
        kd = abs(angles["knee_L"] - angles["knee_R"])
        ed = abs(angles["elbow_L"] - angles["elbow_R"])
        if (kd > 35 or ed > 35) and not hasattr(self, '_asym_cooldown'):
            self._asym_cooldown = frame_idx + int(self.fps * 2)
            event = event or self._fire("ASYM_SPIKE", frame_idx, t,
                                        f"Genunchi: {kd:.0f}gr | Cot: {ed:.0f}gr")
        if hasattr(self, '_asym_cooldown') and frame_idx > self._asym_cooldown:
            del self._asym_cooldown

        # ── Forma optima ───────────────────────────────────────────────────
        if IAAF_AVAILABLE and ATHLETE_PROFILE is not None:
            sc = compute_phase_score(angles, phase)
            self._score_hist.append(sc)
            if len(self._score_hist) > 10:
                self._score_hist.pop(0)
            avg_sc = np.mean(self._score_hist)
            if avg_sc >= 85 and not hasattr(self, '_optimal_cooldown'):
                self._optimal_cooldown = frame_idx + int(self.fps * 3)
                event = event or self._fire("OPTIMAL_FORM", frame_idx, t,
                                            f"Scor: {avg_sc:.0f}/100")
            if hasattr(self, '_optimal_cooldown') and frame_idx > self._optimal_cooldown:
                del self._optimal_cooldown

        self.prev_phase = phase
        if event:
            self._active_event = event
            self._event_ttl = int(self.fps * 3)   # afisat 3 secunde
        elif self._event_ttl > 0:
            self._event_ttl -= 1
        else:
            self._active_event = None

        return event

    def _fire(self, key: str, frame: int, t: float, details: str) -> dict:
        ev = {"event": key, "frame": frame, "time_s": t,
              "details": details,
              "label_ro": self.EVENTS[key]["ro"],
              "label_en": self.EVENTS[key]["en"],
              "col":      self.EVENTS[key]["col"]}
        self.detected.append(ev)
        print(f"  [EVENT] {t:.2f}s — {self.EVENTS[key]['ro']} ({details})")
        return ev

    def draw_event_overlay(self, frame):
        """Deseneaza evenimentul curent pe frame (banner sus-centru)."""
        if not self._active_event:
            return
        ev = self._active_event
        col = ev["col"]
        lbl = ev["label_ro"] if LANG == "ro" else ev["label_en"]
        t = ev["time_s"]
        txt = f"  {lbl}  @{t:.2f}s  "
        font = cv2.FONT_HERSHEY_SIMPLEX
        H, W_f = frame.shape[:2]
        (tw, th), _ = cv2.getTextSize(txt, font, 0.72, 2)
        px = (W_f - tw) // 2
        py = 52
        # Fundal semi-transparent
        overlay = frame.copy()
        cv2.rectangle(overlay, (px-8, py-th-10), (px+tw+8, py+8),
                      (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)
        # Border colorat
        cv2.rectangle(frame, (px-8, py-th-10), (px+tw+8, py+8), col, 2)
        cv2.putText(frame, txt, (px, py), font, 0.72, col, 2, cv2.LINE_AA)
        # Progres bar (cat timp mai e afisat)
        frac = self._event_ttl / max(int(self.fps * 3), 1)
        bw = int((tw + 16) * frac)
        cv2.rectangle(frame, (px-8, py+8), (px-8+bw, py+11), col, -1)

    def summary(self) -> list:
        return self.detected


# ─────────────────────────────────────────────────────────────────────────────
# 2. SCOR GLOBAL 0-100 PER FAZA (comparatie cu elita IAAF)
# ─────────────────────────────────────────────────────────────────────────────

def compute_phase_score(angles: dict, phase: str) -> float:
    """
    Calculeaza scorul 0-100 al atletului pentru faza curenta.
    100 = perfect in intervalul optim IAAF pe toate articulatiile.
    0   = toate unghiurile in afara intervalului acceptabil.
    """
    ph_key = {"BLOCKSTART": "blockstart", "ACCELERATIE": "acceleratie",
              "ANALIZA...": "acceleratie"}.get(phase, "acceleratie")

    if IAAF_AVAILABLE and ATHLETE_PROFILE is not None:
        rng_map = ATHLETE_PROFILE.ranges.get(ph_key, {})
    else:
        rng_map = BIOMECH_RANGES.get(ph_key, {})

    scores = []
    angle_to_rng = {
        "trunk":    ["trunk", "trunk_TD", "trunk_TO"],
        "knee_L":   ["knee_L", "knee_L_TD", "knee_front"],
        "knee_R":   ["knee_R", "knee_R_TD"],
        "hip_L":    ["hip_L", "hip_contact"],
        "hip_R":    ["hip_R"],
        "ankle_L":  ["ankle_L", "ankle_L_TD"],
        "ankle_R":  ["ankle_R", "ankle_R_TD"],
        "elbow_L":  ["elbow_L"],
        "elbow_R":  ["elbow_R"],
    }
    for ang_key, rng_keys in angle_to_rng.items():
        val = angles.get(ang_key)
        if val is None:
            continue
        rng = None
        for rk in rng_keys:
            if rk in rng_map:
                rng = rng_map[rk]
                break
        if rng is None:
            continue
        mn_o, mx_o, mn_a, mx_a = rng
        opt_center = (mn_o + mx_o) / 2
        opt_half = (mx_o - mn_o) / 2
        acc_half = (mx_a - mn_a) / 2
        dist = abs(val - opt_center)
        if dist <= opt_half:
            sc = 100.0
        elif dist <= acc_half:
            # Liniar 50-99 intre banda optima si banda acceptabila
            frac = (dist - opt_half) / max(acc_half - opt_half, 1)
            sc = 99.0 - frac * 49.0
        else:
            # Sub 50, descrestere exponentiala dincolo de acceptabil
            excess = dist - acc_half
            sc = max(0.0, 50.0 - excess * 2.5)
        scores.append(sc)

    return round(float(np.mean(scores)) if scores else 0.0, 1)


def score_color_bgr(score: float):
    """Verde (100) → Galben (70) → Rosu (0)"""
    if score >= 85:
        return (0, 210,   0)   # verde
    if score >= 65:
        return (0, 165, 255)   # portocaliu
    return (30,  30, 220)   # rosu


def draw_score_on_frame(frame, score: float, phase: str):
    """Deseneaza scorul mare in coltul dreapta-sus al frame-ului."""
    font = cv2.FONT_HERSHEY_SIMPLEX
    col = score_color_bgr(score)
    H_f, W_f = frame.shape[:2]

    # Fundal
    box_w, box_h = 110, 68
    bx = W_f - box_w - 10
    by = 8
    overlay = frame.copy()
    cv2.rectangle(overlay, (bx, by), (bx+box_w, by+box_h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)
    cv2.rectangle(frame, (bx, by), (bx+box_w, by+box_h), col, 2)

    # Scor mare
    sc_txt = f"{score:.0f}"
    (tw, th), _ = cv2.getTextSize(sc_txt, font, 1.6, 3)
    cv2.putText(frame, sc_txt,
                (bx + (box_w-tw)//2, by + th + 8),
                font, 1.6, col, 3, cv2.LINE_AA)
    # Label
    lbl = "/100" if LANG == "ro" else "/100"
    cv2.putText(frame, lbl, (bx + box_w//2 - 14, by + box_h - 6),
                font, 0.38, col, 1, cv2.LINE_AA)


# ─────────────────────────────────────────────────────────────────────────────
# 3. ANALIZA SIMETRIE STANGA/DREAPTA
# ─────────────────────────────────────────────────────────────────────────────

class SymmetryTracker:
    """Acumuleaza date pentru graficul de simetrie."""

    def __init__(self):
        self.data: List[dict] = []

    def add(self, angles: dict, frame_idx: int, time_s: float, phase: str):
        self.data.append({
            "frame":     frame_idx,
            "time_s":    time_s,
            "phase":     phase,
            "knee_diff": abs(angles["knee_L"] - angles["knee_R"]),
            "hip_diff":  abs(angles["hip_L"] - angles["hip_R"]),
            "ankle_diff": abs(angles["ankle_L"] - angles["ankle_R"]),
            "elbow_diff": abs(angles["elbow_L"] - angles["elbow_R"]),
            "knee_L":    angles["knee_L"], "knee_R":  angles["knee_R"],
            "hip_L":     angles["hip_L"],  "hip_R":   angles["hip_R"],
            "elbow_L":   angles["elbow_L"], "elbow_R": angles["elbow_R"],
        })

    def to_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.data)

    def summary(self) -> dict:
        if not self.data:
            return {}
        df = self.to_df()
        return {k: {"mean": round(df[k].mean(), 1),
                    "max":  round(df[k].max(), 1),
                    "pct_asymmetric": round((df[k] > 15).mean()*100, 1)}
                for k in ["knee_diff", "hip_diff", "ankle_diff", "elbow_diff"]}


def generate_symmetry_chart(sym_df: pd.DataFrame, output_path: str, video_name: str):
    """Grafic dedicat simetrie stanga/dreapta — 4 panouri + radar."""
    if sym_df.empty:
        return

    fig = plt.figure(figsize=(18, 12), facecolor="#0D0D14")
    fig.suptitle(f"PBRunner — Analiza Simetrie L/R\n{video_name}",
                 color="white", fontsize=14, fontweight="bold", y=0.98)

    gs = GridSpec(3, 4, figure=fig, hspace=0.55, wspace=0.38,
                  left=0.06, right=0.97, top=0.91, bottom=0.07)

    t = sym_df["time_s"].values
    phase_mpl = {"BLOCKSTART": "#FF8C00", "ACCELERATIE": "#00D4FF", }

    def styled(ax):
        ax.set_facecolor("#12121E")
        for sp in ax.spines.values():
            sp.set_color("#2a2a3a")
        ax.tick_params(colors="#888", labelsize=8)
        ax.grid(True, color="#1e1e2e", lw=0.7, ls="--")
        ax.yaxis.label.set_color("#aaa")
        ax.xaxis.label.set_color("#aaa")
        ax.title.set_color("#ddd")

    def shade(ax):
        if "phase" not in sym_df.columns:
            return
        prev_ph = None
        prev_t = t[0]
        for _, row in sym_df.iterrows():
            ph = row["phase"]
            if ph != prev_ph:
                if prev_ph:
                    ax.axvspan(prev_t, row["time_s"], alpha=0.08,
                               color=phase_mpl.get(prev_ph, "#888"))
                prev_ph = ph
                prev_t = row["time_s"]
        if prev_ph:
            ax.axvspan(prev_t, t[-1], alpha=0.08,
                       color=phase_mpl.get(prev_ph, "#888"))

    # Threshold line helper
    def thresh(ax, val=15, label="Prag asimetrie"):
        ax.axhline(val, color="#DD2222", ls="--", lw=1.2, alpha=0.7)
        ax.text(t[-1]*0.02, val+1, label, color="#DD2222",
                fontsize=7, va="bottom")

    pairs = [
        ("knee_L",  "knee_R",  "knee_diff",  "Genunchi",  gs[0, 0], gs[0, 1]),
        ("hip_L",   "hip_R",   "hip_diff",   "Sold",      gs[1, 0], gs[1, 1]),
        ("elbow_L", "elbow_R", "elbow_diff", "Cot",       gs[2, 0], gs[2, 1]),
    ]

    for lk, rk, dk, name, spec_lr, spec_diff in pairs:
        # Panel L vs R
        ax1 = fig.add_subplot(spec_lr)
        styled(ax1)
        shade(ax1)
        sm_l = sym_df[lk].rolling(5, center=True, min_periods=1).mean()
        sm_r = sym_df[rk].rolling(5, center=True, min_periods=1).mean()
        ax1.plot(t, sym_df[lk].values, color="#00D4FF", alpha=0.18, lw=0.8)
        ax1.plot(t, sm_l.values, color="#00D4FF", alpha=0.9, lw=1.6,
                 label=f"{name} STG")
        ax1.plot(t, sym_df[rk].values, color="#FF8C00", alpha=0.18, lw=0.8)
        ax1.plot(t, sm_r.values, color="#FF8C00", alpha=0.9, lw=1.6,
                 label=f"{name} DRP")
        ax1.set_title(f"{name} — STG vs DRP (gr)", fontsize=9, pad=4)
        ax1.set_xlabel("timp (s)", fontsize=7)
        ax1.legend(fontsize=7, facecolor="#1a1a28", edgecolor="#333",
                   labelcolor="white", loc="upper right")

        # Panel diferenta
        ax2 = fig.add_subplot(spec_diff)
        styled(ax2)
        shade(ax2)
        sm_d = sym_df[dk].rolling(5, center=True, min_periods=1).mean()
        ax2.fill_between(t, sym_df[dk].values, alpha=0.15, color="#DD2222")
        ax2.plot(t, sm_d.values, color="#DD2222", lw=1.8,
                 label=f"Diferenta {name}")
        thresh(ax2)
        pct = (sym_df[dk] > 15).mean() * 100
        ax2.set_title(
            f"Asimetrie {name} ({pct:.0f}% peste prag)", fontsize=9, pad=4)
        ax2.set_xlabel("timp (s)", fontsize=7)
        ax2.legend(fontsize=7, facecolor="#1a1a28", edgecolor="#333",
                   labelcolor="white")

    # Radar chart — simetrie medie per articulatie
    ax_r = fig.add_subplot(gs[:, 2:], polar=True)
    ax_r.set_facecolor("#12121E")
    ax_r.spines["polar"].set_color("#2a2a3a")
    ax_r.tick_params(colors="#888", labelsize=8)
    ax_r.yaxis.label.set_color("#aaa")
    ax_r.title.set_color("#ddd")

    cats = ["Genunchi", "Sold", "Glezna", "Cot"]
    means = [sym_df["knee_diff"].mean(),  sym_df["hip_diff"].mean(),
             sym_df["ankle_diff"].mean(), sym_df["elbow_diff"].mean()]
    # Scor simetrie: 100 - mean_diff (cu cap la 0)
    scores_sym = [max(0, 100 - m*3) for m in means]
    N = len(cats)
    angles_r = [n / float(N) * 2 * np.pi for n in range(N)]
    angles_r += angles_r[:1]
    scores_sym += scores_sym[:1]

    ax_r.set_theta_offset(np.pi / 2)
    ax_r.set_theta_direction(-1)
    ax_r.set_xticks(angles_r[:-1])
    ax_r.set_xticklabels(cats, color="white", size=9)
    ax_r.set_ylim(0, 100)
    ax_r.set_yticks([25, 50, 75, 100])
    ax_r.set_yticklabels(["25", "50", "75", "100"], color="#666", size=7)

    ax_r.plot(angles_r, scores_sym, "o-", lw=2, color="#00D4FF")
    ax_r.fill(angles_r, scores_sym, alpha=0.18, color="#00D4FF")
    # Referinta elita (90/100)
    elite = [90]*N + [90]
    ax_r.plot(angles_r, elite, "--", lw=1, color="#00DC00", alpha=0.6,
              label="Referinta IAAF")
    ax_r.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1),
                facecolor="#1a1a28", edgecolor="#333", labelcolor="white",
                fontsize=8)
    ax_r.set_title("Scor Simetrie per Articulatie", color="white",
                   fontsize=11, pad=20)

    plt.savefig(output_path, dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close()
    print(f"  Simetrie: {output_path}")


# ─────────────────────────────────────────────────────────────────────────────
# 4. WATERMARK + ATHLETE NAME + END CARD
# ─────────────────────────────────────────────────────────────────────────────

ATHLETE_NAME = "Atlet"   # suprascris din --name argument


def draw_watermark(frame):
    """PBRunner watermark subtil in coltul stanga-jos."""
    H_f, W_f = frame.shape[:2]
    font = cv2.FONT_HERSHEY_SIMPLEX
    txt = "PBRunner v1.0"
    (tw, th), _ = cv2.getTextSize(txt, font, 0.38, 1)
    x, y = 10, H_f - 10
    cv2.putText(frame, txt, (x+1, y+1), font, 0.38, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.putText(frame, txt, (x,   y), font, 0.38, (60, 60, 80), 1, cv2.LINE_AA)


def draw_athlete_name(frame):
    """Numele atletului in coltul dreapta-jos."""
    if not ATHLETE_NAME or ATHLETE_NAME == "Atlet":
        return
    H_f, W_f = frame.shape[:2]
    font = cv2.FONT_HERSHEY_SIMPLEX
    txt = ATHLETE_NAME
    (tw, th), _ = cv2.getTextSize(txt, font, 0.48, 1)
    x, y = W_f - tw - 12, H_f - 10
    cv2.putText(frame, txt, (x+1, y+1), font, 0.48, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.putText(frame, txt, (x,   y), font, 0.48,
                (0, 200, 255), 1, cv2.LINE_AA)


def generate_end_card(frame_shape, scores_by_phase: dict,
                      top_feedback: list, events: list,
                      sym_summary: dict, duration_s: float) -> np.ndarray:
    """
    Genereaza un frame final (end card) cu rezumatul sesiunii.
    Afisat ultimele 3 secunde ale videoclipului output.
    """
    H, W_full = frame_shape[:2]
    W_video = W_full - PANEL_W
    card = np.zeros((H, W_full, 3), dtype=np.uint8)
    card[:] = (8, 8, 14)

    font = cv2.FONT_HERSHEY_SIMPLEX
    cx = W_video // 2

    # ── Header ────────────────────────────────────────────────────────
    y = 55
    cv2.putText(card, "PBRunner", (cx - 100, y),
                font, 1.8, (0, 210, 255), 3, cv2.LINE_AA)
    cv2.putText(card, "Analiza Biomecanica" if LANG == "ro" else "Biomechanical Analysis",
                (cx - 130, y+36), font, 0.68, (140, 140, 160), 1, cv2.LINE_AA)
    if ATHLETE_NAME != "Atlet":
        cv2.putText(card, ATHLETE_NAME, (cx - 80, y+70),
                    font, 0.80, (0, 200, 255), 2, cv2.LINE_AA)
    cv2.line(card, (40, y+88), (W_video-40, y+88), (40, 40, 60), 1)

    # ── Scoruri per faza ──────────────────────────────────────────────
    y = 185
    title = "SCORURI PER FAZA" if LANG == "ro" else "PHASE SCORES"
    (tw, _), _ = cv2.getTextSize(title, font, 0.55, 1)
    cv2.putText(card, title, (cx - tw//2, y), font, 0.55,
                (160, 160, 180), 1, cv2.LINE_AA)
    y += 28

    phase_order = ["BLOCKSTART", "ACCELERATIE"]
    for ph in phase_order:
        if ph not in scores_by_phase:
            continue
        sc = scores_by_phase[ph]
        col = score_color_bgr(sc)
        ph_lbl = ph
        # bara
        bx, bw = cx - 140, 280
        cv2.rectangle(card, (bx, y), (bx+bw, y+22), (30, 30, 40), -1)
        fill = int(bw * sc / 100)
        cv2.rectangle(card, (bx, y), (bx+fill, y+22), col, -1)
        cv2.rectangle(card, (bx, y), (bx+bw, y+22), (60, 60, 80), 1)
        cv2.putText(card, ph_lbl, (bx - 115, y+16),
                    font, 0.42, (180, 180, 200), 1, cv2.LINE_AA)
        cv2.putText(card, f"{sc:.0f}/100", (bx+bw+8, y+16),
                    font, 0.45, col, 1, cv2.LINE_AA)
        y += 34

    # ── Top 3 recomandari ──────────────────────────────────────────────
    y += 14
    cv2.line(card, (40, y), (W_video-40, y), (40, 40, 60), 1)
    y += 22
    rec_title = "TOP RECOMANDARI" if LANG == "ro" else "TOP RECOMMENDATIONS"
    (tw, _), _ = cv2.getTextSize(rec_title, font, 0.50, 1)
    cv2.putText(card, rec_title, (cx - tw//2, y),
                font, 0.50, (160, 160, 180), 1, cv2.LINE_AA)
    y += 26
    for i, fb in enumerate(top_feedback[:3]):
        txt = fb.get("text", "")
        prio_col = {1: (30, 30, 220), 2: (0, 165, 255), 3: (0, 160, 0)}.get(
            fb.get("priority", 2), (140, 140, 140))
        bullet = f"{i+1}."
        cv2.putText(card, bullet, (cx-160, y+14), font,
                    0.44, prio_col, 1, cv2.LINE_AA)
        # Word wrap a ~45 chars
        words = txt.split()
        line = ""
        lines_out = []
        for w in words:
            if len(line)+len(w)+1 <= 52:
                line += ("" if not line else " ")+w
            else:
                lines_out.append(line)
                line = w
        if line:
            lines_out.append(line)
        for ln in lines_out[:2]:
            cv2.putText(card, ln, (cx-140, y+14), font, 0.40,
                        (210, 210, 220), 1, cv2.LINE_AA)
            y += 18
        y += 6

    # ── Momente critice ────────────────────────────────────────────────
    if events:
        y += 6
        cv2.line(card, (40, y), (W_video-40, y), (40, 40, 60), 1)
        y += 22
        ev_title = "MOMENTE CRITICE" if LANG == "ro" else "CRITICAL MOMENTS"
        (tw, _), _ = cv2.getTextSize(ev_title, font, 0.50, 1)
        cv2.putText(card, ev_title, (cx - tw//2, y),
                    font, 0.50, (160, 160, 180), 1, cv2.LINE_AA)
        y += 24
        for ev in events[:5]:
            lbl = ev["label_ro"] if LANG == "ro" else ev["label_en"]
            etxt = f"  {lbl}: {ev['time_s']:.2f}s"
            cv2.circle(card, (cx-155, y+6), 5, ev["col"], -1, cv2.LINE_AA)
            cv2.putText(card, etxt, (cx-145, y+12),
                        font, 0.40, (200, 200, 210), 1, cv2.LINE_AA)
            y += 20

    # ── Simetrie summary ──────────────────────────────────────────────
    if sym_summary:
        y += 6
        cv2.line(card, (40, y), (W_video-40, y), (40, 40, 60), 1)
        y += 20
        sym_title = "SIMETRIE L/R" if LANG == "ro" else "L/R SYMMETRY"
        cv2.putText(card, sym_title, (cx - 70, y),
                    font, 0.46, (160, 160, 180), 1, cv2.LINE_AA)
        y += 22
        labels_map = {"knee_diff": "Genunchi", "hip_diff": "Sold",
                      "ankle_diff": "Glezna", "elbow_diff": "Cot"}
        for k, lbl in labels_map.items():
            if k not in sym_summary:
                continue
            s = sym_summary[k]
            pct = s["pct_asymmetric"]
            col = (0, 210, 0) if pct < 20 else (
                (0, 165, 255) if pct < 40 else (30, 30, 220))
            stxt = f"  {lbl}: {s['mean']:.1f}gr diff  ({pct:.0f}% asimetric)"
            cv2.putText(card, stxt, (cx-155, y+12),
                        font, 0.38, col, 1, cv2.LINE_AA)
            y += 18

    # ── Footer ─────────────────────────────────────────────────────────
    y = H - 28
    footer = f"PBRunner | Sursa: IAAF Biomechanics Research Project, London 2017 | Durata analiza: {duration_s:.1f}s"
    (tw, _), _ = cv2.getTextSize(footer, font, 0.32, 1)
    cv2.putText(card, footer, (cx - tw//2, y),
                font, 0.32, (60, 60, 80), 1, cv2.LINE_AA)

    return card


# ─────────────────────────────────────────────────────────────────────────────
# MOTOR DE REGULI — genereaza feedback per frame
# ─────────────────────────────────────────────────────────────────────────────
def evaluate_frame(angles: dict, phase: str) -> List[dict]:
    """
    Compara unghiurile cu tintele IAAF personalizate (daca template-ul e disponibil)
    sau cu regulile de baza. Returneaza feedback sortat dupa prioritate.
    """
    # ── Prioritate 1: Motor IAAF personalizat ─────────────────────────────
    if IAAF_AVAILABLE and IAAF_COACH is not None:
        return IAAF_COACH.evaluate(angles, phase)

    # ── Fallback: Motor reguli de baza ────────────────────────────────────
    feedback = []
    tr = angles["trunk"]
    kl = angles["knee_L"]
    kr = angles["knee_R"]
    hl = angles["hip_L"]
    hr = angles["hip_R"]
    el = angles["elbow_L"]
    er = angles["elbow_R"]
    al = angles["ankle_L"]
    ar = angles["ankle_R"]
    head = angles["head"]

    def add(key):
        cue = COACHING_CUES.get(key)
        if cue:
            feedback.append({
                "key":      key,
                "text":     cue[LANG],
                "priority": cue["priority"],
                "phase":    cue["phase"],
                "arrow":    cue.get("arrow", "neutral"),
            })

    if phase == "BLOCKSTART":
        if tr > 45:
            add("bs_trunk_too_vertical")
        if tr < 5:
            add("bs_trunk_too_flat")
        if kl > 115:
            add("bs_knee_front_too_closed")
        if kl < 75:
            add("bs_knee_front_too_open")
        if hl > 70:
            add("bs_hip_too_high")
        if al > 90:
            add("bs_ankle_too_open")
        if el > 115:
            add("bs_elbow_too_open")

    elif phase == "ACCELERATIE":
        if tr > 70:
            add("acc_trunk_too_vertical")
        if kl < 80 or kr < 80:
            add("acc_knee_too_closed")
        if kl > 155 or kr > 155:
            add("acc_knee_recovery_low")
        if hl < 45 or hr < 45:
            add("acc_hip_too_closed")
        if el > 120 or er > 120:
            add("acc_elbow_too_open")
        if al > 100 or ar > 100:
            add("acc_ankle_passive")

    # Universal — orice faza
    if head > 50:
        add("head_forward")
    if abs(kl - kr) > 25:
        add("asymmetry_knees")
    if abs(el - er) > 25:
        add("asymmetry_arms")

    feedback.sort(key=lambda x: x["priority"])
    return feedback


# ─────────────────────────────────────────────────────────────────────────────
# DESENARE OVERLAY PE FRAME
# ─────────────────────────────────────────────────────────────────────────────
# ─── Culori skeleton ─────────────────────────────────────────────────────────
RED_BONE = (0,  50, 220)   # rosu  — scheletul real al atletului
RED_JT = (0,  80, 255)   # rosu deschis — articulatii


def draw_angle_arc(frame, center, p1, p2, color, r=26, t=2):
    cx, cy = int(center[0]), int(center[1])
    a1 = np.degrees(np.arctan2(-(p1-center)[1], (p1-center)[0]))
    a2 = np.degrees(np.arctan2(-(p2-center)[1], (p2-center)[0]))
    s, e = min(a1, a2), max(a1, a2)
    if e-s > 180:
        s, e = e, e+(360-(e-s))
    cv2.ellipse(frame, (cx, cy), (r, r), 0, -e, -s, color, t, cv2.LINE_AA)


# ─────────────────────────────────────────────────────────────────────────────
# JOINT INDICATORS — Arce colorate pe articulatii.
# Verde = unghi in interval optim IAAF.  Galben = aproape.  Rosu = departe.
# ─────────────────────────────────────────────────────────────────────────────
JOINT_GREEN = (0, 215,  60)
JOINT_YELLOW = (0, 200, 230)
JOINT_RED = (40,  40, 220)


def _joint_color(score: float):
    """Verde/galben/rosu pe baza scorului 0-100."""
    if score >= 80:
        return JOINT_GREEN
    if score >= 55:
        return JOINT_YELLOW
    return JOINT_RED


def _score_one_angle(angle_val: float, rng) -> float:
    """Scor 0-100 pentru un unghi vs intervalul (mn_o, mx_o, mn_a, mx_a)."""
    mn_o, mx_o, mn_a, mx_a = rng
    opt_center = (mn_o + mx_o) / 2
    opt_half = (mx_o - mn_o) / 2
    acc_half = (mx_a - mn_a) / 2
    dist = abs(angle_val - opt_center)
    if dist <= opt_half:
        return 100.0
    elif dist <= acc_half:
        frac = (dist - opt_half) / max(acc_half - opt_half, 1)
        return 99.0 - frac * 49.0
    else:
        excess = dist - acc_half
        return max(0.0, 50.0 - excess * 2.5)


def draw_joint_indicators(frame, lms, angles: dict, phase: str, W: int, H: int):
    """
    Codificarea culorii arata cat de aproape e atletul de norma IAAF
    pentru faza curenta.
      VERDE  → in intervalul optim
      GALBEN → in intervalul acceptabil
      ROSU   → in afara intervalului acceptabil

    Arcele se incarca instant pentru fiecare frame (fara calcule de
    geometrie 3D).
    """
    # Selecteaza intervalele IAAF pentru faza curenta
    ph_key = {"BLOCKSTART": "blockstart", "ACCELERATIE": "acceleratie",
              "SET": "blockstart"}.get(phase, "acceleratie")
    if IAAF_AVAILABLE and ATHLETE_PROFILE is not None:
        rng_map = ATHLETE_PROFILE.ranges.get(ph_key, {})
    else:
        rng_map = BIOMECH_RANGES.get(ph_key, {})

    def rng_for(*keys):
        for k in keys:
            if k in rng_map:
                return rng_map[k]
        return None

    # Coordonate landmark
    def lm_pt(idx):
        lm = lms[idx]
        return np.array([float(lm.x) * W, float(lm.y) * H])

    try:
        L_SH, R_SH = 11, 12
        L_HIP, R_HIP = 23, 24
        L_KN,  R_KN = 25, 26
        L_AN,  R_AN = 27, 28
        L_EL,  R_EL = 13, 14
        L_WR,  R_WR = 15, 16

        lsh, rsh = lm_pt(L_SH), lm_pt(R_SH)
        lhp, rhp = lm_pt(L_HIP), lm_pt(R_HIP)
        lkn, rkn = lm_pt(L_KN), lm_pt(R_KN)
        lan, ran = lm_pt(L_AN), lm_pt(R_AN)
        lel, rel = lm_pt(L_EL), lm_pt(R_EL)
        lwr, rwr = lm_pt(L_WR), lm_pt(R_WR)
        hip_c = (lhp + rhp) / 2
        sh_c = (lsh + rsh) / 2
    except Exception:
        return  # daca nu avem landmark-uri valide, sarim

    # ── Genunchi STG ─────────────────────────────────────────────────
    rng = rng_for("knee_L", "knee_front")
    if rng and angles.get("knee_L") is not None:
        sc = _score_one_angle(angles["knee_L"], rng)
        col = _joint_color(sc)
        draw_angle_arc(frame, lkn, lhp, lan, col, r=20, t=3)

    # ── Genunchi DRP ─────────────────────────────────────────────────
    rng = rng_for("knee_R", "knee_rear")
    if rng and angles.get("knee_R") is not None:
        sc = _score_one_angle(angles["knee_R"], rng)
        col = _joint_color(sc)
        draw_angle_arc(frame, rkn, rhp, ran, col, r=20, t=3)

    # ── Sold STG ─────────────────────────────────────────────────────
    rng = rng_for("hip_L", "hip")
    if rng and angles.get("hip_L") is not None:
        sc = _score_one_angle(angles["hip_L"], rng)
        col = _joint_color(sc)
        draw_angle_arc(frame, lhp, lsh, lkn, col, r=22, t=3)

    # ── Sold DRP ─────────────────────────────────────────────────────
    rng = rng_for("hip_R", "hip")
    if rng and angles.get("hip_R") is not None:
        sc = _score_one_angle(angles["hip_R"], rng)
        col = _joint_color(sc)
        draw_angle_arc(frame, rhp, rsh, rkn, col, r=22, t=3)

    # ── Trunchi (centrat la hip_c, intre verticala si sh_c) ─────────
    rng = rng_for("trunk")
    if rng and angles.get("trunk") is not None:
        sc = _score_one_angle(angles["trunk"], rng)
        col = _joint_color(sc)
        vert_ref = np.array([hip_c[0], hip_c[1] - 100.0]
                            )  # vertical pointing up
        draw_angle_arc(frame, hip_c, vert_ref, sh_c, col, r=30, t=3)

    # ── Cot STG ──────────────────────────────────────────────────────
    rng = rng_for("elbow_L", "elbow")
    if rng and angles.get("elbow_L") is not None:
        sc = _score_one_angle(angles["elbow_L"], rng)
        col = _joint_color(sc)
        draw_angle_arc(frame, lel, lsh, lwr, col, r=14, t=2)

    # ── Cot DRP ──────────────────────────────────────────────────────
    rng = rng_for("elbow_R", "elbow")
    if rng and angles.get("elbow_R") is not None:
        sc = _score_one_angle(angles["elbow_R"], rng)
        col = _joint_color(sc)
        draw_angle_arc(frame, rel, rsh, rwr, col, r=14, t=2)


def _bone(frame, a, b, col, t=2):
    cv2.line(frame, (int(a[0]), int(a[1])),
             (int(b[0]), int(b[1])), col, t, cv2.LINE_AA)


def dot(frame, p, r=4, col=C.JT_SM):
    cv2.circle(frame, (int(p[0]), int(p[1])), r, col, -1, cv2.LINE_AA)

# ─────────────────────────────────────────────────────────────────────────────
# SCHELET REAL — rosu
# ─────────────────────────────────────────────────────────────────────────────


def draw_skeleton(frame, lms, W, H, angles):
    def p(i): return lm_px(lms, i, W, H)
    nose = p(0)
    lsh = p(11)
    rsh = p(12)
    lel = p(13)
    rel = p(14)
    lwr = p(15)
    rwr = p(16)
    lhip = p(23)
    rhip = p(24)
    lkn = p(25)
    rkn = p(26)
    lan = p(27)
    ran = p(28)
    lhe = p(29)
    rhe = p(30)
    lft = p(31)
    rft = p(32)
    msh = (lsh+rsh)/2
    mhip = (lhip+rhip)/2

    # ── Oase in ROSU ──────────────────────────────────────────────────────
    _bone(frame, nose, msh,    RED_BONE, 2)
    _bone(frame, msh, mhip,    RED_BONE, 3)
    _bone(frame, lsh, rsh,     RED_BONE, 2)
    _bone(frame, lhip, rhip,   RED_BONE, 2)
    for s, e, w in [(lsh, lel, lwr), (rsh, rel, rwr)]:
        _bone(frame, s, e, RED_BONE, 2)
        _bone(frame, e, w, RED_BONE, 2)
    for h, k, a, he, f in [(lhip, lkn, lan, lhe, lft), (rhip, rkn, ran, rhe, rft)]:
        _bone(frame, h, k, RED_BONE, 2)
        _bone(frame, k, a, RED_BONE, 2)
        _bone(frame, a, he, RED_BONE, 2)
        _bone(frame, he, f, RED_BONE, 2)

    # ── Articulatii ───────────────────────────────────────────────────────
    for pt in [nose, lel, rel, lwr, rwr, lan, ran, lhe, rhe, lft, rft]:
        dot(frame, pt, 3, RED_JT)
    for pt in [lsh, rsh, lhip, rhip, lkn, rkn]:
        dot(frame, pt, 6, RED_JT)

    # ── Valori unghiuri text ──────────────────────────────────────────────

    def lbl(pos, val, key, ox=8, oy=0):
        rng = BIOMECH_RANGES.get("acceleratie", {}).get(key, None)
        col = quality_color(val, *rng) if rng else C.WARN
        txt = f"{val:.0f}"
        x, y = int(pos[0])+ox, int(pos[1])+oy
        (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        cv2.rectangle(frame, (x-2, y-th-2), (x+tw+2, y+2), (0, 0, 0), -1)
        cv2.putText(frame, txt, (x, y), cv2.FONT_HERSHEY_SIMPLEX,
                    0.45, col, 1, cv2.LINE_AA)

    lbl(lkn, angles["knee_L"], "knee_L", ox=8, oy=-12)
    lbl(rkn, angles["knee_R"], "knee_R", ox=8, oy=-12)
    lbl(lhip, angles["hip_L"], "hip_L", ox=-40, oy=-5)
    lbl(rhip, angles["hip_R"], "hip_R", ox=8, oy=-5)
    lbl(lel, angles["elbow_L"], "elbow_L", ox=-40, oy=0)
    lbl(rel, angles["elbow_R"], "elbow_R", ox=8, oy=0)


# ─────────────────────────────────────────────────────────────────────────────
# PANOU LATERAL — skeleton + coaching
# ─────────────────────────────────────────────────────────────────────────────
def priority_color(p):
    return {1: C.P1, 2: C.P2, 3: C.P3}.get(p, C.DIM)


def priority_label(p):
    if LANG == "ro":
        return {1: "CRITIC", 2: "IMPORTANT", 3: "OPTIMIZARE"}.get(p, "")
    return {1: "CRITICAL", 2: "IMPORTANT", 3: "OPTIMIZE"}.get(p, "")


def draw_panel(panel, angles, phase, feedback,
               frame_idx, src_fps, out_fps=0, slowmo_x=1.0):
    """
    src_fps  = fps-ul sursei (pentru timestamp real)
    out_fps  = fps-ul output (pentru durata videoclipului output)
    slowmo_x = factorul de slow motion (ex: 6.0 = 6x mai lent)
    """
    H = panel.shape[0]
    panel[:] = C.PANEL
    cv2.line(panel, (0, 0), (0, H), (40, 40, 55), 2)
    font = cv2.FONT_HERSHEY_SIMPLEX
    y = 0

    def hline(col=(40, 40, 55)):
        nonlocal y
        cv2.line(panel, (8, y), (PANEL_W-8, y), col, 1)
        y += 6

    def text(s, scale=0.50, col=C.WHITE, bold=False, indent=8):
        nonlocal y
        th_val = 2 if bold else 1
        y += 16
        cv2.putText(panel, s, (indent, y), font,
                    scale, col, th_val, cv2.LINE_AA)

    def section_title(s, col=C.WHITE):
        nonlocal y
        y += 20
        cv2.putText(panel, s, (8, y), font, 0.55, col, 1, cv2.LINE_AA)
        y += 4
        hline((50, 50, 65))

    # ── HEADER ───────────────────────────────────────────────────────────────
    y = 18
    cv2.putText(panel, "PBRunner", (8, y), font,
                0.80, (0, 210, 255), 2, cv2.LINE_AA)
    # Timestamp real (din sursa, nu din output slow)
    real_t = frame_idx / src_fps if src_fps > 0 else 0
    ts_txt = f"{real_t:.2f}s"
    cv2.putText(panel, ts_txt, (PANEL_W-58, y),
                font, 0.40, C.DIM, 1, cv2.LINE_AA)
    y += 6
    hline((0, 210, 255))

    # ── INDICATOR SLOW MOTION ─────────────────────────────────────────────────
    if slowmo_x > 1.01:
        sm_col = (0, 200, 255)   # portocaliu deschis
        sm_txt = f"SLOW {slowmo_x:.0f}x  ({src_fps:.0f}->{out_fps:.0f}fps)"
        (tw, th), _ = cv2.getTextSize(sm_txt, font, 0.42, 1)
        px = (PANEL_W - tw) // 2
        cv2.rectangle(panel, (px-4, y+2), (px+tw+4, y+th+8), (0, 40, 60), -1)
        cv2.rectangle(panel, (px-4, y+2), (px+tw+4, y+th+8), sm_col, 1)
        y += th+6
        cv2.putText(panel, sm_txt, (px, y), font, 0.42, sm_col, 1, cv2.LINE_AA)
        y += 6

    # ── FAZA ─────────────────────────────────────────────────────────────────
    ph_col = C.PHASE.get(phase, C.DIM)
    bg = tuple(max(0, x//6) for x in ph_col)
    ph_txt = f"  {phase}  "
    (tw, th), _ = cv2.getTextSize(ph_txt, font, 0.58, 2)
    cv2.rectangle(panel, (6, y+2), (6+tw+4, y+th+10), bg, -1)
    cv2.rectangle(panel, (6, y+2), (6+tw+4, y+th+10), ph_col, 1)
    y += th+6
    cv2.putText(panel, ph_txt, (8, y), font, 0.58, ph_col, 2, cv2.LINE_AA)
    y += 8

    y += 4
    hline()

    # ── METRICI CHEIE (compact) ───────────────────────────────────────────────
    section_title("METRICI" if LANG == "ro" else "METRICS")

    def metric_row(label, val, key):
        nonlocal y
        rng_phase = "acceleratie"
        rng = BIOMECH_RANGES.get(rng_phase, {}).get(key, None)
        col = quality_color(val, *rng) if rng else C.WARN
        # bara
        bx, by = 8, y+14
        bw = PANEL_W-16
        fill = int(np.clip(val/180, 0, 1)*bw)
        cv2.rectangle(panel, (bx, by), (bx+bw, by+4), (35, 35, 45), -1)
        cv2.rectangle(panel, (bx, by), (bx+fill, by+4), col, -1)
        y += 12
        cv2.putText(panel, label, (8, y), font, 0.40, C.DIM, 1, cv2.LINE_AA)
        cv2.putText(panel, f"{val:.0f}gr", (PANEL_W-52, y),
                    font, 0.42, col, 1, cv2.LINE_AA)
        y += 10

    metric_row("Trunchi" if LANG == "ro" else "Trunk",
               angles["trunk"],   "trunk_vs_vertical")
    metric_row("Genunchi STG" if LANG == "ro" else "Knee L",
               angles["knee_L"],  "knee_L")
    metric_row("Genunchi DRP" if LANG == "ro" else "Knee R",
               angles["knee_R"],  "knee_R")
    metric_row("Sold STG" if LANG == "ro" else "Hip L",
               angles["hip_L"],   "hip_L")
    metric_row("Sold DRP" if LANG == "ro" else "Hip R",
               angles["hip_R"],   "hip_R")
    metric_row("Cot STG" if LANG == "ro" else "Elbow L",
               angles["elbow_L"], "elbow_L")
    metric_row("Cot DRP" if LANG == "ro" else "Elbow R",
               angles["elbow_R"], "elbow_R")
    y += 4
    hline()

    # ── COACHING FEEDBACK ────────────────────────────────────────────────────
    section_title("COACHING")
    if not feedback:
        ok_txt = "Forma excelenta!" if LANG == "ro" else "Excellent form!"
        cv2.putText(panel, ok_txt, (8, y+14), font,
                    0.48, C.GOOD, 1, cv2.LINE_AA)
        y += 20
    else:
        shown = feedback[:3]   # maxim 3 pe frame
        for fb in shown:
            nonlocal_y_save = y
            p_col = priority_color(fb["priority"])
            p_lbl = priority_label(fb["priority"])
            # Badge prioritate
            (bw, bh), _ = cv2.getTextSize(p_lbl, font, 0.35, 1)
            y += 14
            cv2.rectangle(panel, (8, y-bh-2), (8+bw+6, y+2), p_col, -1)
            cv2.putText(panel, p_lbl, (10, y), font,
                        0.35, (0, 0, 0), 1, cv2.LINE_AA)
            y += 6
            # Text instructiune (word wrap manual)
            txt = fb["text"]
            words = txt.split()
            line = ""
            max_chars = 34
            for w in words:
                if len(line)+len(w)+1 <= max_chars:
                    line += ("" if not line else " ")+w
                else:
                    cv2.putText(panel, line, (10, y+12), font,
                                0.38, C.WHITE, 1, cv2.LINE_AA)
                    y += 14
                    line = w
            if line:
                cv2.putText(panel, line, (10, y+12), font,
                            0.38, C.WHITE, 1, cv2.LINE_AA)
                y += 14
            y += 4
            if y > H-60:
                break

    # ── LEGENDA CULORI ───────────────────────────────────────────────────────
    y = H-52
    hline()
    for col, lbl in [(C.GOOD, "Optim" if LANG == "ro" else "Optimal"),
                     (C.WARN, "Acceptabil" if LANG == "ro" else "Acceptable"),
                     (C.P1,  "Critic" if LANG == "ro" else "Critical")]:
        cv2.circle(panel, (14, y+4), 4, col, -1, cv2.LINE_AA)
        cv2.putText(panel, lbl, (22, y+8), font, 0.35, C.DIM, 1, cv2.LINE_AA)
        y += 16

# ─────────────────────────────────────────────────────────────────────────────
# RAPORT PDF
# ─────────────────────────────────────────────────────────────────────────────


def generate_report(df: pd.DataFrame, feedback_summary: dict,
                    ml_profile: dict, sym_df: pd.DataFrame,
                    scores_by_phase: dict, events_list: list,
                    output_path: str, video_name: str):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                        Table, TableStyle, HRFlowable, Image as RLImage)
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        import io
        from PIL import Image as PILImage

        # ── Genereaza matplotlib charts în memorie (PNG bytes) ──────────────────
        # Asta evită salvarea pe disk — charts merge direct în PDF
        import tempfile

        temp_chart_path = None
        temp_sym_path = None

        # Chart 1: Analiza unghiuri
        try:
            temp_fd, temp_chart_path = tempfile.mkstemp(suffix=".png")
            os.close(temp_fd)
            generate_chart_internal(df, temp_chart_path, video_name)
        except:
            temp_chart_path = None

        # Chart 2: Analiza simetrie
        if not sym_df.empty:
            try:
                temp_fd, temp_sym_path = tempfile.mkstemp(suffix=".png")
                os.close(temp_fd)
                generate_symmetry_chart(sym_df, temp_sym_path, video_name)
            except:
                temp_sym_path = None

        doc = SimpleDocTemplate(output_path, pagesize=A4,
                                leftMargin=2*cm, rightMargin=2*cm,
                                topMargin=2*cm, bottomMargin=2*cm)
        styles = getSampleStyleSheet()
        story = []

        dark_blue = colors.HexColor("#0D1B2A")
        accent = colors.HexColor("#00D4FF")
        good_col = colors.HexColor("#00D200")
        warn_col = colors.HexColor("#FFA500")
        bad_col = colors.HexColor("#DD2222")
        dim_col = colors.HexColor("#888888")

        h1 = ParagraphStyle("h1", parent=styles["Heading1"],
                            fontSize=22, textColor=dark_blue, spaceAfter=4)
        h2 = ParagraphStyle("h2", parent=styles["Heading2"],
                            fontSize=13, textColor=accent,    spaceAfter=6)
        h3 = ParagraphStyle("h3", parent=styles["Heading3"],
                            fontSize=10, textColor=dark_blue, spaceAfter=4)
        body = ParagraphStyle("body", parent=styles["Normal"],
                              fontSize=9, leading=14, textColor=dark_blue)
        small = ParagraphStyle("small", parent=styles["Normal"],
                               fontSize=8, leading=12, textColor=dim_col)

        title_ro = "Raport Biomecanic — PBRunner"
        title_en = "Biomechanical Report — PBRunner"
        story.append(Paragraph(title_ro if LANG == "ro" else title_en, h1))
        story.append(Paragraph(f"Fisier: {video_name}", small))
        story.append(Spacer(1, 0.3*cm))
        story.append(HRFlowable(width="100%", color=accent))
        story.append(Spacer(1, 0.3*cm))

        # Sumar sesiune
        hdr = "Sumar sesiune" if LANG == "ro" else "Session Summary"
        story.append(Paragraph(hdr, h2))
        n_frames = len(df)
        dur = df["time_s"].max() if "time_s" in df.columns else 0
        phases = df["phase"].value_counts(
        ).to_dict() if "phase" in df.columns else {}

        sum_data = [
            ["Frame-uri procesate" if LANG ==
                "ro" else "Processed frames", str(n_frames)],
            ["Durata" if LANG == "ro" else "Duration",          f"{dur:.2f}s"],
        ]
        for ph, cnt in phases.items():
            pct = cnt/max(n_frames, 1)*100
            sum_data.append([f"Faza {ph}" if LANG == "ro" else f"Phase {ph}",
                             f"{cnt} frames ({pct:.0f}%)"])

        t = Table(sum_data, colWidths=[9*cm, 7*cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8F4FD")),
            ("FONTSIZE",   (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1),
             [colors.white, colors.HexColor("#F7FBFF")]),
            ("BOX",        (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
            ("INNERGRID",  (0, 0), (-1, -1), 0.3, colors.HexColor("#DDDDDD")),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.4*cm))

        # Statistici unghiuri
        hdr2 = "Statistici unghiuri (grade)" if LANG == "ro" else "Angle statistics (degrees)"
        story.append(Paragraph(hdr2, h2))
        angle_keys = ["knee_L", "knee_R", "hip_L", "hip_R", "ankle_L", "ankle_R",
                      "elbow_L", "elbow_R", "trunk", "head"]
        angle_labels = {
            "knee_L": "Genunchi STG", "knee_R": "Genunchi DRP",
            "hip_L": "Sold STG", "hip_R": "Sold DRP",
            "ankle_L": "Glezna STG", "ankle_R": "Glezna DRP",
            "elbow_L": "Cot STG", "elbow_R": "Cot DRP",
            "trunk": "Trunchi", "head": "Cap",
        } if LANG == "ro" else {
            "knee_L": "Knee L", "knee_R": "Knee R",
            "hip_L": "Hip L", "hip_R": "Hip R",
            "ankle_L": "Ankle L", "ankle_R": "Ankle R",
            "elbow_L": "Elbow L", "elbow_R": "Elbow R",
            "trunk": "Trunk", "head": "Head",
        }
        stat_rows = [["Articulatie" if LANG == "ro" else "Joint",
                      "Min", "Med", "Max", "Std"]]
        for k in angle_keys:
            if k in df.columns:
                stat_rows.append([
                    angle_labels.get(k, k),
                    f"{df[k].min():.1f}", f"{df[k].mean():.1f}",
                    f"{df[k].max():.1f}", f"{df[k].std():.1f}",
                ])
        st = Table(stat_rows, colWidths=[5*cm, 3*cm, 3*cm, 3*cm, 3*cm])
        st.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, 0), dark_blue),
            ("TEXTCOLOR",    (0, 0), (-1, 0), colors.white),
            ("FONTSIZE",     (0, 0), (-1, -1), 8.5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#F7FBFF")]),
            ("BOX",          (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
            ("INNERGRID",    (0, 0), (-1, -1), 0.3, colors.HexColor("#DDDDDD")),
            ("LEFTPADDING",  (0, 0), (-1, -1), 6),
        ]))
        story.append(st)
        story.append(Spacer(1, 0.4*cm))

        # Recomandari coaching
        hdr3 = "Recomandari coaching prioritizate" if LANG == "ro" else "Prioritized coaching recommendations"
        story.append(Paragraph(hdr3, h2))

        for phase_name, cues in feedback_summary.items():
            if not cues:
                continue
            story.append(Paragraph(f"Faza: {phase_name}" if LANG == "ro"
                                   else f"Phase: {phase_name}", h3))
            for i, (key, count, pct, fb) in enumerate(cues[:6]):
                p_txt = priority_label(fb["priority"])
                p_col_hex = {1: "#DD2222", 2: "#FFA500",
                             3: "#008800"}.get(fb["priority"], "#555")
                badge = f'<font color="{p_col_hex}"><b>[{p_txt}]</b></font>'
                freq = f'({pct:.0f}% frames)' if LANG == "ro" else f'({pct:.0f}% of frames)'
                line = f"{badge} {fb.get(LANG, fb.get('ro', ''))} <font color='#888888'><i>{freq}</i></font>"
                story.append(Paragraph(line, body))
                story.append(Spacer(1, 0.15*cm))
            story.append(Spacer(1, 0.2*cm))

        # ── Comparatie cu elita IAAF ─────────────────────────────────────────
        if IAAF_AVAILABLE and ATHLETE_PROFILE is not None:
            story.append(HRFlowable(width="100%", color=accent))
            hdr_iaaf = "Comparatie cu elita IAAF — Londra 2017" if LANG == "ro" \
                       else "Comparison with IAAF Elite — London 2017"
            story.append(Paragraph(hdr_iaaf, h2))

            prof_sum = ATHLETE_PROFILE.summary()
            story.append(Paragraph(
                (f"Profil atlet: {prof_sum['height_cm']}cm / {prof_sum['weight_kg']}kg / {prof_sum['age']} ani  |  "
                 f"BMI: {prof_sum['bmi']}  |  Referinta: {', '.join(prof_sum['similar_elites'])}")
                if LANG == "ro" else
                (f"Athlete profile: {prof_sum['height_cm']}cm / {prof_sum['weight_kg']}kg / {prof_sum['age']} yrs  |  "
                 f"BMI: {prof_sum['bmi']}  |  Reference: {', '.join(prof_sum['similar_elites'])}"),
                body))
            story.append(Spacer(1, 0.3*cm))

            # Tabel tinte cinematice
            t_hdr = ["Parametru" if LANG == "ro" else "Parameter",
                     "Tinta IAAF" if LANG == "ro" else "IAAF Target",
                     "Gatlin (1st)", "Coleman (2nd)", "Bolt (3rd)"]
            from pbrunner_template import IAAF_KINEMATICS
            t_rows = [
                ["Lungime pas (m)" if LANG == "ro" else "Step length (m)",
                 f"{prof_sum['targets']['step_length_m']:.2f}",
                 f"{IAAF_KINEMATICS['GATLIN']['step_length_m']:.2f}",
                 f"{IAAF_KINEMATICS['COLEMAN']['step_length_m']:.2f}",
                 f"{IAAF_KINEMATICS['BOLT']['step_length_m']:.2f}"],
                ["Frecventa (Hz)" if LANG == "ro" else "Step rate (Hz)",
                 f"{prof_sum['targets']['step_rate_hz']:.2f}",
                 f"{IAAF_KINEMATICS['GATLIN']['step_rate_hz']:.2f}",
                 f"{IAAF_KINEMATICS['COLEMAN']['step_rate_hz']:.2f}",
                 f"{IAAF_KINEMATICS['BOLT']['step_rate_hz']:.2f}"],
                ["Viteza tinta (m/s)" if LANG == "ro" else "Target speed (m/s)",
                 f"{prof_sum['targets']['target_speed_ms']:.2f}",
                 f"{IAAF_KINEMATICS['GATLIN']['mean_speed_ms']:.2f}",
                 f"{IAAF_KINEMATICS['COLEMAN']['mean_speed_ms']:.2f}",
                 f"{IAAF_KINEMATICS['BOLT']['mean_speed_ms']:.2f}"],
            ]
            iaaf_tbl = Table(
                [t_hdr]+t_rows, colWidths=[5*cm, 3*cm, 3*cm, 3*cm, 3*cm])
            iaaf_tbl.setStyle(TableStyle([
                ("BACKGROUND",  (0, 0), (-1, 0), dark_blue),
                ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
                ("FONTSIZE",    (0, 0), (-1, -1), 8.5),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                 [colors.white, colors.HexColor("#F7FBFF")]),
                ("BOX",         (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
                ("INNERGRID",   (0, 0), (-1, -1), 0.3, colors.HexColor("#DDDDDD")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("BACKGROUND",  (1, 1), (1, -1), colors.HexColor("#E8F8F0")),
            ]))
            story.append(iaaf_tbl)
            story.append(Spacer(1, 0.3*cm))

        # Profil ML
        story.append(HRFlowable(width="100%", color=accent))
        hdr4 = "Profil ML atlet" if LANG == "ro" else "Athlete ML Profile"
        story.append(Paragraph(hdr4, h2))
        if ml_profile.get("is_fitted"):
            for c_id, c_data in ml_profile.get("clusters", {}).items():
                cline = (f"Cluster {c_id}: {c_data['label']} — "
                         f"{c_data['pct']}% din sesiune")
                story.append(Paragraph(cline, body))
            note = ml_profile.get("note_ro" if LANG == "ro" else "note_en", "")
            story.append(Spacer(1, 0.2*cm))
            story.append(Paragraph(note, small))
        else:
            story.append(Paragraph(
                "Date insuficiente pentru clustering ML in aceasta sesiune." if LANG == "ro"
                else "Insufficient data for ML clustering in this session.", small))

        # ── Adauga imagini matplotlib în PDF ──────────────────────────────────
        story.append(HRFlowable(width="100%", color=accent))
        chart_title = "Analiza Unghiuri Articulare" if LANG == "ro" else "Joint Angle Analysis"
        story.append(Paragraph(chart_title, h2))
        if temp_chart_path and os.path.exists(temp_chart_path):
            try:
                img = RLImage(temp_chart_path, width=19*cm, height=13*cm)
                story.append(img)
                story.append(Spacer(1, 0.3*cm))
            except:
                pass

        if not sym_df.empty:
            story.append(HRFlowable(width="100%", color=accent))
            sym_title = "Analiza Simetrie L/R" if LANG == "ro" else "L/R Symmetry Analysis"
            story.append(Paragraph(sym_title, h2))
            if temp_sym_path and os.path.exists(temp_sym_path):
                try:
                    img = RLImage(temp_sym_path, width=19*cm, height=13*cm)
                    story.append(img)
                    story.append(Spacer(1, 0.3*cm))
                except:
                    pass

        doc.build(story)
        print(f"  PDF: {output_path}")

        # ── Cleanup fișiere temporare ───────────────────────────────────────────
        if temp_chart_path and os.path.exists(temp_chart_path):
            try:
                os.remove(temp_chart_path)
            except:
                pass
        if temp_sym_path and os.path.exists(temp_sym_path):
            try:
                os.remove(temp_sym_path)
            except:
                pass

    except ImportError:
        print("  [WARN] reportlab nu e instalat — PDF sarit. "
              "Instaleaza cu: pip install reportlab")
        # Fallback: raport text
        txt_path = output_path.replace(".pdf", ".txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(f"PBRunner — Raport Biomecanic\n{'='*50}\n")
            f.write(f"Video: {video_name}\n")
            f.write(f"Frames: {len(df)}\n\n")
            f.write("RECOMANDARI:\n")
            for phase_name, cues in feedback_summary.items():
                f.write(f"\n{phase_name}:\n")
                for key, count, pct, fb in cues[:5]:
                    f.write(
                        f"  [{priority_label(fb['priority'])}] {fb.get(LANG, fb.get('ro', ''))} ({pct:.0f}%)\n")
        print(f"  TXT: {txt_path}")

# ─────────────────────────────────────────────────────────────────────────────
# GRAFIC RAPORT
# ─────────────────────────────────────────────────────────────────────────────


def generate_chart_internal(df: pd.DataFrame, output_path: str, video_name: str):
    phase_mpl = {"BLOCKSTART": "#FF8C00", "ACCELERATIE": "#00D4FF", }

    fig = plt.figure(figsize=(20, 14), facecolor="#0D0D14")
    fig.suptitle(f"PBRunner — Analiza Biomecanica\n{video_name}",
                 color="white", fontsize=15, fontweight="bold", y=0.98)
    gs = GridSpec(3, 3, figure=fig, hspace=0.55, wspace=0.35,
                  left=0.06, right=0.97, top=0.92, bottom=0.07)

    def styled(ax):
        ax.set_facecolor("#12121E")
        for sp in ax.spines.values():
            sp.set_color("#2a2a3a")
        ax.tick_params(colors="#888", labelsize=8)
        ax.yaxis.label.set_color("#aaa")
        ax.xaxis.label.set_color("#aaa")
        ax.title.set_color("#ddd")
        ax.grid(True, color="#1e1e2e", linewidth=0.7, linestyle="--")

    def shade(ax):
        if "phase" not in df.columns:
            return
        prev_ph = None
        prev_t = df["time_s"].iloc[0]
        for _, row in df.iterrows():
            ph = row["phase"]
            if ph != prev_ph:
                if prev_ph:
                    ax.axvspan(prev_t, row["time_s"], alpha=0.09,
                               color=phase_mpl.get(prev_ph, "#888"))
                prev_ph = ph
                prev_t = row["time_s"]
        if prev_ph:
            ax.axvspan(prev_t, df["time_s"].iloc[-1], alpha=0.09,
                       color=phase_mpl.get(prev_ph, "#888"))

    t = df["time_s"].values
    panels = [
        (gs[0, 0], [("knee_L", "#00D4FF", "Genunchi STG"),
         ("knee_R", "#FF8C00", "Genunchi DRP")], "Genunchi (gr)"),
        (gs[0, 1], [("hip_L", "#00D4FF", "Sold STG"),
         ("hip_R", "#FF8C00", "Sold DRP")], "Sold (gr)"),
        (gs[0, 2], [("ankle_L", "#00D4FF", "Glezna STG"),
         ("ankle_R", "#FF8C00", "Glezna DRP")], "Glezna (gr)"),
        (gs[1, 0], [("elbow_L", "#00D4FF", "Cot STG"),
         ("elbow_R", "#FF8C00", "Cot DRP")], "Cot (gr)"),
        (gs[1, 1], [("shoulder_L", "#00D4FF", "Umar STG"),
         ("shoulder_R", "#FF8C00", "Umar DRP")], "Umar (gr)"),
        (gs[1, 2], [("trunk", "#FFFFFF", "Trunchi")], "Trunchi vs Vertical (gr)"),
        (gs[2, 0], [("foot_L", "#00D4FF", "Talpa STG"),
         ("foot_R", "#FF8C00", "Talpa DRP")], "Talpa (gr)"),
        (gs[2, 1], [("head", "#DDA0FF", "Cap")], "Cap vs Vertical (gr)"),
    ]
    for spec, series, ttl in panels:
        ax = fig.add_subplot(spec)
        styled(ax)
        shade(ax)
        for ck, col, lbl in series:
            if ck in df.columns:
                sm = df[ck].rolling(5, center=True, min_periods=1).mean()
                ax.plot(t, df[ck].values, color=col, alpha=0.18, linewidth=0.7)
                ax.plot(t, sm.values, color=col, alpha=0.92,
                        linewidth=1.6, label=lbl)
        ax.set_title(ttl, fontsize=9, pad=4)
        ax.set_xlabel("timp (s)", fontsize=7)
        ax.legend(fontsize=7, facecolor="#1a1a28", edgecolor="#333",
                  labelcolor="white", loc="upper right")

    # Panel statistici
    ax_s = fig.add_subplot(gs[2, 2])
    styled(ax_s)
    ax_s.axis("off")
    ax_s.set_title("Statistici", fontsize=9, pad=4)
    keys = ["knee_L", "knee_R", "hip_L",
            "hip_R", "trunk", "elbow_L", "elbow_R"]
    lbls = ["Gen STG", "Gen DRP", "Sold STG",
            "Sold DRP", "Trunchi", "Cot STG", "Cot DRP"]
    rows = [["Metric", "Min", "Med", "Max"]]
    for k, l in zip(keys, lbls):
        if k in df.columns:
            rows.append([l, f"{df[k].min():.0f}",
                        f"{df[k].mean():.0f}", f"{df[k].max():.0f}"])
    tb = ax_s.table(cellText=rows[1:], colLabels=rows[0],
                    cellLoc="center", loc="center", bbox=[0, 0, 1, 1])
    tb.auto_set_font_size(False)
    tb.set_fontsize(8)
    for (r, c), cell in tb.get_celld().items():
        cell.set_facecolor("#0D0D14" if r % 2 == 0 else "#16162a")
        cell.set_edgecolor("#2a2a3a")
        cell.set_text_props(color="white" if r > 0 else "#00D4FF")

    patches = [mpatches.Patch(color=v, label=k, alpha=0.7)
               for k, v in phase_mpl.items() if k != "ANALIZA..."]
    fig.legend(handles=patches, loc="lower center", ncol=3,
               facecolor="#12121E", edgecolor="#333", labelcolor="white",
               fontsize=9, bbox_to_anchor=(0.5, 0.01))

    plt.savefig(output_path, dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close()
    print(f"  Grafic: {output_path}")

# ─────────────────────────────────────────────────────────────────────────────
# ML ADAPTIVE PHASE DETECTION — K-Means Clustering
# ─────────────────────────────────────────────────────────────────────────────
# Algoritm de invatare nesupervizata (unsupervised learning) care descopera
# automat fazele biomecanice din videoclipul atletului, FARA reguli hardcodate.
#
# Functioneaza in 2 etape:
#
# ETAPA 1 — Colectare features:
#   Pentru fiecare frame, extragem un vector de 8 caracteristici biomecanice
#   (unghi trunchi, unghiuri genunchi, viteza sold, etc.). Asta produce o
#   matrice N×8 cu toate datele atletului.
#
# ETAPA 2 — K-Means descopera tiparele:
#   sklearn.cluster.KMeans imparte automat datele in 3-4 grupuri naturale
#   (clustere) FARA sa-i spunem ce inseamna fiecare. Algoritmul gaseste
#   singur centrele dominante ale miscarii. Apoi atribuim nume fazelor pe
#   baza unghiurilor medii din fiecare cluster:
#     - Cluster cu trunchi cel mai aplecat → SET sau BLOCKSTART
#     - Restul → ACCELERATIE
#
# DE CE E ML REAL:
#   K-Means este unul din primii algoritmi de unsupervised learning predati
#   in orice curs de Machine Learning. Folosim implementarea oficiala din
#   scikit-learn (sklearn.cluster.KMeans). Algoritmul invata din datele
#   ATLETULUI ACESTUIA — pentru fiecare video, descopera tipare diferite,
#   adaptandu-se la corpul si stilul lui de alergare.
# ─────────────────────────────────────────────────────────────────────────────


PHASE_PROGRESSION_ORDER = {
    "SET": 0, "BLOCKSTART": 1, "ACCELERATIE": 2, }


def extract_phase_features(angles: dict, seg: dict, hip_velocity: float,
                           frame_idx: int, total_frames: int, H: int) -> np.ndarray:
    """
    Extrage vectorul de 8 features biomecanice pentru K-Means.

    Features alese sa surprinda complet starea biomecanica:
      [0] trunk_angle      — pozitia trunchiului (cel mai distinctiv per faza)
      [1] knee_avg         — flexie medie genunchi
      [2] knee_asymmetry   — diferenta L/R (mare la sprint, mic la set)
      [3] hip_avg          — extensie sold mediu
      [4] hip_velocity     — viteza orizontala (set=0, sprint=mare)
      [5] hip_y_norm       — pozitie verticala sold (set=mare, sprint=mediu)
      [6] frame_progress   — context temporal (0=inceput, 1=sfarsit)
      [7] elbow_avg        — activitate brate (set=intinse, sprint=ciclate)
    """
    trunk = float(angles.get("trunk", 45.0))
    knee_L = float(angles.get("knee_L", 130.0))
    knee_R = float(angles.get("knee_R", 130.0))
    hip_L = float(angles.get("hip_L", 90.0))
    hip_R = float(angles.get("hip_R", 90.0))
    elbow_L = float(angles.get("elbow_L", 90.0))
    elbow_R = float(angles.get("elbow_R", 90.0))

    knee_avg = (knee_L + knee_R) / 2.0
    knee_asym = abs(knee_L - knee_R)
    hip_avg = (hip_L + hip_R) / 2.0
    elbow_avg = (elbow_L + elbow_R) / 2.0
    hip_y_norm = float(seg["hip_c"][1]) / max(H, 1)
    progress = frame_idx / max(total_frames, 1)

    return np.array([
        trunk, knee_avg, knee_asym, hip_avg,
        float(hip_velocity), hip_y_norm, progress, elbow_avg
    ], dtype=np.float32)


def adaptive_phase_detection_ml(features_list: list, src_fps: float) -> tuple:
    """
    APLICA K-MEANS pentru a descoperi fazele biomecanice ALE ATLETULUI.

    K-Means este un algoritm de unsupervised learning din scikit-learn.
    El descopera SINGUR grupurile naturale din date, fara sa-i spunem
    ce e o "faza" — invata din videoul concret.

    Input:
        features_list — lista de vectori de features (sau None unde lipseste detectia)
        src_fps       — fps-ul sursei (pentru filtre temporale)

    Returns:
        ml_phases     — lista de label-uri faza per frame
        info          — dict cu detalii clustering (centroids, mapping, k)
    """
    # Pastram doar feature-urile valide pentru clustering
    valid_indices = [i for i, f in enumerate(features_list) if f is not None]
    valid_features = [features_list[i] for i in valid_indices]
    n_valid = len(valid_features)
    n_total = len(features_list)

    info = {"used_ml": False, "n_valid_frames": n_valid,
            "n_total_frames": n_total}

    # Fallback daca prea putine date pentru ML
    if n_valid < 12:
        return ["ACCELERATIE"] * n_total, info

    X = np.array(valid_features, dtype=np.float64)

    # ── Pas 1: Standardizare (K-Means e sensibil la scala features) ──────
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # ── Pas 2: Alegere K (numar de clustere) bazat pe varietatea datelor ─
    trunk_range = X[:, 0].max() - X[:, 0].min()
    velocity_max = X[:, 4].max()

    k = 3

    # ── Pas 3: K-Means descopera clusterele SINGUR ───────────────────────
    # n_init=10 ruleaza algoritmul de 10 ori cu seed-uri diferite si
    # alege rezultatul cu cea mai mica inertie (cea mai buna grupare).
    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10, max_iter=300)
    cluster_labels_valid = kmeans.fit_predict(X_scaled)

    # Centroizii in spatiul original (denormalizati pentru interpretare)
    centroids = scaler.inverse_transform(kmeans.cluster_centers_)
    # Coloane: trunk, knee_avg, knee_asym, hip_avg, hip_vel, hip_y, progress, elbow_avg

    # ── Pas 4: Sortare clustere dupa unghi trunchi ───────────────────────
    # Cel mai aplecat = primul (potential SET/BLOCKSTART)
    sorted_clusters = sorted(range(k), key=lambda c: -centroids[c, 0])

    # ── Pas 5: Atribuire faze pe baza analizei biomecanice a centroizilor
    # Logica foloseste: unghi trunchi + progres temporal + viteza orizontala.
    # Nu mai depinde strict de ranking-ul trunchi → mai robust pe variatii.
    cluster_to_phase = {}
    for rank, cid in enumerate(sorted_clusters):
        trunk_c = centroids[cid, 0]
        vel_c = centroids[cid, 4]
        progress_c = centroids[cid, 6]
        knee_asym_c = centroids[cid, 2]

        if trunk_c > 55 and vel_c < 3.0:
            # Trunchi aproape orizontal + viteza mica → SET
            cluster_to_phase[cid] = "SET"
        elif trunk_c > 40 and progress_c < 0.30:
            # Trunchi puternic aplecat (>40°) in primii 30% din video → drive
            # phase din blocuri (BLOCKSTART). Restrictiv: doar primele frame-uri
            # cu trunchi cu adevarat inclinat.
            cluster_to_phase[cid] = "BLOCKSTART"
        else:
            cluster_to_phase[cid] = "ACCELERATIE"

    # ── Pas 6: Mapare label per frame (incl. cele fara detectie) ─────────
    ml_phases = []
    last_known = "ACCELERATIE"
    j = 0
    for i in range(n_total):
        if features_list[i] is None:
            ml_phases.append(last_known)
        else:
            phase = cluster_to_phase[cluster_labels_valid[j]]
            ml_phases.append(phase)
            last_known = phase
            j += 1

    # ── Pas 7: Smoothing temporal (consistenta fazei) ────────────────────
    ml_phases = median_filter_phases(ml_phases, window=5)
    ml_phases = enforce_monotonic_progression(ml_phases)

    info.update({
        "used_ml":          True,
        "k":                k,
        "centroids":        centroids.tolist(),
        "cluster_to_phase": {int(k): v for k, v in cluster_to_phase.items()},
        "sorted_clusters":  [int(c) for c in sorted_clusters],
        "inertia":          float(kmeans.inertia_),
        "trunk_range":      float(trunk_range),
        "velocity_max":     float(velocity_max),
    })

    return ml_phases, info


def median_filter_phases(phases: list, window: int = 5) -> list:
    """Filtru median pe lista de faze — elimina flicker-ul intre frame-uri."""
    n = len(phases)
    if n < window:
        return list(phases)
    result = list(phases)
    half = window // 2
    for i in range(half, n - half):
        window_phases = phases[i - half:i + half + 1]
        # Vot majoritar
        most_common = max(set(window_phases), key=window_phases.count)
        result[i] = most_common
    return result


def enforce_monotonic_progression(phases: list) -> list:
    """
    Sprintul are o ordine biomecanica naturala — odata trecut la ACCELERATIE,
    nu se mai poate intoarce la SET. Aplica aceasta regula.
    """
    if not phases:
        return phases
    result = list(phases)
    inverse = {v: k for k, v in PHASE_PROGRESSION_ORDER.items()}
    current_max = PHASE_PROGRESSION_ORDER.get(result[0], 0)
    for i in range(len(result)):
        order = PHASE_PROGRESSION_ORDER.get(result[i], 0)
        if order < current_max:
            result[i] = inverse[current_max]
        else:
            current_max = order
    return result


def print_ml_clustering_report(info: dict, lang: str = "ro"):
    """Afiseaza in consola rezultatele K-Means pentru transparenta."""
    if not info.get("used_ml"):
        print("  [ML] Date insuficiente pentru K-Means — fallback la reguli.")
        return
    print(f"  [ML] K-Means a descoperit {info['k']} clustere "
          f"(inertie: {info['inertia']:.1f})")
    print(
        f"  [ML] Frame-uri analizate: {info['n_valid_frames']}/{info['n_total_frames']}")
    print(f"  [ML] Varietate trunchi: {info['trunk_range']:.1f}°  "
          f"viteza max: {info['velocity_max']:.2f} px/frame")
    centroids = np.array(info["centroids"])
    cluster_to_phase = info["cluster_to_phase"]
    print(f"  [ML] Mapare cluster → faza:")
    for cid in info["sorted_clusters"]:
        phase = cluster_to_phase[cid]
        c = centroids[cid]
        print(f"        Cluster {cid} → {phase:12}  "
              f"trunk={c[0]:5.1f}°  knee={c[1]:5.1f}°  vel={c[4]:5.2f}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def process_video(video_path: str, lang: str,
                  height_cm: float = 184,
                  weight_kg: float = 82,
                  age: int = 21,
                  slowmo_fps: float = 0.0,
                  athlete_name: str = "Atlet"):
    """
    slowmo_fps: daca > 0, videoul output va fi scris la aceasta viteza
    (ex: sursa 60fps + slowmo_fps=10 => slow motion 6x).
    Toate frame-urile sunt procesate, MediaPipe primeste timestamp-ul
    real din sursa pentru acuratete; output-ul merge la slowmo_fps.
    """
    global LANG, ATHLETE_PROFILE, IAAF_COACH, ATHLETE_NAME
    LANG = lang.lower()
    ATHLETE_NAME = athlete_name

    # ── Initializeaza profilul IAAF personalizat ──────────────────────────
    if IAAF_AVAILABLE:
        ATHLETE_PROFILE = AthleteProfile(
            height_cm=height_cm,
            weight_kg=weight_kg,
            age=age,
            name="Atlet PBRunner",
        )
        IAAF_COACH = IAAFCoachEngine(ATHLETE_PROFILE, lang=LANG)
        prof_sum = ATHLETE_PROFILE.summary()
        print(
            f"[IAAF] Template activ: {height_cm}cm / {weight_kg}kg / {age} ani")
        print(
            f"[IAAF] Atleti referinta: {', '.join(prof_sum['similar_elites'])}")
        print(f"[IAAF] Tinta pas: {prof_sum['targets']['step_length_m']:.2f}m "
              f"@ {prof_sum['targets']['step_rate_hz']:.2f}Hz "
              f"= {prof_sum['targets']['target_speed_ms']:.2f}m/s")
    else:
        print("[INFO] Rulare fara template IAAF")

    if not os.path.exists(video_path):
        print(f"[EROARE] Video negasit: {video_path}")
        sys.exit(1)
    if not os.path.exists(MODEL_PATH):
        print(f"[EROARE] Model MediaPipe lipsa: {MODEL_PATH}\n"
              "Descarca de la: https://storage.googleapis.com/mediapipe-models/"
              "pose_landmarker/pose_landmarker_heavy/float16/latest/"
              "pose_landmarker_heavy.task")
        sys.exit(1)

    # Output files — DOAR 3:
    # 1. video_coached.mp4 — video cu overlay
    # 2. data.csv — date brute per frame
    # 3. report.pdf — RAPORT COMPLET (charts, symmetry, coaching, IAAF, ML)
    base = os.path.splitext(video_path)[0]
    out_video = base + "_coached.mp4"
    out_csv = base + "_coach_data.csv"
    out_pdf = base + "_coach_report.pdf"

    cap = cv2.VideoCapture(video_path)
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # ── Slow motion ──────────────────────────────────────────────────────
    # fps = viteza la care MediaPipe timestampeaza frame-urile (sursa reala)
    # out_fps = viteza output (mai mica => slow motion)
    fps = src_fps
    out_fps = slowmo_fps if slowmo_fps > 0 else src_fps
    slowmo_x = src_fps / out_fps if out_fps > 0 else 1.0

    if slowmo_fps > 0:
        print(f"[INFO] {W}x{H} @ {src_fps:.1f}fps sursa  |  "
              f"output {out_fps:.1f}fps  |  SLOW MOTION {slowmo_x:.1f}x  |  "
              f"{total} frames  |  lang={LANG.upper()}")
        print(f"[INFO] Durata video sursa  : {total/src_fps:.1f}s")
        print(f"[INFO] Durata video output : {total/out_fps:.1f}s  "
              f"(+{total/out_fps - total/src_fps:.1f}s)")
    else:
        print(
            f"[INFO] {W}x{H} @ {src_fps:.1f}fps  |  {total} frames  |  lang={LANG.upper()}")

    OUT_W = W + PANEL_W
    writer = cv2.VideoWriter(
        out_video, cv2.VideoWriter_fourcc(*"mp4v"), out_fps, (OUT_W, H))

    records = []
    history = []
    phase_feedback = {}
    phase_scores = {}
    sym_tracker = SymmetryTracker()
    moment_detector = CriticalMomentDetector(src_fps)
    key_frames = {}
    last_feedback = []
    no_det = 0
    idx = 0

    # ── Initializeaza PhaseDetector ──────────────────────────────────────
    global _PHASE_DETECTOR
    _PHASE_DETECTOR = PhaseDetector()

    # ── Initializeaza colectarea de features pentru K-Means ML ───────────
    # Pentru fiecare frame procesat colectam un vector biomecanic 8D.
    # La sfarsit, K-Means descopera SINGUR fazele din aceste date.
    features_list = []     # lista vectori feature (sau None)
    hip_x_history_ml = []     # pentru calcul viteza sold

    options = mp_vision.PoseLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=MODEL_PATH),
        running_mode=mp_vision.RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    with mp_vision.PoseLandmarker.create_from_options(options) as lander:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_im = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            # Timestamp REAL din sursa (MediaPipe are nevoie de timestamp monoton si corect)
            ts_ms = int(idx*(1000.0/src_fps))
            res = lander.detect_for_video(mp_im, ts_ms)

            panel = np.zeros((H, PANEL_W, 3), dtype=np.uint8)

            if res.pose_landmarks and len(res.pose_landmarks) > 0:
                lms = res.pose_landmarks[0]

                def p(i): return lm_px(lms, i, W, H)
                nose = p(0)
                lsh = p(11)
                rsh = p(12)
                lel = p(13)
                rel = p(14)
                lwr = p(15)
                rwr = p(16)
                lhip = p(23)
                rhip = p(24)
                lkn = p(25)
                rkn = p(26)
                lan = p(27)
                ran = p(28)
                lhe = p(29)
                rhe = p(30)
                lft = p(31)
                rft = p(32)
                msh = (lsh+rsh)/2
                mhip = (lhip+rhip)/2

                angles = {
                    "knee_L":   angle_3pts(lhip, lkn, lan),
                    "knee_R":   angle_3pts(rhip, rkn, ran),
                    "hip_L":    angle_3pts(lsh, lhip, lkn),
                    "hip_R":    angle_3pts(rsh, rhip, rkn),
                    "ankle_L":  angle_3pts(lkn, lan, lft),
                    "ankle_R":  angle_3pts(rkn, ran, rft),
                    "foot_L":   angle_3pts(lhe, lan, lft),
                    "foot_R":   angle_3pts(rhe, ran, rft),
                    "elbow_L":  angle_3pts(lsh, lel, lwr),
                    "elbow_R":  angle_3pts(rsh, rel, rwr),
                    "shoulder_L": angle_3pts(lhip, lsh, lel),
                    "shoulder_R": angle_3pts(rhip, rsh, rel),
                    "trunk":    angle_vertical(msh, mhip),
                    "head":     angle_vertical(nose, msh),
                }

                history.append(angles)

                # Construieste lms_pos pentru PhaseDetector
                _lms_pos = {
                    "hip_c":    mhip, "sh_c":  msh,
                    "lwr":      lwr,  "rwr":   rwr,
                    "ground_y": float(max(lft[1], rft[1])),
                }
                phase = detect_phase(history, lms_pos=_lms_pos, angles=angles)
                feedback = evaluate_frame(angles, phase)

                # ── Colectare features pentru K-Means ML ──────────────────
                # Actualizam istoricul de pozitii sold pentru viteza orizontala
                hip_x_history_ml.append(float(mhip[0]))
                if len(hip_x_history_ml) > 8:
                    hip_x_history_ml.pop(0)
                hip_vel_ml = 0.0
                if len(hip_x_history_ml) >= 3:
                    hip_vel_ml = abs(
                        hip_x_history_ml[-1] - hip_x_history_ml[0]) / len(hip_x_history_ml)

                # Construim seg pentru extract_phase_features (re-folosim compute_seg_lengths)
                _seg_for_features = {"hip_c": mhip}
                _feat = extract_phase_features(angles, _seg_for_features,
                                               hip_vel_ml, idx, total, H)
                features_list.append(_feat)
                # ──────────────────────────────────────────────────────────

                # Acumuleaza feedback pentru raport
                if phase not in phase_feedback:
                    phase_feedback[phase] = {}
                for fb in feedback:
                    k = fb["key"]
                    phase_feedback[phase][k] = phase_feedback[phase].get(
                        k, 0)+1

                # ── Calcul scor IAAF ─────────────────────────────────────
                score = compute_phase_score(angles, phase)
                if phase not in phase_scores:
                    phase_scores[phase] = []
                phase_scores[phase].append(score)

                # ── Simetrie ──────────────────────────────────────────────
                sym_tracker.add(angles, idx, round(idx/src_fps, 4), phase)

                # ── Detectie momente critice ──────────────────────────────
                ankle_y_avg = (lft[1]+rft[1])/2 if "lft" in dir() else 0
                event = moment_detector.update(angles, phase, idx,
                                               lan[1], ran[1])
                if event and event["event"] not in key_frames:
                    key_frames[event["event"]] = frame.copy()

                last_feedback = feedback

                # ── 1. Joint indicators (arce colorate IAAF) ──────────────
                # Arce verzi/galbene/rosii pe articulatii arata direct
                # cat de aproape e atletul de norma biomecanica IAAF.
                draw_joint_indicators(frame, lms, angles, phase, W, H)

                # ── 2. Scheletul real (rosu) ──────────────────────────────
                draw_skeleton(frame, lms, W, H, angles)

                # ── 3. Scor pe frame ──────────────────────────────────────
                draw_score_on_frame(frame, score, phase)

                # ── 4. Event banner ───────────────────────────────────────
                moment_detector.draw_event_overlay(frame)

                # ── 5. Watermark + nume atlet ─────────────────────────────
                draw_watermark(frame)
                draw_athlete_name(frame)

                draw_panel(panel, angles, phase, feedback,
                           idx, src_fps, out_fps, slowmo_x)

                rec = dict(angles)
                rec.update({"frame": idx,
                            "time_s": round(idx/src_fps, 4),
                            "time_s_output": round(idx/out_fps, 4),
                            "phase": phase})
                records.append(rec)
            else:
                no_det += 1
                features_list.append(None)   # placeholder pentru ML
                phase = "ANALIZA..."
                blank_angles = {k: 0.0 for k in ["knee_L", "knee_R", "hip_L", "hip_R",
                                                 "ankle_L", "ankle_R", "foot_L", "foot_R", "elbow_L", "elbow_R",
                                                 "shoulder_L", "shoulder_R", "trunk", "head"]}
                draw_panel(panel, blank_angles, phase, [],
                           idx, src_fps, out_fps, slowmo_x)
                cv2.putText(frame, "[ nicio detectie ]", (20, 70),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (30, 30, 200), 2)
                draw_watermark(frame)
                draw_athlete_name(frame)

            combined = np.hstack([frame, panel])
            writer.write(combined)
            idx += 1
            if idx % 60 == 0:
                print(f"  {idx}/{total} ({idx/max(total, 1)*100:.0f}%)")

    cap.release()

    # ═════════════════════════════════════════════════════════════════════
    # ML — K-Means descopera fazele biomecanice ALE ATLETULUI
    # ═════════════════════════════════════════════════════════════════════
    # Acum ca avem toate features-urile colectate, aplicam K-Means.
    # Algoritmul invata SINGUR tiparele specifice acestui atlet si video.
    print("\n[ML] Aplicare K-Means clustering pe features biomecanice...")
    ml_phases, ml_info = adaptive_phase_detection_ml(features_list, src_fps)
    print_ml_clustering_report(ml_info, lang=LANG)

    # ── Rescrie fazele in records cu rezultatul ML ──────────────────────
    # Pana acum records contine fazele PhaseDetector-ului (real-time, pentru
    # afisarea pe video). Acum le inlocuim cu fazele ML pentru toate
    # rapoartele finale (CSV, PDF, dashboard, end card, scoruri).
    if ml_info.get("used_ml") and records:
        # Mapeaza idx → record (records nu contine frame-uri fara detectie)
        for rec in records:
            rec_idx = rec.get("frame", 0)
            if 0 <= rec_idx < len(ml_phases):
                # pastreaza pentru transparenta
                rec["phase_rule_based"] = rec["phase"]
                rec["phase"] = ml_phases[rec_idx]

        # Reconstruieste phase_feedback si phase_scores cu fazele ML
        angle_keys = ["knee_L", "knee_R", "hip_L", "hip_R", "ankle_L", "ankle_R",
                      "foot_L", "foot_R", "elbow_L", "elbow_R",
                      "shoulder_L", "shoulder_R", "trunk", "head"]
        phase_feedback = {}
        phase_scores = {}
        for rec in records:
            phase = rec["phase"]
            angles_rec = {k: rec.get(k, 0.0) for k in angle_keys}

            # Feedback per frame
            fb_list = evaluate_frame(angles_rec, phase)
            if phase not in phase_feedback:
                phase_feedback[phase] = {}
            for fb in fb_list:
                k = fb["key"]
                phase_feedback[phase][k] = phase_feedback[phase].get(k, 0) + 1

            # Scor per frame
            score = compute_phase_score(angles_rec, phase)
            if phase not in phase_scores:
                phase_scores[phase] = []
            phase_scores[phase].append(score)

        print(f"  [ML] Faze finale per frame:")
        for ph in ["SET", "BLOCKSTART", "ACCELERATIE"]:
            count = sum(1 for r in records if r["phase"] == ph)
            if count > 0:
                avg_score = np.mean(phase_scores.get(ph, [0]))
                print(
                    f"        {ph:12} → {count} frame-uri  scor mediu: {avg_score:.1f}/100")

    # ── End card ─────────────────────────────────────────────────────────────
    scores_by_phase = {ph: round(float(np.mean(v)), 1)
                       for ph, v in phase_scores.items() if v}
    sym_sum = sym_tracker.summary()
    events_list = moment_detector.summary()
    end_card_frame = generate_end_card(
        (H, W+PANEL_W, 3), scores_by_phase,
        last_feedback, events_list, sym_sum,
        total/src_fps)

    end_card_seconds = 3
    for _ in range(int(out_fps * end_card_seconds)):
        writer.write(end_card_frame)

    writer.release()

    # ── Genereaza CSV-ul ─────────────────────────────────────────────────────
    # ML profile include în PDF, nu mai salvez JSON separat
    # Key frames JPG nu mai sunt necesare

    if records:
        cols = ["frame", "time_s", "time_s_output", "phase",
                "knee_L", "knee_R", "hip_L", "hip_R",
                "ankle_L", "ankle_R", "foot_L", "foot_R",
                "elbow_L", "elbow_R", "shoulder_L", "shoulder_R",
                "trunk", "head"]
        df = pd.DataFrame(records)
        df = df[[c for c in cols if c in df.columns]]
        df.to_csv(out_csv, index=False)
        print(f"  CSV: {out_csv}")

        # Construieste sumarul feedback pentru PDF
        feedback_summary = {}
        for phase_name, cue_counts in phase_feedback.items():
            n_phase = len([r for r in records if r.get("phase") == phase_name])
            sorted_cues = sorted(cue_counts.items(), key=lambda x: -x[1])
            feedback_summary[phase_name] = [
                (k, cnt, cnt/max(n_phase, 1)*100, COACHING_CUES[k])
                for k, cnt in sorted_cues if k in COACHING_CUES
            ]

        # UN SINGUR APEL: generate_report genereaza totul în PDF
        # (charts, symmetry, coaching, IAAF comparison, ML profile)
        sym_df = sym_tracker.to_df()
        generate_report(df, feedback_summary, ml_info, sym_df,
                        scores_by_phase, events_list,
                        out_pdf, os.path.basename(video_path))

    # ─── Re-encode pentru compatibilitate mobila (Android/iOS) ──────────
    # OpenCV scrie H264 cu profil incompatibil pe multe telefoane.
    # Folosim ffmpeg sa convertim la H264 Baseline yuv420p + faststart.
    out_video = reencode_for_mobile(out_video)

    rate = (idx-no_det)/max(idx, 1)*100
    print(f"\n[DONE]")
    print(f"  Video        : {out_video}")
    print(f"  Detectie     : {rate:.1f}%")
    if slowmo_fps > 0:
        print(
            f"  Slow motion  : {slowmo_x:.1f}x  ({src_fps:.0f}fps -> {out_fps:.0f}fps)")
        print(
            f"  Durata output: {total/out_fps:.1f}s  (original {total/src_fps:.1f}s)")


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="PBRunner Coaching Engine v3.0 — IAAF Elite Template",
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--video",   required=True,
                        help="Calea catre .mp4")
    parser.add_argument("--lang",    default="ro",  choices=["ro", "en"],
                        help="Limba instructiuni: ro / en (default: ro)")
    parser.add_argument("--height",  type=float, default=184,
                        help="Inaltimea atletului in cm (default: 184)")
    parser.add_argument("--weight",  type=float, default=82,
                        help="Greutatea atletului in kg (default: 82)")
    parser.add_argument("--age",     type=int,   default=21,
                        help="Varsta atletului in ani (default: 21)")
    parser.add_argument("--slowmo",  type=float, default=0.0,
                        help=(
                            "FPS-ul output pentru slow motion.\n"
                            "Exemplu: video 60fps + --slowmo 10 => slow motion 6x.\n"
                            "Exemplu: video 120fps + --slowmo 10 => slow motion 12x.\n"
                            "Lasa 0 pentru viteza normala (default: 0)"))
    parser.add_argument("--name",    type=str,   default="Atlet",
                        help="Numele atletului (afisat pe video si in raport)")
    args = parser.parse_args()

    # Validare slowmo
    if args.slowmo > 0:
        import cv2 as _cv2_check
        _cap = _cv2_check.VideoCapture(args.video)
        _src = _cap.get(_cv2_check.CAP_PROP_FPS)
        _cap.release()
        if _src > 0 and args.slowmo >= _src:
            print(f"[WARN] --slowmo {args.slowmo} >= fps sursa {_src:.0f}."
                  f" Slow motion va fi ignorat (output la {_src:.0f}fps).")
            args.slowmo = 0.0
        elif _src > 0:
            print(f"[INFO] Slow motion: {_src:.0f}fps -> {args.slowmo:.0f}fps "
                  f"= {_src/args.slowmo:.1f}x mai lent")

    process_video(args.video, args.lang,
                  height_cm=args.height,
                  weight_kg=args.weight,
                  age=args.age,
                  slowmo_fps=args.slowmo,
                  athlete_name=args.name)
