"""Couche d'accès aux données : base SQLite locale `carnet_notes.db`.

Au premier lancement :
  * création du schéma ;
  * création du compte administrateur par défaut (admin / admin123) ;
  * pré-remplissage avec 3 matières et 4 étudiants de démonstration ;
  * import automatique de l'ancien fichier `carnet.json` s'il existe.
"""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import auth
import calculs

DOSSIER_APP = Path(__file__).resolve().parent
CHEMIN_DB = DOSSIER_APP / "carnet_notes.db"
# Emplacements possibles de l'ancienne sauvegarde JSON (version customtkinter)
ANCIENS_FICHIERS = (DOSSIER_APP / "carnet.json", DOSSIER_APP.parent / "carnet.json")
MATIERE_IMPORT = "Ancien carnet (import)"
ADMIN_DEFAUT = ("admin", "admin123")

MATIERES_DEMO = (("Python", 3), ("Statistiques", 2), ("Machine Learning", 3))
ETUDIANTS_DEMO = (
    # nom, prénom, notes (Python, Statistiques, ML), appréciation générale
    ("MARTIN", "Léa", (16.5, 14.0, 17.0), "Excellent semestre, travail rigoureux et autonome."),
    ("DIALLO", "Moussa", (12.0, 9.5, 11.0), "Résultats corrects, à consolider en statistiques."),
    ("NGUYEN", "Thomas", (8.5, 11.0, 9.0), "Des efforts sont attendus en programmation."),
    ("BERNARD", "Camille", (14.0, 15.5, 13.5), "Bon travail régulier, participation active."),
)

LONGUEUR_MAX_APPRECIATION = 2000

SCHEMA = """
CREATE TABLE IF NOT EXISTS utilisateurs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT    NOT NULL,
    role          TEXT    NOT NULL CHECK (role IN ('admin', 'enseignant', 'etudiant')),
    etudiant_id   INTEGER REFERENCES etudiants(id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_utilisateurs_etudiant
    ON utilisateurs(etudiant_id) WHERE etudiant_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS matieres (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    nom           TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    coefficient   REAL    NOT NULL CHECK (coefficient > 0),
    enseignant_id INTEGER REFERENCES utilisateurs(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS etudiants (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    nom          TEXT NOT NULL,
    prenom       TEXT NOT NULL DEFAULT '',
    appreciation TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS notes (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    etudiant_id       INTEGER NOT NULL REFERENCES etudiants(id) ON DELETE CASCADE,
    matiere_id        INTEGER NOT NULL REFERENCES matieres(id) ON DELETE CASCADE,
    valeur            REAL    NOT NULL CHECK (valeur BETWEEN 0 AND 20),
    appreciation      TEXT    NOT NULL DEFAULT '',
    date_modification TEXT    NOT NULL,
    UNIQUE (etudiant_id, matiere_id)
);

CREATE TABLE IF NOT EXISTS meta (
    cle    TEXT PRIMARY KEY,
    valeur TEXT
);
"""

_UPSERT_NOTE = """
INSERT INTO notes (etudiant_id, matiere_id, valeur, appreciation, date_modification)
VALUES (?, ?, ?, ?, ?)
ON CONFLICT (etudiant_id, matiere_id) DO UPDATE SET
    valeur = excluded.valeur,
    appreciation = excluded.appreciation,
    date_modification = excluded.date_modification
"""


def maintenant() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _cle_nom(texte: str) -> str:
    return " ".join(texte.split()).casefold()


