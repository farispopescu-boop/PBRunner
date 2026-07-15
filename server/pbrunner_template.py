"""
=============================================================================
  PBRunner — IAAF Elite Reference Template
  Sursa: IAAF Biomechanics Research Project
          "100 Metres Men — Final, London 2017"
          Carnegie School of Sport / World Athletics
=============================================================================
  Date extrase din raportul oficial IAAF:
    - Unghiuri articulare la touchdown si toe-off (Tabele 10-15)
    - Lungime pas, frecventa pas, latime pas (Tabel 3)
    - Timpi contact / zbor (Figura 10)
    - Viteze unghiulare sold/genunchi/glezna (Figuri 19.1-19.8)
    - Profile individuale: Gatlin, Coleman, Bolt, Blake, Simbine,
      Vicaut, Prescod, Su
=============================================================================
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, Tuple, Optional

# ─────────────────────────────────────────────────────────────────────────────
# DATE BRUTE IAAF — Finala 100m Barbati, Londra 2017
# Unghiuri in grade; pozitiv = extensie, negativ = flexie (conventie IAAF)
# α  = trunchi vs vertical (90° = vertical, 0° = culcat)
# β  = unghi coapsa (segment femural vs vertical)
# γ  = unghi genunchi (coapsa-gamba; 180° = intins complet)
# ζ  = unghi sold picior contact (umar-sold-genunchi)
# η  = unghi sold picior swing
# θ  = unghi coapsa picior swing vs vertical
# ι  = unghi genunchi (definitie anatomica; 180° = intins)
# κ  = unghi glezna (180° = pozitie neutra)
# ─────────────────────────────────────────────────────────────────────────────

# === TABEL 10-11: Unghiuri la TOUCHDOWN (viteza maxima, 47-55m) ===
IAAF_TOUCHDOWN = {
    "GATLIN":   {"height": 175, "weight": 73, "age": 35,
                 "alpha_L": 73.5, "alpha_R": 73.4,
                 "beta_L": 152.7, "beta_R": 148.8,
                 "gamma_L": 132.5, "gamma_R": 144.1,
                 "zeta_L": 36.9, "zeta_R": 33.7,
                 "eta_L": 12.1, "eta_R": 6.0,
                 "theta_L": -24.6, "theta_R": -27.7,
                 "iota_L": 103.0, "iota_R": 98.1,
                 "kappa_L": 102.3, "kappa_R": 111.5},
    "COLEMAN":  {"height": 175, "weight": 70, "age": 21,
                 "alpha_L": 74.2, "alpha_R": 76.5,
                 "beta_L": 143.4, "beta_R": 161.5,
                 "gamma_L": 134.7, "gamma_R": 144.1,
                 "zeta_L": 37.4, "zeta_R": 36.3,
                 "eta_L": 1.5, "eta_R": 7.4,
                 "theta_L": -25.9, "theta_R": -13.5,
                 "iota_L": 105.7, "iota_R": 95.4,
                 "kappa_L": 122.3, "kappa_R": 119.8},
    "BOLT":     {"height": 195, "weight": 94, "age": 30,
                 "alpha_L": 76.8, "alpha_R": 72.7,
                 "beta_L": 161.5, "beta_R": 127.1,
                 "gamma_L": 143.0, "gamma_R": 127.1,
                 "zeta_L": 38.8, "zeta_R": 22.3,
                 "eta_L": 2.8, "eta_R": 36.8,
                 "theta_L": -31.6, "theta_R": -4.6,
                 "iota_L": 103.7, "iota_R": 65.4,
                 "kappa_L": 115.3, "kappa_R": 118.2},
    "BLAKE":    {"height": 180, "weight": 76, "age": 27,
                 "alpha_L": 99.7, "alpha_R": 73.3,
                 "beta_L": 152.3, "beta_R": 156.0,
                 "gamma_L": 131.3, "gamma_R": 135.5,
                 "zeta_L": 33.2, "zeta_R": 24.2,
                 "eta_L": 15.9, "eta_R": 13.0,
                 "theta_L": -22.0, "theta_R": -22.2,
                 "iota_L": 116.3, "iota_R": 111.8,
                 "kappa_L": 120.1, "kappa_R": 117.6},
    "SIMBINE":  {"height": 184, "weight": 75, "age": 23,
                 "alpha_L": 107.8, "alpha_R": 109.4,
                 "beta_L": 148.1, "beta_R": 155.2,
                 "gamma_L": 134.8, "gamma_R": 136.9,
                 "zeta_L": 28.2, "zeta_R": 30.5,
                 "eta_L": 15.8, "eta_R": 11.0,
                 "theta_L": -18.5, "theta_R": -19.4,
                 "iota_L": 113.1, "iota_R": 111.4,
                 "kappa_L": 119.3, "kappa_R": 118.4},
    "VICAUT":   {"height": 176, "weight": 73, "age": 26,
                 "alpha_L": 98.5, "alpha_R": 100.4,
                 "beta_L": 141.0, "beta_R": 135.2,
                 "gamma_L": 130.6, "gamma_R": 130.4,
                 "zeta_L": 29.7, "zeta_R": 26.7,
                 "eta_L": 10.7, "eta_R": 8.2,
                 "theta_L": -27.5, "theta_R": -13.7,
                 "iota_L": 111.4, "iota_R": 106.7,
                 "kappa_L": 119.5, "kappa_R": 116.4},
    "PRESCOD":  {"height": 185, "weight": 76, "age": 21,
                 "alpha_L": 98.5, "alpha_R": 105.2,
                 "beta_L": 148.5, "beta_R": 161.0,
                 "gamma_L": 130.6, "gamma_R": 138.5,
                 "zeta_L": 30.7, "zeta_R": 30.5,
                 "eta_L": 12.5, "eta_R": 8.5,
                 "theta_L": -27.5, "theta_R": -21.5,
                 "iota_L": 117.6, "iota_R": 113.6,
                 "kappa_L": 117.5, "kappa_R": 116.4},
    "SU":       {"height": 173, "weight": 65, "age": 28,
                 "alpha_L": 96.5, "alpha_R": 97.0,
                 "beta_L": 145.3, "beta_R": 152.4,
                 "gamma_L": 130.0, "gamma_R": 133.2,
                 "zeta_L": 28.8, "zeta_R": 27.0,
                 "eta_L": 14.2, "eta_R": 13.0,
                 "theta_L": -27.0, "theta_R": -26.4,
                 "iota_L": 109.8, "iota_R": 108.0,
                 "kappa_L": 115.3, "kappa_R": 114.3},
}

# === TABEL 12-13: Unghiuri la TOE-OFF (viteza maxima) ===
IAAF_TOEOFF = {
    "GATLIN":  {"alpha_L": 77.9, "alpha_R": 81.2,
                "beta_L": 160.5, "beta_R": 155.0,
                "gamma_L": 155.7, "gamma_R": 110.9,
                "zeta_L": -28.7, "zeta_R": -38.3,
                "eta_L": 56.4, "eta_R": 66.7,
                "iota_L": 103.0, "iota_R": 98.1,
                "kappa_L": 132.0, "kappa_R": 131.3},
    "COLEMAN": {"alpha_L": 83.2, "alpha_R": 81.2,
                "beta_L": 155.2, "beta_R": 151.9,
                "gamma_L": 155.5, "gamma_R": 159.0,
                "zeta_L": -25.5, "zeta_R": -27.4,
                "eta_L": 57.4, "eta_R": 61.5,
                "iota_L": 130.0, "iota_R": 128.5,
                "kappa_L": 141.0, "kappa_R": 138.0},
    "BOLT":    {"alpha_L": 61.2, "alpha_R": 81.8,
                "beta_L": 157.6, "beta_R": 155.8,
                "gamma_L": 158.0, "gamma_R": 145.7,
                "zeta_L": -30.1, "zeta_R": -41.2,
                "eta_L": 60.5, "eta_R": 67.0,
                "iota_L": 125.0, "iota_R": 132.5,
                "kappa_L": 140.4, "kappa_R": 143.7},
    "BLAKE":   {"alpha_L": 75.0, "alpha_R": 74.8,
                "beta_L": 152.7, "beta_R": 167.7,
                "gamma_L": 185.7, "gamma_R": 187.1,
                "zeta_L": -32.0, "zeta_R": -27.0,
                "eta_L": 74.9, "eta_R": 77.1,
                "iota_L": 138.0, "iota_R": 139.0,
                "kappa_L": 142.4, "kappa_R": 141.6},
    "SIMBINE": {"alpha_L": 95.6, "alpha_R": 98.8,
                "beta_L": 149.9, "beta_R": 156.0,
                "gamma_L": 182.0, "gamma_R": 156.0,
                "zeta_L": -32.0, "zeta_R": -31.0,
                "eta_L": 76.5, "eta_R": 77.5,
                "iota_L": 140.0, "iota_R": 136.0,
                "kappa_L": 143.2, "kappa_R": 142.0},
}

# === TABEL 3: Date cinematice la viteza maxima (47-55m) ===
IAAF_KINEMATICS = {
    "GATLIN":  {"step_length_m": 2.51, "rel_step": 1.36, "step_rate_hz": 4.67,
                "step_width_m": 0.12, "mean_speed_ms": 11.73},
    "COLEMAN": {"step_length_m": 2.33, "rel_step": 1.25, "step_rate_hz": 4.55,
                "step_width_m": 0.20, "mean_speed_ms": 11.53},
    "BOLT":    {"step_length_m": 2.70, "rel_step": 1.35, "step_rate_hz": 4.38,
                "step_width_m": 0.15, "mean_speed_ms": 11.84},
    "BLAKE":   {"step_length_m": 2.38, "rel_step": 1.32, "step_rate_hz": 4.65,
                "step_width_m": 0.20, "mean_speed_ms": 11.55},
    "SIMBINE": {"step_length_m": 2.38, "rel_step": 1.29, "step_rate_hz": 4.90,
                "step_width_m": 0.21, "mean_speed_ms": 11.55},
    "VICAUT":  {"step_length_m": 2.38, "rel_step": 1.30, "step_rate_hz": 4.65,
                "step_width_m": 0.22, "mean_speed_ms": 11.72},
    "PRESCOD": {"step_length_m": 2.51, "rel_step": 1.36, "step_rate_hz": 4.63,
                "step_width_m": 0.22, "mean_speed_ms": 11.62},
    "SU":      {"step_length_m": 2.36, "rel_step": 1.36, "step_rate_hz": 5.00,
                "step_width_m": 0.13, "mean_speed_ms": 11.30},
}

# === TABEL 2.1: Timpi split la fiecare 10m ===
IAAF_SPLITS = {
    "GATLIN":  {"RT": 0.138, "0_10": 1.88, "10_20": 1.02, "20_30": 0.91,
                "30_40": 0.90, "40_50": 0.88, "50_60": 0.86, "60_70": 0.86,
                "70_80": 0.87, "80_90": 0.87, "90_100": 0.87, "total": 9.92},
    "COLEMAN": {"RT": 0.123, "0_10": 1.87, "10_20": 1.00, "20_30": 0.90,
                "30_40": 0.88, "40_50": 0.87, "50_60": 0.86, "60_70": 0.88,
                "70_80": 0.88, "80_90": 0.88, "90_100": 0.52, "total": 9.94},
    "BOLT":    {"RT": 0.183, "0_10": 1.96, "10_20": 1.02, "20_30": 0.90,
                "30_40": 0.88, "40_50": 0.85, "50_60": 0.85, "60_70": 0.86,
                "70_80": 0.86, "80_90": 0.89, "90_100": 9.35, "total": 9.95},
}

# === TABEL 16: Step penultim + final (finisare) ===
IAAF_FINISH = {
    "GATLIN":  {"step_length_ps": 3.70, "step_rate_ps": 3.24, "vel_ps": 11.44,
                "contact_ps_ms": 104, "flight_ps_ms": 136,
                "contact_fs_ms": 140, "flight_fs_ms": 140},
    "COLEMAN": {"step_length_ps": 3.45, "step_rate_ps": 4.55, "vel_ps": 11.14,
                "contact_ps_ms": 98, "flight_ps_ms": 123,
                "contact_fs_ms": 134, "flight_fs_ms": 152},
    "BOLT":    {"step_length_ps": 3.87, "step_rate_ps": 3.97, "vel_ps": 11.34,
                "contact_ps_ms": 112, "flight_ps_ms": 124,
                "contact_fs_ms": 104, "flight_fs_ms": 152},
}

# ─────────────────────────────────────────────────────────────────────────────
# GENERATOR DE PROFIL PERSONALIZAT
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class AthleteProfile:
    """Profilul biomecanic personalizat al atletului."""
    height_cm:   float
    weight_kg:   float
    age:         int
    name:        str = "Atlet"

    # Calculat automat
    bmi:          float = field(init=False)
    height_m:     float = field(init=False)
    similar_elites: list = field(default_factory=list)

    # Tinte cinematice (calculate din IAAF)
    target_step_length_m:  float = field(init=False)
    target_step_rate_hz:   float = field(init=False)
    target_step_width_m:   float = field(init=False)
    target_speed_ms:       float = field(init=False)

    # Ranguri optime per faza (grade) — cheie: unghi_articulatie
    ranges: Dict = field(default_factory=dict)

    # Referinte directe IAAF (cei mai similari atleti)
    iaaf_ref_td:  Dict = field(default_factory=dict)
    iaaf_ref_to:  Dict = field(default_factory=dict)

    def __post_init__(self):
        self.bmi = self.weight_kg / (self.height_cm/100)**2
        self.height_m = self.height_cm / 100
        self._find_similar_elites()
        self._compute_kinematics()
        self._compute_angle_ranges()
        self._build_iaaf_refs()

    def _find_similar_elites(self):
        """Gaseste cei mai similari atleti de elita din baza IAAF."""
        scored = []
        for name, td in IAAF_TOUCHDOWN.items():
            h = td["height"]
            dist = abs(h - self.height_cm)
            scored.append((dist, name))
        scored.sort()
        self.similar_elites = [name for _, name in scored[:3]]

    def _compute_kinematics(self):
        """
        Calculeaza tintele cinematice prin interpolare ponderata
        pe baza inaltimii atletului.
        """
        # Ponderi inversate distantei de inaltime
        weights = {}
        total_w = 0.0
        for name, kin in IAAF_KINEMATICS.items():
            td = IAAF_TOUCHDOWN[name]
            dist = abs(td["height"] - self.height_cm) + 1
            w = 1.0 / dist
            weights[name] = w
            total_w += w

        step_len = sum(IAAF_KINEMATICS[n]["step_length_m"] * w
                       for n, w in weights.items()) / total_w
        step_rate = sum(IAAF_KINEMATICS[n]["step_rate_hz"] * w
                        for n, w in weights.items()) / total_w
        step_wid = sum(IAAF_KINEMATICS[n]["step_width_m"] * w
                       for n, w in weights.items()) / total_w
        speed = sum(IAAF_KINEMATICS[n]["mean_speed_ms"] * w
                    for n, w in weights.items()) / total_w

        # Ajustare pe baza inaltimii relative (relatia log-lineara din date)
        # Dupa date: rel_step ~ 1.30-1.36 independent de inaltime
        # Folosim media ponderata a relativului si inmultim cu inaltimea
        rel_step = sum(IAAF_KINEMATICS[n]["rel_step"] * w
                       for n, w in weights.items()) / total_w

        self.target_step_length_m = round(rel_step * self.height_m, 3)
        self.target_step_rate_hz = round(step_rate, 2)
        self.target_step_width_m = round(step_wid,  3)
        self.target_speed_ms = round(speed,     2)

    def _compute_angle_ranges(self):
        """
        Construieste rangurile optime de unghi per faza
        prin interpolare ponderata pe baza similaritatii de inaltime.
        """
        weights = {}
        total_w = 0.0
        for name, td in IAAF_TOUCHDOWN.items():
            dist = abs(td["height"] - self.height_cm) + 1
            w = 1.0 / dist
            weights[name] = w
            total_w += w

        def wavg(key, source_dict=IAAF_TOUCHDOWN):
            vals = [source_dict[n].get(key, 0) * w
                    for n, w in weights.items()
                    if key in source_dict.get(n, {})]
            return sum(vals) / total_w if vals else 0

        # ── Unghiuri la TOUCHDOWN ──
        trunk_td = wavg("alpha_L")   # trunchi vs vertical
        knee_td = (wavg("iota_L") + wavg("iota_R")) / 2
        ankle_td = (wavg("kappa_L") + wavg("kappa_R")) / 2
        hip_zeta = (wavg("zeta_L") + wavg("zeta_R")) / 2

        # ── Unghiuri la TOE-OFF ──
        trunk_to = wavg("alpha_L", IAAF_TOEOFF)
        knee_to = (wavg("iota_L", IAAF_TOEOFF) +
                   wavg("iota_R", IAAF_TOEOFF)) / 2
        ankle_to = (wavg("kappa_L", IAAF_TOEOFF) +
                    wavg("kappa_R", IAAF_TOEOFF)) / 2

        # ── Toleranta (+/- grade) ──
        tol_opt = 8    # banda verde
        tol_acc = 18   # banda galben

        def rng(val, t_o=None, t_a=None):
            t_o = t_o or tol_opt
            t_a = t_a or tol_acc
            return (round(val-t_o, 1), round(val+t_o, 1),
                    round(val-t_a, 1), round(val+t_a, 1))

        self.ranges = {

            # ─── VITEZA MAXIMA ────────────────────────────────────────────
            "viteza_max": {
                # Trunchi vs vertical: ~74gr la TD → ~79gr la TO
                "trunk_TD":    rng(trunk_td,  6, 14),
                "trunk_TO":    rng(trunk_to,  6, 14),
                # Genunchi la TD: ~105gr (flexat la aterizare)
                "knee_L_TD":   rng(knee_td,   8, 18),
                "knee_R_TD":   rng(knee_td,   8, 18),
                # Genunchi la TO: swing leg ~130gr
                "knee_L_TO":   rng(knee_to,  12, 25),
                "knee_R_TO":   rng(knee_to,  12, 25),
                # Glezna TD: ~112gr (usor dorsiflexata)
                "ankle_L_TD":  rng(ankle_td,  8, 18),
                "ankle_R_TD":  rng(ankle_td,  8, 18),
                # Glezna TO: ~136gr (plantarflexie activa)
                "ankle_L_TO":  rng(ankle_to,  8, 18),
                "ankle_R_TO":  rng(ankle_to,  8, 18),
                # Sold la contact: ~35gr
                "hip_contact": rng(hip_zeta,  8, 18),
            },

            # ─── ACCELERATIE ─────────────────────────────────────────────
            # La acceleratie trunchiul e mai aplecat, genunchii mai flexati
            "acceleratie": {
                "trunk":       rng(45, 10, 22),   # mai inclinat ~45gr
                "knee_L":      rng(110, 12, 25),
                "knee_R":      rng(110, 12, 25),
                "hip_L":       rng(90,  12, 25),
                "hip_R":       rng(90,  12, 25),
                "ankle_L":     rng(95,  10, 20),
                "ankle_R":     rng(95,  10, 20),
                "elbow_L":     rng(90,  10, 20),
                "elbow_R":     rng(90,  10, 20),
                "shoulder_L":  rng(55,  15, 30),
                "shoulder_R":  rng(55,  15, 30),
            },

            # ─── BLOCKSTART ──────────────────────────────────────────────
            # Bazat pe biomechanica clasica blockstart IAAF
            "blockstart": {
                "trunk":       rng(25,  10, 20),   # foarte aplecat
                "knee_front":  rng(93,  8,  18),   # 85-101gr optim
                "knee_rear":   rng(125, 10, 22),   # 115-135gr optim
                "hip":         rng(45,  10, 20),   # sold jos
                "ankle":       rng(70,  10, 20),   # dorsiflexie activa
                "elbow":       rng(92,  7,  15),   # suport greutate ~90gr
            },
        }

    def _build_iaaf_refs(self):
        """Construieste referintele IAAF pentru cei mai similari atleti."""
        for name in self.similar_elites:
            self.iaaf_ref_td[name] = IAAF_TOUCHDOWN.get(name, {})
            self.iaaf_ref_to[name] = IAAF_TOEOFF.get(name, {})

    def summary(self) -> dict:
        """Returneaza un sumar al profilului pentru raport."""
        return {
            "athlete":          self.name,
            "height_cm":        self.height_cm,
            "weight_kg":        self.weight_kg,
            "age":              self.age,
            "bmi":              round(self.bmi, 1),
            "similar_elites":   self.similar_elites,
            "targets": {
                "step_length_m":  self.target_step_length_m,
                "step_rate_hz":   self.target_step_rate_hz,
                "step_width_m":   self.target_step_width_m,
                "target_speed_ms": self.target_speed_ms,
            },
            "iaaf_source": "IAAF Biomechanics Research Project, London 2017",
        }


# ─────────────────────────────────────────────────────────────────────────────
# MOTOR COACHING BAZAT PE TEMPLATE IAAF
# ─────────────────────────────────────────────────────────────────────────────

class IAAFCoachEngine:
    """
    Genereaza coaching feedback comparat cu template-ul IAAF personalizat.
    Spre deosebire de motorul cu reguli fixe din pbrunner_coach.py,
    acesta foloseste tintele calculate din datele reale de elita.
    """

    def __init__(self, profile: AthleteProfile, lang: str = "ro"):
        self.profile = profile
        self.lang = lang

    def evaluate(self, angles: dict, phase: str) -> list:
        """
        Compara unghiurile masive cu template-ul si returneaza
        lista de recomandari prioritizate.
        """
        feedback = []
        p = self.profile
        ph_key = self._phase_key(phase)
        rng = p.ranges.get(ph_key, {})

        trunk = angles.get("trunk", 90)
        kl = angles.get("knee_L", 130)
        kr = angles.get("knee_R", 130)
        hl = angles.get("hip_L",  120)
        hr = angles.get("hip_R",  120)
        al = angles.get("ankle_L", 90)
        ar = angles.get("ankle_R", 90)
        el = angles.get("elbow_L", 90)
        er = angles.get("elbow_R", 90)
        sl = angles.get("shoulder_L", 60)
        sr = angles.get("shoulder_R", 60)
        head = angles.get("head", 10)

        def check(val, rng_key, msgs_over, msgs_under, priority=2):
            if rng_key not in rng:
                return
            mn_o, mx_o, mn_a, mx_a = rng[rng_key]
            if val > mx_o:
                self._add(feedback, val, mn_o, mx_o,
                          msgs_over,  priority, "over")
            elif val < mn_o:
                self._add(feedback, val, mn_o, mx_o,
                          msgs_under, priority, "under")

        if ph_key == "viteza_max":
            check(trunk, "trunk_TD",
                  {"ro": f"Trunchiul prea vertical ({trunk:.0f}gr) — tinteste ~{rng.get('trunk_TD', (74, 74, 0, 0))[0]+8:.0f}gr la contact cu solul",
                   "en": f"Trunk too upright ({trunk:.0f}deg) — aim ~{rng.get('trunk_TD', (74, 74, 0, 0))[0]+8:.0f}deg at ground contact"},
                  {"ro": f"Trunchiul prea aplecat ({trunk:.0f}gr) — la viteza maxima ridica-l catre ~{rng.get('trunk_TD', (74, 74, 0, 0))[0]+8:.0f}gr",
                   "en": f"Trunk too inclined ({trunk:.0f}deg) — at max speed raise to ~{rng.get('trunk_TD', (74, 74, 0, 0))[0]+8:.0f}deg"},
                  priority=2)
            check(kl, "knee_L_TD",
                  {"ro": f"Genunchi stang prea intins la aterizare ({kl:.0f}gr vs optim {rng.get('knee_L_TD', (105, 105, 0, 0))[0]+8:.0f}gr) — risc crescut de frana",
                   "en": f"Left knee too extended at landing ({kl:.0f}deg vs optimal {rng.get('knee_L_TD', (105, 105, 0, 0))[0]+8:.0f}deg) — braking risk"},
                  {"ro": f"Genunchi stang prea flexat la aterizare ({kl:.0f}gr) — extinde mai mult la contact",
                   "en": f"Left knee too flexed at landing ({kl:.0f}deg) — extend more at contact"},
                  priority=1)
            check(kr, "knee_R_TD",
                  {"ro": f"Genunchi drept prea intins la aterizare ({kr:.0f}gr vs elita ~{rng.get('knee_R_TD', (105, 105, 0, 0))[0]+8:.0f}gr)",
                   "en": f"Right knee too extended at landing ({kr:.0f}deg vs elite ~{rng.get('knee_R_TD', (105, 105, 0, 0))[0]+8:.0f}deg)"},
                  {"ro": f"Genunchi drept prea flexat la aterizare ({kr:.0f}gr)",
                   "en": f"Right knee too flexed at landing ({kr:.0f}deg)"},
                  priority=1)
            check(al, "ankle_L_TD",
                  {"ro": f"Glezna stanga prea plantarflexata la contact ({al:.0f}gr) — aterizeaza pe metatars cu dorsiflexie activa ~{rng.get('ankle_L_TD', (112, 112, 0, 0))[0]+8:.0f}gr",
                   "en": f"Left ankle too plantarflexed at contact ({al:.0f}deg) — land on forefoot with active dorsiflexion ~{rng.get('ankle_L_TD', (112, 112, 0, 0))[0]+8:.0f}deg"},
                  {"ro": f"Glezna stanga prea dorsiflexata ({al:.0f}gr) — impinge activ la decolare",
                   "en": f"Left ankle over-dorsiflexed ({al:.0f}deg) — push actively at toe-off"},
                  priority=2)
            check(ar, "ankle_R_TD",
                  {"ro": f"Glezna dreapta prea plantarflexata la contact ({ar:.0f}gr)",
                   "en": f"Right ankle too plantarflexed at contact ({ar:.0f}deg)"},
                  {"ro": f"Glezna dreapta prea dorsiflexata ({ar:.0f}gr)",
                   "en": f"Right ankle over-dorsiflexed ({ar:.0f}deg)"},
                  priority=2)

        elif ph_key == "acceleratie":
            check(trunk, "trunk",
                  {"ro": f"Trunchiul prea vertical in acceleratie ({trunk:.0f}gr) — mentine inclinatia ~45gr pentru forta de propulsie",
                   "en": f"Trunk too upright in acceleration ({trunk:.0f}deg) — maintain ~45deg incline for propulsion"},
                  {"ro": f"Trunchiul prea aplecat in acceleratie ({trunk:.0f}gr) — nu te apleca excesiv, risc de cadere",
                   "en": f"Trunk too inclined in acceleration ({trunk:.0f}deg) — don't over-lean, fall risk"},
                  priority=1)
            check(kl, "knee_L",
                  {"ro": f"Extinde complet genunchiul stang la propulsie ({kl:.0f}gr) — tinteste ~{rng.get('knee_L', (110, 110, 0, 0))[0]+12:.0f}gr",
                   "en": f"Fully extend left knee at push-off ({kl:.0f}deg) — aim ~{rng.get('knee_L', (110, 110, 0, 0))[0]+12:.0f}deg"},
                  {"ro": f"Genunchi stang prea flexat la recuperare ({kl:.0f}gr) — ridica-l mai sus",
                   "en": f"Left knee too flexed at recovery ({kl:.0f}deg) — drive it higher"},
                  priority=1)
            check(kr, "knee_R",
                  {"ro": f"Extinde complet genunchiul drept la propulsie ({kr:.0f}gr)",
                   "en": f"Fully extend right knee at push-off ({kr:.0f}deg)"},
                  {"ro": f"Genunchi drept prea flexat la recuperare ({kr:.0f}gr)",
                   "en": f"Right knee too flexed at recovery ({kr:.0f}deg)"},
                  priority=1)
            check(el, "elbow_L",
                  {"ro": f"Cotul stang se deschide ({el:.0f}gr) — mentine ~90gr tot ciclul",
                   "en": f"Left elbow opening ({el:.0f}deg) — maintain ~90deg throughout"},
                  {"ro": f"Cotul stang prea inchis ({el:.0f}gr)",
                   "en": f"Left elbow too closed ({el:.0f}deg)"},
                  priority=2)
            check(er, "elbow_R",
                  {"ro": f"Cotul drept se deschide ({er:.0f}gr) — bracke bratele ~90gr",
                   "en": f"Right elbow opening ({er:.0f}deg) — keep arms ~90deg"},
                  {"ro": f"Cotul drept prea inchis ({er:.0f}gr)",
                   "en": f"Right elbow too closed ({er:.0f}deg)"},
                  priority=2)

        elif ph_key == "blockstart":
            check(trunk, "trunk",
                  {"ro": f"Trunchiul prea vertical la start ({trunk:.0f}gr) — tinteste ~25gr fata de vertical, greutatea pe maini",
                   "en": f"Trunk too upright at start ({trunk:.0f}deg) — aim ~25deg from vertical, weight on hands"},
                  {"ro": f"Trunchiul prea orizontal la start ({trunk:.0f}gr) — ridica putin soldurile",
                   "en": f"Trunk too horizontal at start ({trunk:.0f}deg) — raise hips slightly"},
                  priority=1)
            check(kl, "knee_front",
                  {"ro": f"Genunchi front prea deschis ({kl:.0f}gr) — adanceste pozitia in bloc, tinteste ~93gr",
                   "en": f"Front knee too open ({kl:.0f}deg) — deepen block position, aim ~93deg"},
                  {"ro": f"Genunchi front prea inchis ({kl:.0f}gr) — deschide pozitia in bloc",
                   "en": f"Front knee too closed ({kl:.0f}deg) — open block position"},
                  priority=1)

        # Universal — orice faza
        if head > 45:
            feedback.append({
                "key": "head_alignment",
                "text": (f"Capul ridicat ({head:.0f}gr) — aliniaza-l cu coloana, priveste 2-3m inainte"
                         if self.lang == "ro" else
                         f"Head raised ({head:.0f}deg) — align with spine, look 2-3m ahead"),
                "priority": 3, "phase": "ALL",
                "detail": (f"Capul ridicat creeaza tensiune in trapez si destabilizeaza trunchiul. "
                           f"Elit: Gatlin mentinea capul la ~{IAAF_TOUCHDOWN['GATLIN']['alpha_L']-65:.0f}gr fata de coloana."
                           if self.lang == "ro" else
                           f"Raised head creates trapezius tension and destabilizes trunk. "
                           f"Elite: Gatlin maintained head at ~{IAAF_TOUCHDOWN['GATLIN']['alpha_L']-65:.0f}deg from spine."),
            })

        if abs(kl - kr) > 22:
            asym = abs(kl - kr)
            feedback.append({
                "key": "knee_asymmetry",
                "text": (f"Asimetrie genunchi {asym:.0f}gr — lucreaza bilateral la exercitii de forta"
                         if self.lang == "ro" else
                         f"Knee asymmetry {asym:.0f}deg — work bilateral strength exercises"),
                "priority": 2, "phase": "ALL",
                "detail": (f"Asimetria reduce eficienta ciclului pasului. "
                           f"Toleranta de elita: <15gr intre picioare (Gatlin: {abs(IAAF_TOUCHDOWN['GATLIN']['iota_L']-IAAF_TOUCHDOWN['GATLIN']['iota_R']):.1f}gr)."
                           if self.lang == "ro" else
                           f"Asymmetry reduces stride cycle efficiency. "
                           f"Elite tolerance: <15deg between legs (Gatlin: {abs(IAAF_TOUCHDOWN['GATLIN']['iota_L']-IAAF_TOUCHDOWN['GATLIN']['iota_R']):.1f}deg)."),
            })

        feedback.sort(key=lambda x: x["priority"])
        return feedback

    def _phase_key(self, phase: str) -> str:
        return {"BLOCKSTART": "blockstart", "ACCELERATIE": "acceleratie",
                "VITEZA MAX": "viteza_max", "ANALIZA...": "acceleratie"}.get(phase, "acceleratie")

    def _add(self, feedback, val, mn_o, mx_o, msgs, priority, direction):
        opt_val = (mn_o + mx_o) / 2
        diff = abs(val - opt_val)
        text = msgs.get(self.lang, msgs.get("ro", ""))
        # Adauga referinta IAAF
        ref_name = self.profile.similar_elites[0] if self.profile.similar_elites else "elita"
        detail_ro = (f"Tinta IAAF pentru {self.profile.height_cm}cm: {mn_o:.0f}-{mx_o:.0f}gr. "
                     f"Referinta: {ref_name} la viteza maxima.")
        detail_en = (f"IAAF target for {self.profile.height_cm}cm: {mn_o:.0f}-{mx_o:.0f}deg. "
                     f"Reference: {ref_name} at max speed.")
        feedback.append({
            "key":      f"iaaf_{direction}_{len(feedback)}",
            "text":     text,
            "detail":   detail_ro if self.lang == "ro" else detail_en,
            "priority": priority,
            "phase":    "CURRENT",
            "deviation_deg": round(diff, 1),
        })


# ─────────────────────────────────────────────────────────────────────────────
# PROFIL DEFAULT — atletul tau
# ─────────────────────────────────────────────────────────────────────────────
def create_default_profile(lang="ro") -> AthleteProfile:
    """
    Profil pre-calculat pentru:
        Inaltime : 184 cm
        Greutate : 82 kg
        Varsta   : 21 ani
    """
    return AthleteProfile(
        height_cm=184,
        weight_kg=82,
        age=21,
        name="Atlet PBRunner",
    )


# ─────────────────────────────────────────────────────────────────────────────
# MAIN — test standalone
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json
    profile = create_default_profile()
    print("\n" + "="*60)
    print("  PROFIL BIOMECANIC PERSONALIZAT — IAAF 2017")
    print("="*60)
    s = profile.summary()
    print(
        f"\n  Atlet       : {s['height_cm']}cm / {s['weight_kg']}kg / {s['age']} ani")
    print(f"  BMI         : {s['bmi']}")
    print(f"  Cei mai similari din IAAF: {', '.join(s['similar_elites'])}")
    print(f"\n  TINTE CINEMATICE (viteza maxima):")
    t = s["targets"]
    print(f"    Lungime pas  : {t['step_length_m']:.2f} m")
    print(f"    Frecventa    : {t['step_rate_hz']:.2f} Hz")
    print(f"    Latime pas   : {t['step_width_m']:.3f} m")
    print(f"    Viteza tinta : {t['target_speed_ms']:.2f} m/s")

    print(f"\n  RANGURI UNGHIURI — VITEZA MAXIMA:")
    for k, v in profile.ranges["viteza_max"].items():
        print(
            f"    {k:20s}: optim {v[0]:.0f}-{v[1]:.0f}gr  |  acceptabil {v[2]:.0f}-{v[3]:.0f}gr")

    # Test coaching
    print("\n  TEST COACHING (simulare unghi genunchi prea deschis):")
    engine = IAAFCoachEngine(profile, lang="ro")
    test_angles = {"trunk": 74, "knee_L": 145, "knee_R": 90, "hip_L": 120, "hip_R": 118,
                   "ankle_L": 85, "ankle_R": 92, "elbow_L": 95, "elbow_R": 105,
                   "shoulder_L": 55, "shoulder_R": 58, "head": 15}
    fb = engine.evaluate(test_angles, "VITEZA MAX")
    for f in fb:
        print(f"    [{f['priority']}] {f['text']}")
        if "detail" in f:
            print(f"        -> {f['detail']}")
