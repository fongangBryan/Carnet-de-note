"""Script de vérification : syntaxe, imports, logique métier et ouverture de toutes les fenêtres.

Utilise une base temporaire : la vraie base `carnet_notes.db` n'est pas modifiée.
Lancement :  python verification.py
"""

import json
import py_compile
import sys
import tempfile
import tkinter as tk
from pathlib import Path

DOSSIER = Path(__file__).resolve().parent
sys.path.insert(0, str(DOSSIER))
MODULES = ["theme", "calculs", "auth", "database", "export", "login_window",
           "ui_dialogs", "ui_stats", "ui_main", "main"]
resultats = []


def verifier(libelle, condition):
    resultats.append((libelle, bool(condition)))
    print(("  OK   " if condition else "  ÉCHEC ") + libelle)


def leve(fonction, *args):
    try:
        fonction(*args)
    except ValueError:
        return True
    return False


print("1. Syntaxe et imports")
for nom in MODULES:
    py_compile.compile(str(DOSSIER / f"{nom}.py"), doraise=True)
    __import__(nom)
verifier(f"{len(MODULES)} modules compilés et importés", True)

import auth, calculs, export  # noqa: E402
from database import Database  # noqa: E402

print("2. Validation des saisies")
verifier("« 12,5 » -> 12.5", calculs.valider_note("12,5") == 12.5)
verifier("« 12.5 » -> 12.5", calculs.valider_note(" 12.5 ") == 12.5)
verifier("« 20 » et « 0 » acceptés", calculs.valider_note("20") == 20 and calculs.valider_note("0") == 0)
for mauvaise in ("21", "-1", "abc", "", "1_0", "12,5,3", "nan", "1e1"):
    verifier(f"note « {mauvaise} » refusée", leve(calculs.valider_note, mauvaise))
verifier("coefficient 0 refusé", leve(calculs.valider_coefficient, "0"))
verifier("coefficient « 1,5 » accepté", calculs.valider_coefficient("1,5") == 1.5)

print("3. Calculs")
verifier("moyenne pondérée", abs(calculs.moyenne_ponderee({1: 10, 2: 16}, {1: 1, 2: 2}) - 14) < 1e-9)
verifier("rangs ex aequo (1, 2, 2, 4)", calculs.classer({1: 15, 2: 12, 3: 12, 4: 8}) == {1: 1, 2: 2, 3: 2, 4: 4})
ind = calculs.indicateurs([8, 12, 14, 16])
verifier("indicateurs (médiane 13, réussite 75 %)", ind["mediane"] == 13 and ind["taux_reussite"] == 75)
verifier("tranches", [calculs.tranche(v) for v in (0, 9.99, 10, 12, 14, 16, 20)] == [0, 0, 1, 2, 3, 4, 4])