class Database:
    """Point d'accès unique à la base de données."""

    def __init__(self, chemin=CHEMIN_DB, anciens_fichiers=ANCIENS_FICHIERS, demo=True):
        self.chemin = Path(chemin)
        self.messages: list[str] = []  # informations à afficher au démarrage
        self.conn = sqlite3.connect(self.chemin)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self._initialiser(anciens_fichiers, demo)

    def fermer(self):
        self.conn.close()

    # ------------------------------------------------------------ initialisation
    def _meta(self, cle):
        ligne = self.conn.execute("SELECT valeur FROM meta WHERE cle = ?", (cle,)).fetchone()
        return ligne["valeur"] if ligne else None

    def _set_meta(self, cle, valeur):
        with self.conn:
            self.conn.execute("INSERT OR REPLACE INTO meta (cle, valeur) VALUES (?, ?)", (cle, valeur))

    def _compter(self, table) -> int:
        return self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def _initialiser(self, anciens_fichiers, demo):
        if self._compter("utilisateurs") == 0:
            self.creer_utilisateur(*ADMIN_DEFAUT, role="admin")
            self.messages.append("Compte administrateur par défaut créé : admin / admin123.")

        if demo and self._meta("demo") is None:
            if self._compter("matieres") == 0 and self._compter("etudiants") == 0:
                self._creer_demo()
                self.messages.append("Base pré-remplie : 3 matières et 4 étudiants de démonstration.")
            self._set_meta("demo", maintenant())

        if self._meta("import_json") is None:
            for fichier in anciens_fichiers:
                fichier = Path(fichier)
                if not fichier.is_file():
                    continue
                try:
                    importes, ignores = self.importer_json(fichier)
                    texte = f"Ancien carnet importé ({fichier.name}) : {importes} note(s)"
                    if ignores:
                        texte += f", {ignores} entrée(s) invalide(s) ignorée(s)"
                    self.messages.append(texte + f" dans la matière « {MATIERE_IMPORT} ».")
                except (OSError, ValueError) as erreur:
                    self.messages.append(f"Import de {fichier.name} impossible : {erreur}")
                self._set_meta("import_json", f"{fichier} | {maintenant()}")
                break

    def _creer_demo(self):
        date = maintenant()
        with self.conn:
            ids_matieres = [
                self.conn.execute("INSERT INTO matieres (nom, coefficient) VALUES (?, ?)", m).lastrowid
                for m in MATIERES_DEMO
            ]
            for nom, prenom, notes, appreciation in ETUDIANTS_DEMO:
                eid = self.conn.execute(
                    "INSERT INTO etudiants (nom, prenom, appreciation) VALUES (?, ?, ?)",
                    (nom, prenom, appreciation)).lastrowid
                for mid, valeur in zip(ids_matieres, notes):
                    self.conn.execute(_UPSERT_NOTE, (eid, mid, valeur, "", date))

    def importer_json(self, chemin) -> tuple[int, int]:
        """Importe un fichier [{"nom": "...", "note": 12.5}, ...] de l'ancienne version.

        « Dupont Jean » devient nom = DUPONT… prénom = Jean ; la note est rangée dans une
        matière dédiée (coefficient 1) que l'administrateur peut ensuite renommer.
        """
        with open(chemin, encoding="utf-8") as f:
            donnees = json.load(f)
        if not isinstance(donnees, list):
            raise ValueError("le fichier doit contenir une liste d'étudiants.")

        importes = ignores = 0
        date = maintenant()
        index = {(_cle_nom(e["nom"]), _cle_nom(e["prenom"])): e["id"] for e in self.lister_etudiants()}
        with self.conn:
            ligne = self.conn.execute("SELECT id FROM matieres WHERE nom = ?", (MATIERE_IMPORT,)).fetchone()
            mid = ligne["id"] if ligne else self.conn.execute(
                "INSERT INTO matieres (nom, coefficient) VALUES (?, 1)", (MATIERE_IMPORT,)).lastrowid
            for item in donnees:
                try:
                    nom_complet = " ".join(str(item["nom"]).split())
                    if not nom_complet or isinstance(item["note"], bool):
                        raise ValueError
                    valeur = calculs.valider_note(str(item["note"]))
                except (KeyError, TypeError, ValueError):
                    ignores += 1
                    continue
                nom, _, prenom = nom_complet.partition(" ")
                cle = (_cle_nom(nom), _cle_nom(prenom))
                if cle not in index:
                    index[cle] = self.conn.execute(
                        "INSERT INTO etudiants (nom, prenom) VALUES (?, ?)", (nom, prenom)).lastrowid
                self.conn.execute(_UPSERT_NOTE, (index[cle], mid, valeur, "", date))
                importes += 1
        return importes, ignores

    # -------------------------------------------------------------- utilisateurs
    def authentifier(self, username: str, mot_de_passe: str):
        ligne = self.conn.execute(
            "SELECT id, password_hash FROM utilisateurs WHERE username = ?", (username.strip(),)).fetchone()
        if ligne is None:
            auth.verifier_mot_de_passe(mot_de_passe, auth.empreinte_leurre())
            return None
        if not auth.verifier_mot_de_passe(mot_de_passe, ligne["password_hash"]):
            return None
        return self.charger_utilisateur(ligne["id"])

    def charger_utilisateur(self, uid: int):
        ligne = self.conn.execute(
            "SELECT id, username, role, etudiant_id FROM utilisateurs WHERE id = ?", (uid,)).fetchone()
        if ligne is None:
            return None
        matieres = frozenset(r[0] for r in self.conn.execute(
            "SELECT id FROM matieres WHERE enseignant_id = ?", (uid,)))
        return auth.Utilisateur(ligne["id"], ligne["username"], ligne["role"],
                                ligne["etudiant_id"], matieres)

    def mot_de_passe_par_defaut_actif(self) -> bool:
        ligne = self.conn.execute(
            "SELECT password_hash FROM utilisateurs WHERE username = ? AND role = 'admin'",
            (ADMIN_DEFAUT[0],)).fetchone()
        return bool(ligne) and auth.verifier_mot_de_passe(ADMIN_DEFAUT[1], ligne["password_hash"])

    def lister_utilisateurs(self, role: str | None = None) -> list[dict]:
        requete = """
            SELECT u.id, u.username, u.role, u.etudiant_id, e.nom, e.prenom,
                   (SELECT GROUP_CONCAT(m.nom, ', ') FROM matieres m WHERE m.enseignant_id = u.id) AS matieres
            FROM utilisateurs u LEFT JOIN etudiants e ON e.id = u.etudiant_id
        """
        parametres = ()
        if role:
            requete += " WHERE u.role = ?"
            parametres = (role,)
        requete += """ ORDER BY CASE u.role WHEN 'admin' THEN 0 WHEN 'enseignant' THEN 1 ELSE 2 END,
                       u.username COLLATE NOCASE"""
        return [dict(r) for r in self.conn.execute(requete, parametres)]

    def creer_utilisateur(self, username, mot_de_passe, role, etudiant_id=None, matieres=()) -> int:
        username = auth.valider_identifiant(username)
        auth.valider_mot_de_passe(mot_de_passe, username)
        if role not in auth.ROLES:
            raise ValueError(f"Rôle inconnu : {role}")
        if role == "etudiant" and etudiant_id is None:
            raise ValueError("Un compte étudiant doit être rattaché à un étudiant.")
        if role != "etudiant":
            etudiant_id = None
        try:
            with self.conn:
                uid = self.conn.execute(
                    "INSERT INTO utilisateurs (username, password_hash, role, etudiant_id) VALUES (?, ?, ?, ?)",
                    (username, auth.hacher_mot_de_passe(mot_de_passe), role, etudiant_id)).lastrowid
                if role == "enseignant":
                    for mid in matieres:
                        self.conn.execute("UPDATE matieres SET enseignant_id = ? WHERE id = ?", (uid, mid))
        except sqlite3.IntegrityError as erreur:
            if "etudiant_id" in str(erreur):
                raise ValueError("Cet étudiant possède déjà un compte.") from None
            raise ValueError(f"L'identifiant « {username} » est déjà utilisé.") from None
        return uid

    def changer_mot_de_passe(self, uid: int, mot_de_passe: str):
        ligne = self.conn.execute("SELECT username FROM utilisateurs WHERE id = ?", (uid,)).fetchone()
        if ligne is None:
            raise ValueError("Utilisateur introuvable.")
        auth.valider_mot_de_passe(mot_de_passe, ligne["username"])
        with self.conn:
            self.conn.execute("UPDATE utilisateurs SET password_hash = ? WHERE id = ?",
                              (auth.hacher_mot_de_passe(mot_de_passe), uid))

    def nombre_admins(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM utilisateurs WHERE role = 'admin'").fetchone()[0]

    def supprimer_utilisateur(self, uid: int):
        with self.conn:
            self.conn.execute("DELETE FROM utilisateurs WHERE id = ?", (uid,))

    def attribuer_matieres(self, uid: int, matieres):
        with self.conn:
            self.conn.execute("UPDATE matieres SET enseignant_id = NULL WHERE enseignant_id = ?", (uid,))
            for mid in matieres:
                self.conn.execute("UPDATE matieres SET enseignant_id = ? WHERE id = ?", (uid, mid))

    # ------------------------------------------------------------------ matières
    def lister_matieres(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute("""
            SELECT m.id, m.nom, m.coefficient, m.enseignant_id, u.username AS enseignant,
                   (SELECT COUNT(*) FROM notes n WHERE n.matiere_id = m.id) AS nb_notes
            FROM matieres m LEFT JOIN utilisateurs u ON u.id = m.enseignant_id
            ORDER BY m.nom COLLATE NOCASE""")]

    @staticmethod
    def _valider_nom_matiere(nom: str) -> str:
        nom = " ".join(nom.split())
        if not nom:
            raise ValueError("Le nom de la matière est obligatoire.")
        if len(nom) > 60:
            raise ValueError("Le nom de la matière ne doit pas dépasser 60 caractères.")
        return nom

    def ajouter_matiere(self, nom, coefficient, enseignant_id=None) -> int:
        nom = self._valider_nom_matiere(nom)
        try:
            with self.conn:
                return self.conn.execute(
                    "INSERT INTO matieres (nom, coefficient, enseignant_id) VALUES (?, ?, ?)",
                    (nom, coefficient, enseignant_id)).lastrowid
        except sqlite3.IntegrityError:
            raise ValueError(f"Une matière nommée « {nom} » existe déjà.") from None

    def modifier_matiere(self, mid, nom, coefficient, enseignant_id=None):
        nom = self._valider_nom_matiere(nom)
        try:
            with self.conn:
                self.conn.execute(
                    "UPDATE matieres SET nom = ?, coefficient = ?, enseignant_id = ? WHERE id = ?",
                    (nom, coefficient, enseignant_id, mid))
        except sqlite3.IntegrityError:
            raise ValueError(f"Une matière nommée « {nom} » existe déjà.") from None

    def supprimer_matiere(self, mid):
        with self.conn:
            self.conn.execute("DELETE FROM matieres WHERE id = ?", (mid,))

    # ----------------------------------------------------------------- étudiants
    def lister_etudiants(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute(
            "SELECT id, nom, prenom, appreciation FROM etudiants "
            "ORDER BY nom COLLATE NOCASE, prenom COLLATE NOCASE")]

    def get_etudiant(self, eid):
        ligne = self.conn.execute(
            "SELECT id, nom, prenom, appreciation FROM etudiants WHERE id = ?", (eid,)).fetchone()
        return dict(ligne) if ligne else None

    def trouver_etudiant(self, nom, prenom):
        """Recherche insensible à la casse et aux espaces multiples."""
        cle = (_cle_nom(nom), _cle_nom(prenom))
        for e in self.lister_etudiants():
            if (_cle_nom(e["nom"]), _cle_nom(e["prenom"])) == cle:
                return e
        return None

    def ajouter_etudiant(self, nom, prenom="") -> int:
        nom, prenom = " ".join(nom.split()), " ".join(prenom.split())
        if not nom:
            raise ValueError("Le nom est obligatoire.")
        with self.conn:
            return self.conn.execute(
                "INSERT INTO etudiants (nom, prenom) VALUES (?, ?)", (nom, prenom)).lastrowid

    def supprimer_etudiant(self, eid):
        with self.conn:
            self.conn.execute("DELETE FROM etudiants WHERE id = ?", (eid,))

    def etudiants_sans_compte(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute("""
            SELECT id, nom, prenom FROM etudiants
            WHERE id NOT IN (SELECT etudiant_id FROM utilisateurs WHERE etudiant_id IS NOT NULL)
            ORDER BY nom COLLATE NOCASE, prenom COLLATE NOCASE""")]

    # --------------------------------------------------------------------- notes
    def notes_etudiant(self, eid) -> dict[int, dict]:
        return {r["matiere_id"]: dict(r) for r in self.conn.execute(
            "SELECT matiere_id, valeur, appreciation, date_modification FROM notes WHERE etudiant_id = ?",
            (eid,))}

    def definir_note(self, eid, mid, valeur, appreciation=None):
        if not calculs.NOTE_MIN <= valeur <= calculs.NOTE_MAX:
            raise ValueError("La note doit être comprise entre 0 et 20.")
        if appreciation is None:
            ancienne = self.notes_etudiant(eid).get(mid)
            appreciation = ancienne["appreciation"] if ancienne else ""
        with self.conn:
            self.conn.execute(_UPSERT_NOTE, (eid, mid, valeur, appreciation, maintenant()))

    def enregistrer_fiche(self, utilisateur, eid, nom, prenom, appreciation, notes):
        """Enregistre la fiche d'un étudiant en une seule transaction.

        `notes` : {matiere_id: None (suppression) | (valeur, appreciation)}.
        Les droits sont revérifiés ici : un enseignant ne touche qu'à ses matières.
        """
        nom, prenom = " ".join(nom.split()), " ".join(prenom.split())
        if not nom:
            raise ValueError("Le nom est obligatoire.")
        if len(appreciation or "") > LONGUEUR_MAX_APPRECIATION:
            raise ValueError(f"L'appréciation ne doit pas dépasser {LONGUEUR_MAX_APPRECIATION} caractères.")
        existantes = self.notes_etudiant(eid)
        date = maintenant()
        with self.conn:
            if utilisateur.peut_modifier_identite:
                self.conn.execute("UPDATE etudiants SET nom = ?, prenom = ?, appreciation = ? WHERE id = ?",
                                  (nom, prenom, appreciation or "", eid))
            for mid, contenu in notes.items():
                if not utilisateur.peut_noter(mid):
                    continue
                ancienne = existantes.get(mid)
                if contenu is None:
                    if ancienne:
                        self.conn.execute("DELETE FROM notes WHERE etudiant_id = ? AND matiere_id = ?",
                                          (eid, mid))
                    continue
                valeur, app = contenu
                if not calculs.NOTE_MIN <= valeur <= calculs.NOTE_MAX:
                    raise ValueError("La note doit être comprise entre 0 et 20.")
                if ancienne and ancienne["valeur"] == valeur and ancienne["appreciation"] == app:
                    continue  # inchangée : on conserve la date de modification
                self.conn.execute(_UPSERT_NOTE, (eid, mid, valeur, app, date))

    # ------------------------------------------------------------------ synthèse
    def tableau_promotion(self) -> list[dict]:
        """Tous les étudiants avec leurs notes, moyenne pondérée et rang général."""
        coefs = {m["id"]: m["coefficient"] for m in self.lister_matieres()}
        notes = defaultdict(dict)
        for r in self.conn.execute("SELECT etudiant_id, matiere_id, valeur FROM notes"):
            notes[r["etudiant_id"]][r["matiere_id"]] = r["valeur"]
        lignes = []
        for e in self.lister_etudiants():
            n = notes.get(e["id"], {})
            lignes.append({**e, "notes": n, "moyenne": calculs.moyenne_ponderee(n, coefs)})
        rangs = calculs.classer({l["id"]: l["moyenne"] for l in lignes})
        for l in lignes:
            l["rang"] = rangs.get(l["id"])
        return lignes
