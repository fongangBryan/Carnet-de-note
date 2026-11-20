"""Fonctions de calcul et de validation pures (aucune dépendance à Tkinter ni à SQLite)."""

from __future__ import annotations

import re
import statistics

NOTE_MIN, NOTE_MAX = 0.0, 20.0
SEUIL_ADMISSION = 10.0
COEF_MAX = 100.0

# Accepte « 12 », « 12.5 », « 12,5 », « -3 » (refusé ensuite par la borne)
_RE_NOMBRE = re.compile(r"^-?\d+(?:[.,]\d+)?$")

# Tranches de l'histogramme : (libellé, borne basse incluse, couleur)
TRANCHES = (
    ("< 10", 0.0, "#C0392B"),
    ("10-12", 10.0, "#E67E22"),
    ("12-14", 12.0, "#F1C40F"),
    ("14-16", 14.0, "#2ECC71"),
    ("16-20", 16.0, "#1E8449"),
)


# ----------------------------------------------------------------- validation
def lire_nombre(texte: str) -> float:
    """Convertit une saisie utilisateur (virgule ou point) en float. Lève ValueError."""
    t = str(texte).strip().replace(" ", "").replace(" ", "")
    if not _RE_NOMBRE.match(t):
        raise ValueError(texte)
    return float(t.replace(",", "."))


def valider_note(texte: str, libelle: str = "La note") -> float:
    """Valide une note sur 20 saisie au clavier et renvoie sa valeur arrondie au centième."""
    if not str(texte).strip():
        raise ValueError(f"{libelle} est vide.")
    try:
        valeur = lire_nombre(texte)
    except ValueError:
        raise ValueError(
            f"{libelle} « {texte} » n'est pas un nombre valide.\n"
            "Exemples acceptés : 12   12,5   12.5"
        ) from None
    if not NOTE_MIN <= valeur <= NOTE_MAX:
        raise ValueError(f"{libelle} doit être comprise entre 0 et 20 (valeur saisie : {texte}).")
    return round(valeur, 2)


def valider_coefficient(texte: str) -> float:
    """Valide un coefficient strictement positif (max 100)."""
    try:
        valeur = lire_nombre(texte)
    except ValueError:
        raise ValueError(f"Le coefficient « {texte} » n'est pas un nombre valide (ex : 2 ou 1,5).") from None
    if not 0 < valeur <= COEF_MAX:
        raise ValueError("Le coefficient doit être strictement positif et inférieur ou égal à 100.")
    return round(valeur, 2)


# ------------------------------------------------------------------- calculs
def moyenne_ponderee(notes: dict[int, float], coefficients: dict[int, float]) -> float | None:
    """Moyenne pondérée des matières notées. None si aucune note."""
    total_coef = sum(coefficients[m] for m in notes if m in coefficients)
    if total_coef == 0:
        return None
    return sum(v * coefficients[m] for m, v in notes.items() if m in coefficients) / total_coef


def classer(valeurs: dict[int, float | None]) -> dict[int, int]:
    """Rang de chaque identifiant (rang « olympique » : 1, 2, 2, 4). Les None ne sont pas classés."""
    notes = [v for v in valeurs.values() if v is not None]
    return {
        cle: 1 + sum(1 for autre in notes if autre > v + 1e-9)
        for cle, v in valeurs.items() if v is not None
    }


def indicateurs(valeurs: list[float]) -> dict | None:
    """Indicateurs statistiques complets d'une série de notes."""
    if not valeurs:
        return None
    admis = sum(1 for v in valeurs if v >= SEUIL_ADMISSION)
    return {
        "effectif": len(valeurs),
        "moyenne": statistics.mean(valeurs),
        "ecart_type": statistics.stdev(valeurs) if len(valeurs) >= 2 else 0.0,
        "mediane": statistics.median(valeurs),
        "min": min(valeurs),
        "max": max(valeurs),
        "admis": admis,
        "ajournes": len(valeurs) - admis,
        "taux_reussite": 100 * admis / len(valeurs),
    }


def tranche(valeur: float) -> int:
    """Indice de la tranche d'histogramme d'une note."""
    for i in range(len(TRANCHES) - 1, -1, -1):
        if valeur >= TRANCHES[i][1]:
            return i
    return 0


def mention(moyenne: float | None) -> str:
    if moyenne is None:
        return "—"
    if moyenne < 10:
        return "Ajourné"
    if moyenne < 12:
        return "Passable"
    if moyenne < 14:
        return "Assez bien"
    if moyenne < 16:
        return "Bien"
    return "Très bien"


def libelle_rang(rang: int | None, podium: bool = True) -> str:
    """« 🥇 1er », « 🥈 2ème »… comme dans la version d'origine."""
    if rang is None:
        return "—"
    if podium and rang <= 3:
        return ("🥇 1er", "🥈 2ème", "🥉 3ème")[rang - 1]
    return "1er" if rang == 1 else f"{rang}ème"


def fmt(valeur: float | None, decimales: int = 2) -> str:
    return "—" if valeur is None else f"{valeur:.{decimales}f}"