print("4. Authentification")
h = auth.hacher_mot_de_passe("secret1")
verifier("hachage salé (deux empreintes différentes)", h != auth.hacher_mot_de_passe("secret1"))
verifier("vérification correcte / incorrecte",
         auth.verifier_mot_de_passe("secret1", h) and not auth.verifier_mot_de_passe("secret2", h))

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    ancien = tmp / "carnet.json"
    ancien.write_text(json.dumps([{"nom": "POL", "note": 15.5}, {"nom": "Dupont Jean", "note": "13,5"},
                                  {"nom": "X", "note": 42}]), encoding="utf-8")
    db = Database(tmp / "test.db", anciens_fichiers=[ancien])

    print("5. Base de données & migration")
    verifier("4 étudiants démo + 2 importés", len(db.lister_etudiants()) == 6)
    noms = {m["nom"] for m in db.lister_matieres()}
    verifier("3 matières démo + matière d'import",
             {"Python", "Statistiques", "Machine Learning"} <= noms and len(noms) == 4)
    verifier("entrée JSON invalide ignorée (note 42)", db.trouver_etudiant("X", "") is None)
    verifier("« Dupont Jean » -> nom DUPONT / prénom Jean", db.trouver_etudiant("dupont", "JEAN") is not None)
    verifier("import marqué comme effectué (pas de doublon au redémarrage)",
             len(Database(tmp / "test.db", anciens_fichiers=[ancien]).lister_etudiants()) == 6)
    admin = db.authentifier("admin", "admin123")
    verifier("connexion admin/admin123", admin is not None and admin.est_admin)
    verifier("mauvais mot de passe refusé", db.authentifier("admin", "faux") is None)
    verifier("utilisateur inconnu refusé", db.authentifier("personne", "admin123") is None)

    promo = {f"{l['prenom']} {l['nom']}": l for l in db.tableau_promotion()}
    lea = promo["Léa MARTIN"]
    attendu = (16.5 * 3 + 14 * 2 + 17 * 3) / 8
    verifier(f"moyenne pondérée de Léa = {attendu:.3f}", abs(lea["moyenne"] - attendu) < 1e-9)
    verifier("Léa classée 1ère", lea["rang"] == 1)

    ids = {m["nom"]: m["id"] for m in db.lister_matieres()}
    db.modifier_matiere(ids["Statistiques"], "Statistiques", 10)
    nouvelle = next(l for l in db.tableau_promotion() if l["id"] == lea["id"])["moyenne"]
    verifier("changement de coefficient pris en compte",
             abs(nouvelle - (16.5 * 3 + 14 * 10 + 17 * 3) / 16) < 1e-9)
    db.modifier_matiere(ids["Statistiques"], "Statistiques", 2)
    verifier("doublon de matière refusé", leve(db.ajouter_matiere, "python", 1))

    print("6. Rôles et droits")
    uid = db.creer_utilisateur("prof.python", "motdepasse", "enseignant", matieres=[ids["Python"]])
    prof = db.authentifier("prof.python", "motdepasse")
    verifier("enseignant : peut noter sa matière", prof.peut_noter(ids["Python"]))
    verifier("enseignant : ne peut pas noter les autres", not prof.peut_noter(ids["Statistiques"]))
    verifier("enseignant : pas d'accès à la gestion des utilisateurs", not prof.peut_gerer_utilisateurs)
    eid = lea["id"]
    avant = db.notes_etudiant(eid)
    db.enregistrer_fiche(prof, eid, "MARTIN", "Léa", "ok", {ids["Python"]: (18.0, "Très bien"),
                                                             ids["Statistiques"]: (0.0, "piratage")})
    apres = db.notes_etudiant(eid)
    verifier("enregistrer_fiche : note de sa matière modifiée", apres[ids["Python"]]["valeur"] == 18)
    verifier("enregistrer_fiche : autre matière protégée",
             apres[ids["Statistiques"]]["valeur"] == avant[ids["Statistiques"]]["valeur"])
    db.creer_utilisateur("lea", "etudiante", "etudiant", etudiant_id=eid)
    lea_u = db.authentifier("lea", "etudiante")
    verifier("étudiant : lecture seule", not lea_u.peut_noter(ids["Python"]) and not lea_u.peut_modifier_identite)
    verifier("étudiant : ne voit que sa fiche",
             lea_u.peut_voir_etudiant(eid) and not lea_u.peut_voir_etudiant(eid + 1))
    verifier("deuxième compte pour le même étudiant refusé",
             leve(db.creer_utilisateur, "lea2", "etudiante", "etudiant", eid))
    verifier("identifiant en double refusé", leve(db.creer_utilisateur, "ADMIN", "xxxxxx", "admin"))
    verifier("mot de passe trop court refusé", leve(db.creer_utilisateur, "court", "123", "admin"))
    db.supprimer_utilisateur(uid)
    verifier("suppression enseignant -> matière sans responsable",
             next(m for m in db.lister_matieres() if m["id"] == ids["Python"])["enseignant_id"] is None)

    print("7. Exports")
    csv_chemin = tmp / "promo.csv"
    n = export.exporter_csv(db, csv_chemin)
    contenu = csv_chemin.read_text(encoding="utf-8-sig")
    verifier(f"CSV : {n} lignes, séparateur ;", n == 6 and contenu.splitlines()[0].startswith("Rang;Nom;Prénom"))
    page = export.generer_releve_html(db, eid, dossier=tmp)
    verifier("relevé HTML généré", page.exists() and "Relevé de notes" in page.read_text(encoding="utf-8"))

    print("8. Interface (ouverture de chaque fenêtre)")
    import theme
    from login_window import LoginWindow
    from ui_main import MainWindow
    from ui_dialogs import StudentDialog, MatieresDialog, UsersDialog, AttributionDialog
    from ui_stats import StatsWindow

    racine = tk.Tk()
    racine.geometry("1100x720+0+0")
    theme.appliquer_style(racine)
    LoginWindow(racine, db, lambda u: None).destroy()
    for compte in (admin, db.authentifier("lea", "etudiante")):
        fen = MainWindow(racine, db, compte, lambda: None)
        fen.pack(fill="both", expand=True)
        racine.update()
        fen.trier("nom")
        fen.trier("note")
        fen.var_recherche.set("ma")
        racine.update()
        verifier(f"fenêtre principale ({compte.libelle_role}) : {len(fen.tableau.get_children())} ligne(s)",
                 len(fen.tableau.get_children()) >= 1)
        fenetres = [(StudentDialog, (eid,))]
        if compte.est_admin:  # fenêtres non accessibles à un compte étudiant
            fenetres += [(MatieresDialog, ()), (StatsWindow, ()), (UsersDialog, ())]
        for classe, args in fenetres:
            d = classe(fen, db, compte, *args)
            racine.update()
            if classe is StatsWindow:
                d.var_mode.set(next(iter(d.libelles)))
                d.calculer()
                dessins = []
                for onglet, canvas in enumerate((d.canvas_hist, d.canvas_indiv)):
                    d.onglets.select(onglet)
                    racine.update()
                    d.dessiner()
                    dessins.append(len(canvas.find_all()))
                verifier(f"graphiques Canvas dessinés ({dessins[0]} et {dessins[1]} éléments)",
                         min(dessins) > 10)
            if classe is UsersDialog:
                prof2 = db.creer_utilisateur("prof2", "motdepasse", "enseignant")
                a = AttributionDialog(d, db, {"id": prof2, "username": "prof2"})
                racine.update()
                a.destroy()
            d.destroy()
            verifier(f"  {classe.__name__} ouverte et fermée", True)
        fen.destroy()
    racine.destroy()
    db.fermer()

echecs = [l for l, ok in resultats if not ok]
print(f"\n{len(resultats) - len(echecs)}/{len(resultats)} vérifications réussies.")
sys.exit(1 if echecs else 0)
