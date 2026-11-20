"""Authentification (hachage salé SHA-256) et règles de droits par rôle.

Les mots de passe sont hachés avec PBKDF2-HMAC-SHA256 (hashlib) et un sel
aléatoire de 16 octets (secrets). Format stocké :
    pbkdf2_sha256$<itérations>$<sel hex>$<empreinte hex>
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass, field
from functools import lru_cache

ALGO = "pbkdf2_sha256"
ITERATIONS = 120_000

ROLES = {"admin": "Administrateur", "enseignant": "Enseignant", "etudiant": "Étudiant"}

_RE_IDENTIFIANT = re.compile(r"^[A-Za-z0-9_.-]{3,30}$")


def hacher_mot_de_passe(mot_de_passe: str, sel: str | None = None,
                        iterations: int = ITERATIONS) -> str:
    sel = sel or secrets.token_hex(16)
    empreinte = hashlib.pbkdf2_hmac("sha256", mot_de_passe.encode("utf-8"),
                                    bytes.fromhex(sel), iterations).hex()
    return f"{ALGO}${iterations}${sel}${empreinte}"


def verifier_mot_de_passe(mot_de_passe: str, stocke: str) -> bool:
    try:
        algo, iterations, sel, empreinte = stocke.split("$")
        iterations = int(iterations)
    except (ValueError, AttributeError):
        return False
    if algo != ALGO:
        return False
    calcule = hacher_mot_de_passe(mot_de_passe, sel, iterations).split("$")[3]
    return hmac.compare_digest(calcule, empreinte)  # comparaison à temps constant


@lru_cache(maxsize=1)
def empreinte_leurre() -> str:
    """Empreinte factice : on hache même si l'identifiant n'existe pas (temps de réponse constant)."""
    return hacher_mot_de_passe(secrets.token_hex(8))


def valider_identifiant(identifiant: str) -> str:
    identifiant = identifiant.strip()
    if not _RE_IDENTIFIANT.match(identifiant):
        raise ValueError("L'identifiant doit contenir 3 à 30 caractères "
                         "(lettres sans accent, chiffres, « . », « _ » ou « - »).")
    return identifiant


def valider_mot_de_passe(mot_de_passe: str, identifiant: str = "") -> None:
    if len(mot_de_passe) < 6:
        raise ValueError("Le mot de passe doit contenir au moins 6 caractères.")
    if identifiant and mot_de_passe.lower() == identifiant.lower():
        raise ValueError("Le mot de passe doit être différent de l'identifiant.")


@dataclass(frozen=True)
class Utilisateur:
    """Utilisateur connecté et ses droits."""

    id: int
    username: str
    role: str
    etudiant_id: int | None = None
    matieres: frozenset = field(default_factory=frozenset)  # matières dont l'enseignant est responsable

    @property
    def libelle_role(self) -> str:
        return ROLES.get(self.role, self.role)

    @property
    def est_admin(self) -> bool:
        return self.role == "admin"

    @property
    def est_enseignant(self) -> bool:
        return self.role == "enseignant"

    @property
    def est_etudiant(self) -> bool:
        return self.role == "etudiant"

    # --- droits
    @property
    def peut_gerer_utilisateurs(self) -> bool:
        return self.est_admin

    @property
    def peut_gerer_matieres(self) -> bool:
        return self.est_admin

    @property
    def peut_ajouter_etudiant(self) -> bool:
        return self.est_admin or self.est_enseignant

    @property
    def peut_supprimer_etudiant(self) -> bool:
        return self.est_admin

    @property
    def peut_modifier_identite(self) -> bool:
        """Nom, prénom et appréciation générale."""
        return self.est_admin or self.est_enseignant

    @property
    def peut_voir_statistiques(self) -> bool:
        return not self.est_etudiant

    @property
    def peut_exporter_promotion(self) -> bool:
        return not self.est_etudiant

    def peut_noter(self, matiere_id: int) -> bool:
        """Un enseignant ne modifie que les notes de ses propres matières."""
        return self.est_admin or (self.est_enseignant and matiere_id in self.matieres)

    def peut_voir_etudiant(self, etudiant_id: int) -> bool:
        return not self.est_etudiant or etudiant_id == self.etudiant_id
