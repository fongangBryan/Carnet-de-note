"""Fenêtres secondaires (Toplevel) :
  * StudentDialog      — détails & édition d'un étudiant (double-clic) ;
  * MatieresDialog     — gestion des matières & coefficients ;
  * UsersDialog        — gestion des utilisateurs (réservée à l'administrateur) ;
  * AttributionDialog  — matières attribuées à un enseignant.
"""

from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import messagebox, simpledialog, ttk

import auth
import calculs
import export
import theme

AUCUN = "(aucun)"


def preparer_fenetre(fenetre, parent, titre):
    fenetre.title(titre)
    fenetre.configure(bg=theme.FOND)
    fenetre.transient(parent.winfo_toplevel())
    fenetre.bind("<Escape>", lambda e: fenetre.destroy())


def centrer_et_bloquer(fenetre, parent, modale=True):
    """Centre la fenêtre sur son parent et la rend modale (grab)."""
    fenetre.update_idletasks()
    p = parent.winfo_toplevel()
    x = p.winfo_rootx() + (p.winfo_width() - fenetre.winfo_reqwidth()) // 2
    y = p.winfo_rooty() + (p.winfo_height() - fenetre.winfo_reqheight()) // 2
    fenetre.geometry(f"+{max(x, 0)}+{max(y, 0)}")
    if modale:
        try:
            fenetre.grab_set()
        except tk.TclError:  # fenêtre pas encore visible
            pass
    fenetre.focus_set()


def ouvrir_releve(parent, db, etudiant_id):
    """Génère le relevé HTML et l'ouvre dans le navigateur."""
    try:
        chemin = export.generer_releve_html(db, etudiant_id)
    except (OSError, ValueError) as erreur:
        messagebox.showerror("Relevé de notes", f"Impossible de générer le relevé : {erreur}", parent=parent)
        return
    if not webbrowser.open(chemin.as_uri()):
        messagebox.showinfo("Relevé de notes", f"Relevé enregistré :\n{chemin}", parent=parent)


# ==================================================================== ÉTUDIANT
class StudentDialog(tk.Toplevel):
    """Fiche détaillée d'un étudiant : identité, notes par matière, appréciations, moyenne et rang."""

    def __init__(self, parent, db, utilisateur, etudiant_id, on_save=None):
        super().__init__(parent)
        self.db, self.utilisateur, self.eid, self.on_save = db, utilisateur, etudiant_id, on_save
        self.etudiant = db.get_etudiant(etudiant_id)
        self.matieres = db.lister_matieres()
        self.notes = db.notes_etudiant(etudiant_id)
        self.promotion = db.tableau_promotion()
        self.coefs = {m["id"]: m["coefficient"] for m in self.matieres}
        self.champs = {}  # matiere_id -> dict(var_note, var_app, entree, editable, libelle)

        preparer_fenetre(self, parent, f"Fiche étudiant — {self.etudiant['prenom']} {self.etudiant['nom']}")
        self.resizable(False, False)
        self._construire()
        self._maj_resultats()
        centrer_et_bloquer(self, parent)

    @property
    def peut_enregistrer(self):
        return self.utilisateur.peut_modifier_identite or any(c["editable"] for c in self.champs.values())

    def _construire(self):
        cadre = ttk.Frame(self, padding=16)
        cadre.pack(fill="both", expand=True)
        etat_identite = "normal" if self.utilisateur.peut_modifier_identite else "disabled"

        # --- Identité
        f_id = ttk.LabelFrame(cadre, text="Identité", padding=12)
        f_id.pack(fill="x")
        self.var_nom = tk.StringVar(value=self.etudiant["nom"])
        self.var_prenom = tk.StringVar(value=self.etudiant["prenom"])
        ttk.Label(f_id, text="Nom :", style="Carte.TLabel").grid(row=0, column=0, sticky="e", padx=(0, 6))
        self.champ_nom = ttk.Entry(f_id, textvariable=self.var_nom, width=28, state=etat_identite)
        self.champ_nom.grid(row=0, column=1, padx=(0, 20))
        ttk.Label(f_id, text="Prénom :", style="Carte.TLabel").grid(row=0, column=2, sticky="e", padx=(0, 6))
        ttk.Entry(f_id, textvariable=self.var_prenom, width=28, state=etat_identite).grid(row=0, column=3)
        ttk.Label(f_id, text=f"N° {self.eid:05d}", style="CarteSous.TLabel").grid(row=0, column=4, padx=(20, 0))

        # --- Notes par matière
        f_notes = ttk.LabelFrame(cadre, text="Notes par matière", padding=12)
        f_notes.pack(fill="x", pady=12)
        for col, titre in enumerate(("Matière", "Coef.", "Note /20", "Appréciation", "Modifiée le")):
            ttk.Label(f_notes, text=titre, style="CarteSous.TLabel").grid(row=0, column=col, sticky="w", padx=4)
        for i, m in enumerate(self.matieres, start=1):
            note = self.notes.get(m["id"])
            editable = self.utilisateur.peut_noter(m["id"])
            etat = "normal" if editable else "disabled"
            var_note = tk.StringVar(value=calculs.fmt(note["valeur"]) if note else "")
            var_app = tk.StringVar(value=note["appreciation"] if note else "")
            libelle = m["nom"] + ("" if editable or self.utilisateur.est_etudiant else "  🔒")
            ttk.Label(f_notes, text=libelle, style="Carte.TLabel").grid(row=i, column=0, sticky="w", padx=4, pady=3)
            ttk.Label(f_notes, text=f"{m['coefficient']:g}", style="Carte.TLabel").grid(row=i, column=1, padx=4)
            entree = ttk.Entry(f_notes, textvariable=var_note, width=8, justify="center", state=etat)
            entree.grid(row=i, column=2, padx=4)
            ttk.Entry(f_notes, textvariable=var_app, width=42, state=etat).grid(row=i, column=3, padx=4)
            date = note["date_modification"][:16] if note else "—"
            ttk.Label(f_notes, text=date, style="CarteSous.TLabel").grid(row=i, column=4, padx=4)
            var_note.trace_add("write", lambda *a: self._maj_resultats())
            self.champs[m["id"]] = dict(var_note=var_note, var_app=var_app, entree=entree,
                                        editable=editable, libelle=m["nom"])
        if not self.matieres:
            ttk.Label(f_notes, text="Aucune matière définie.", style="CarteSous.TLabel").grid(
                row=1, column=0, columnspan=5, sticky="w")
        if self.utilisateur.est_enseignant:
            ttk.Label(f_notes, text="🔒 : matière d'un autre enseignant (lecture seule).",
                      style="CarteSous.TLabel").grid(row=len(self.matieres) + 1, column=0,
                                                     columnspan=5, sticky="w", pady=(8, 0))

        # --- Appréciation générale
        f_app = ttk.LabelFrame(cadre, text="Appréciation pédagogique générale", padding=12)
        f_app.pack(fill="x")
        self.texte_app = tk.Text(f_app, height=4, width=90, wrap="word", font=(theme.POLICE, 10),
                                 relief="solid", bd=1, highlightthickness=0, padx=6, pady=4)
        self.texte_app.insert("1.0", self.etudiant["appreciation"])
        if not self.utilisateur.peut_modifier_identite:
            self.texte_app.configure(state="disabled", bg=theme.FOND)
        self.texte_app.pack(fill="x")

        # --- Résultats
        f_res = ttk.LabelFrame(cadre, text="Résultats", padding=12)
        f_res.pack(fill="x", pady=12)
        self.var_moyenne, self.var_rang, self.var_mention = tk.StringVar(), tk.StringVar(), tk.StringVar()
        for col, (titre, var) in enumerate((("Moyenne pondérée", self.var_moyenne),
                                            ("Rang dans la promotion", self.var_rang),
                                            ("Mention / décision", self.var_mention))):
            f_res.columnconfigure(col, weight=1)
            ttk.Label(f_res, text=titre, style="CarteSous.TLabel").grid(row=0, column=col)
            ttk.Label(f_res, textvariable=var, style="Grand.TLabel").grid(row=1, column=col)

        # --- Boutons
        f_btn = ttk.Frame(cadre)
        f_btn.pack(fill="x")
        ttk.Button(f_btn, text="Fermer", style="Neutre.TButton", command=self.destroy).pack(side="right")
        if self.peut_enregistrer:
            ttk.Button(f_btn, text="Enregistrer", style="Succes.TButton",
                       command=self.enregistrer).pack(side="right", padx=8)
            self.bind("<Control-s>", lambda e: self.enregistrer())
        ttk.Button(f_btn, text="📄 Relevé de notes (HTML)", style="Info.TButton",
                   command=lambda: ouvrir_releve(self, self.db, self.eid)).pack(side="left")

    def _notes_apercu(self):
        """Notes telles qu'actuellement saisies (les saisies invalides sont signalées et ignorées)."""
        apercu = {}
        for mid, c in self.champs.items():
            if not c["editable"]:
                if mid in self.notes:
                    apercu[mid] = self.notes[mid]["valeur"]
                continue
            texte = c["var_note"].get().strip()
            if not texte:
                c["entree"].configure(style="TEntry")
                continue
            try:
                apercu[mid] = calculs.valider_note(texte)
                c["entree"].configure(style="TEntry")
            except ValueError:
                c["entree"].configure(style="Invalide.TEntry")
        return apercu

    def _maj_resultats(self):
        moyenne = calculs.moyenne_ponderee(self._notes_apercu(), self.coefs)
        valeurs = {l["id"]: l["moyenne"] for l in self.promotion}
        valeurs[self.eid] = moyenne
        rangs = calculs.classer(valeurs)
        classes = sum(1 for v in valeurs.values() if v is not None)
        self.var_moyenne.set(f"{moyenne:.2f} /20" if moyenne is not None else "—")
        self.var_rang.set(f"{calculs.libelle_rang(rangs[self.eid])} / {classes}" if self.eid in rangs else "—")
        self.var_mention.set(calculs.mention(moyenne))  # « Ajourné » sous 10, sinon la mention

    def enregistrer(self):
        nom, prenom = self.var_nom.get().strip(), self.var_prenom.get().strip()
        if self.utilisateur.peut_modifier_identite:
            if not nom:
                messagebox.showerror("Saisie incomplète", "Le nom est obligatoire.", parent=self)
                self.champ_nom.focus_set()
                return
            homonyme = self.db.trouver_etudiant(nom, prenom)
            if homonyme and homonyme["id"] != self.eid:
                messagebox.showerror("Doublon", f"Un autre étudiant s'appelle déjà « {nom} {prenom} ».",
                                     parent=self)
                return

        modifications = {}
        for mid, c in self.champs.items():
            if not c["editable"]:
                continue
            texte, appreciation = c["var_note"].get().strip(), c["var_app"].get().strip()
            if len(appreciation) > 500:
                messagebox.showerror("Appréciation trop longue",
                                     f"L'appréciation de « {c['libelle']} » dépasse 500 caractères.", parent=self)
                return
            if not texte:
                if appreciation:
                    messagebox.showerror("Note manquante",
                                         f"Saisissez une note en « {c['libelle']} » avant de rédiger "
                                         "une appréciation pour cette matière.", parent=self)
                    c["entree"].focus_set()
                    return
                modifications[mid] = None
                continue
            try:
                valeur = calculs.valider_note(texte, f"La note de « {c['libelle']} »")
            except ValueError as erreur:
                messagebox.showerror("Note invalide", str(erreur), parent=self)
                c["entree"].focus_set()
                c["entree"].select_range(0, "end")
                return
            modifications[mid] = (valeur, appreciation)

        supprimees = [self.champs[m]["libelle"] for m, v in modifications.items() if v is None and m in self.notes]
        if supprimees and not messagebox.askyesno(
                "Suppression de notes", "Les notes suivantes ont été effacées et seront supprimées :\n• "
                + "\n• ".join(supprimees) + "\n\nContinuer ?", parent=self):
            return

        try:
            self.db.enregistrer_fiche(self.utilisateur, self.eid, nom, prenom,
                                      self.texte_app.get("1.0", "end").strip(), modifications)
        except ValueError as erreur:
            messagebox.showerror("Enregistrement impossible", str(erreur), parent=self)
            return
        if self.on_save:
            self.on_save()
        self.destroy()


# ==================================================================== MATIÈRES
class MatieresDialog(tk.Toplevel):
    """Ajout, modification et suppression des matières et de leurs coefficients."""

    def __init__(self, parent, db, utilisateur, on_change=None):
        super().__init__(parent)
        self.db, self.utilisateur, self.on_change = db, utilisateur, on_change
        self.admin = utilisateur.peut_gerer_matieres
        self.enseignants = {}
        preparer_fenetre(self, parent, "Gestion des matières & coefficients")
        self.minsize(640, 420)
        self._construire()
        self.charger()
        centrer_et_bloquer(self, parent)

    def _construire(self):
        cadre = ttk.Frame(self, padding=16)
        cadre.pack(fill="both", expand=True)

        f_liste = ttk.LabelFrame(cadre, text="Matières", padding=10)
        f_liste.pack(fill="both", expand=True)
        colonnes = ("nom", "coef", "enseignant", "notes")
        self.tableau = ttk.Treeview(f_liste, columns=colonnes, show="headings", height=8, selectmode="browse")
        for col, titre, largeur, ancre in (("nom", "Matière", 240, "w"), ("coef", "Coefficient", 100, "center"),
                                           ("enseignant", "Enseignant responsable", 180, "center"),
                                           ("notes", "Notes saisies", 110, "center")):
            self.tableau.heading(col, text=titre, anchor=ancre)
            self.tableau.column(col, width=largeur, anchor=ancre)
        self.tableau.pack(fill="both", expand=True)
        self.tableau.bind("<<TreeviewSelect>>", self._remplir_formulaire)
        self.var_total = tk.StringVar()
        ttk.Label(f_liste, textvariable=self.var_total, style="CarteSous.TLabel").pack(anchor="w", pady=(6, 0))

        if not self.admin:
            ttk.Label(cadre, text="Lecture seule : seul l'administrateur peut modifier les matières.",
                      style="Sous.TLabel").pack(anchor="w", pady=(10, 0))
            ttk.Button(cadre, text="Fermer", style="Neutre.TButton", command=self.destroy).pack(anchor="e")
            return

        f_form = ttk.LabelFrame(cadre, text="Matière sélectionnée / nouvelle matière", padding=10)
        f_form.pack(fill="x", pady=(12, 0))
        self.var_nom, self.var_coef, self.var_ens = tk.StringVar(), tk.StringVar(value="1"), tk.StringVar(value=AUCUN)
        ttk.Label(f_form, text="Nom :", style="Carte.TLabel").grid(row=0, column=0, sticky="e")
        self.champ_nom = ttk.Entry(f_form, textvariable=self.var_nom, width=26)
        self.champ_nom.grid(row=0, column=1, padx=6)
        ttk.Label(f_form, text="Coefficient :", style="Carte.TLabel").grid(row=0, column=2, sticky="e")
        self.champ_coef = ttk.Entry(f_form, textvariable=self.var_coef, width=6, justify="center")
        self.champ_coef.grid(row=0, column=3, padx=6)
        ttk.Label(f_form, text="Enseignant :", style="Carte.TLabel").grid(row=0, column=4, sticky="e")
        self.combo_ens = ttk.Combobox(f_form, textvariable=self.var_ens, state="readonly", width=16)
        self.combo_ens.grid(row=0, column=5, padx=6)

        f_btn = ttk.Frame(f_form, style="Carte.TFrame")
        f_btn.grid(row=1, column=0, columnspan=6, sticky="we", pady=(12, 0))
        ttk.Button(f_btn, text="Ajouter", style="Succes.TButton", command=self.ajouter).pack(side="left")
        ttk.Button(f_btn, text="Modifier", style="Info.TButton", command=self.modifier).pack(side="left", padx=8)
        ttk.Button(f_btn, text="Supprimer", style="Danger.TButton", command=self.supprimer).pack(side="left")
        ttk.Button(f_btn, text="Nouveau", style="Neutre.TButton", command=self._vider).pack(side="left", padx=8)
        ttk.Button(f_btn, text="Fermer", style="Neutre.TButton", command=self.destroy).pack(side="right")
        self.champ_coef.bind("<Return>", lambda e: self.ajouter() if not self.tableau.selection() else self.modifier())

    def charger(self):
        self.matieres = {m["id"]: m for m in self.db.lister_matieres()}
        self.tableau.delete(*self.tableau.get_children())
        for m in self.matieres.values():
            self.tableau.insert("", "end", iid=str(m["id"]),
                                values=(m["nom"], f"{m['coefficient']:g}", m["enseignant"] or "—", m["nb_notes"]))
        total = sum(m["coefficient"] for m in self.matieres.values())
        self.var_total.set(f"{len(self.matieres)} matière(s) — somme des coefficients : {total:g}")
        if self.admin:
            self.enseignants = {u["username"]: u["id"] for u in self.db.lister_utilisateurs("enseignant")}
            self.combo_ens["values"] = [AUCUN, *self.enseignants]

    def _selection(self):
        sel = self.tableau.selection()
        return int(sel[0]) if sel else None

    def _remplir_formulaire(self, _event=None):
        mid = self._selection()
        if not self.admin or mid is None:
            return
        m = self.matieres[mid]
        self.var_nom.set(m["nom"])
        self.var_coef.set(f"{m['coefficient']:g}")
        self.var_ens.set(m["enseignant"] or AUCUN)

    def _vider(self):
        self.tableau.selection_remove(*self.tableau.selection())
        self.var_nom.set("")
        self.var_coef.set("1")
        self.var_ens.set(AUCUN)
        self.champ_nom.focus_set()

    def _lire_formulaire(self):
        if not self.var_nom.get().strip():
            messagebox.showerror("Saisie incomplète", "Le nom de la matière est obligatoire.", parent=self)
            self.champ_nom.focus_set()
            return None
        try:
            coef = calculs.valider_coefficient(self.var_coef.get())
        except ValueError as erreur:
            messagebox.showerror("Coefficient invalide", str(erreur), parent=self)
            self.champ_coef.focus_set()
            return None
        return self.var_nom.get(), coef, self.enseignants.get(self.var_ens.get())

    def _apres_modification(self, mid=None):
        self.charger()
        if mid is not None and self.tableau.exists(str(mid)):
            self.tableau.selection_set(str(mid))
        if self.on_change:
            self.on_change()  # recalcul immédiat des moyennes dans la fenêtre principale

    def ajouter(self):
        donnees = self._lire_formulaire()
        if donnees is None:
            return
        try:
            mid = self.db.ajouter_matiere(*donnees)
        except ValueError as erreur:
            messagebox.showerror("Ajout impossible", str(erreur), parent=self)
            return
        self._apres_modification(mid)

    def modifier(self):
        mid = self._selection()
        if mid is None:
            messagebox.showinfo("Modification", "Sélectionnez d'abord une matière dans la liste.", parent=self)
            return
        donnees = self._lire_formulaire()
        if donnees is None:
            return
        try:
            self.db.modifier_matiere(mid, *donnees)
        except ValueError as erreur:
            messagebox.showerror("Modification impossible", str(erreur), parent=self)
            return
        self._apres_modification(mid)

    def supprimer(self):
        mid = self._selection()
        if mid is None:
            messagebox.showinfo("Suppression", "Sélectionnez d'abord une matière dans la liste.", parent=self)
            return
        m = self.matieres[mid]
        message = f"Supprimer la matière « {m['nom']} » ?"
        if m["nb_notes"]:
            message += f"\n\n⚠ {m['nb_notes']} note(s) associée(s) seront définitivement supprimées."
        if messagebox.askyesno("Confirmer la suppression", message, icon="warning", parent=self):
            self.db.supprimer_matiere(mid)
            self._vider()
            self._apres_modification()


# ================================================================ UTILISATEURS
class UsersDialog(tk.Toplevel):
    """Création / suppression des comptes (administrateurs, enseignants, étudiants)."""

    def __init__(self, parent, db, utilisateur, on_change=None):
        super().__init__(parent)
        if not utilisateur.peut_gerer_utilisateurs:
            self.destroy()
            raise PermissionError("Fenêtre réservée à l'administrateur.")
        self.db, self.utilisateur, self.on_change = db, utilisateur, on_change
        self.roles_par_libelle = {v: k for k, v in auth.ROLES.items()}
        preparer_fenetre(self, parent, "Gestion des utilisateurs")
        self.minsize(900, 460)
        self._construire()
        self.charger()
        centrer_et_bloquer(self, parent)

    def _construire(self):
        cadre = ttk.Frame(self, padding=16)
        cadre.pack(fill="both", expand=True)
        cadre.columnconfigure(0, weight=1)
        cadre.rowconfigure(0, weight=1)

        # --- Liste des comptes
        f_liste = ttk.LabelFrame(cadre, text="Comptes existants", padding=10)
        f_liste.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self.tableau = ttk.Treeview(f_liste, columns=("username", "role", "lien"), show="headings",
                                    height=10, selectmode="browse")
        for col, titre, largeur, ancre in (("username", "Identifiant", 130, "w"), ("role", "Rôle", 120, "center"),
                                           ("lien", "Rattachement / matières", 240, "w")):
            self.tableau.heading(col, text=titre, anchor=ancre)
            self.tableau.column(col, width=largeur, anchor=ancre)
        self.tableau.pack(fill="both", expand=True)
        f_actions = ttk.Frame(f_liste, style="Carte.TFrame")
        f_actions.pack(fill="x", pady=(10, 0))
        ttk.Button(f_actions, text="Supprimer le compte", style="Danger.TButton",
                   command=self.supprimer).pack(side="left")
        ttk.Button(f_actions, text="Nouveau mot de passe…", style="Neutre.TButton",
                   command=self.reinitialiser).pack(side="left", padx=8)
        ttk.Button(f_actions, text="Matières de l'enseignant…", style="Info.TButton",
                   command=self.attribuer).pack(side="left")

        # --- Formulaire de création
        f_form = ttk.LabelFrame(cadre, text="Créer un compte", padding=12)
        f_form.grid(row=0, column=1, sticky="ns")
        self.var_id, self.var_mdp, self.var_conf = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.var_role = tk.StringVar(value=auth.ROLES["enseignant"])
        self.var_etudiant = tk.StringVar()
        lignes = (("Identifiant", ttk.Entry(f_form, textvariable=self.var_id, width=28)),
                  ("Mot de passe (6 car. min.)", ttk.Entry(f_form, textvariable=self.var_mdp, show="•", width=28)),
                  ("Confirmation", ttk.Entry(f_form, textvariable=self.var_conf, show="•", width=28)),
                  ("Rôle", ttk.Combobox(f_form, textvariable=self.var_role, state="readonly", width=26,
                                        values=list(auth.ROLES.values()))))
        for i, (texte, widget) in enumerate(lignes):
            ttk.Label(f_form, text=texte, style="Carte.TLabel").grid(row=2 * i, column=0, sticky="w")
            widget.grid(row=2 * i + 1, column=0, sticky="we", pady=(0, 8))
        self.champ_id = lignes[0][1]
        lignes[3][1].bind("<<ComboboxSelected>>", lambda e: self._maj_options_role())

        # Options dépendant du rôle
        self.f_etudiant = ttk.Frame(f_form, style="Carte.TFrame")
        ttk.Label(self.f_etudiant, text="Étudiant rattaché (lecture seule de ses notes)",
                  style="Carte.TLabel").pack(anchor="w")
        self.combo_etudiant = ttk.Combobox(self.f_etudiant, textvariable=self.var_etudiant,
                                           state="readonly", width=26)
        self.combo_etudiant.pack(fill="x")

        self.f_enseignant = ttk.Frame(f_form, style="Carte.TFrame")
        ttk.Label(self.f_enseignant, text="Matières attribuées (Ctrl+clic : plusieurs)",
                  style="Carte.TLabel").pack(anchor="w")
        self.liste_matieres = tk.Listbox(self.f_enseignant, selectmode="extended", height=5,
                                         exportselection=False, relief="solid", bd=1,
                                         highlightthickness=0, font=(theme.POLICE, 10),
                                         selectbackground=theme.PRIMAIRE)
        self.liste_matieres.pack(fill="x")

        self.f_options_ligne = 8
        ttk.Button(f_form, text="Créer le compte", style="Succes.TButton",
                   command=self.creer).grid(row=10, column=0, sticky="we", pady=(12, 0))
        ttk.Button(f_form, text="Fermer", style="Neutre.TButton",
                   command=self.destroy).grid(row=11, column=0, sticky="we", pady=(8, 0))

    def _maj_options_role(self):
        role = self.roles_par_libelle.get(self.var_role.get())
        self.f_etudiant.grid_forget()
        self.f_enseignant.grid_forget()
        if role == "etudiant":
            self.f_etudiant.grid(row=self.f_options_ligne, column=0, sticky="we")
        elif role == "enseignant":
            self.f_enseignant.grid(row=self.f_options_ligne, column=0, sticky="we")

    def charger(self):
        self.comptes = {u["id"]: u for u in self.db.lister_utilisateurs()}
        self.tableau.delete(*self.tableau.get_children())
        for u in self.comptes.values():
            if u["role"] == "etudiant":
                lien = f"{u['nom']} {u['prenom']}".strip()
            elif u["role"] == "enseignant":
                lien = u["matieres"] or "aucune matière"
            else:
                lien = "accès complet"
            nom = u["username"] + ("  (vous)" if u["id"] == self.utilisateur.id else "")
            self.tableau.insert("", "end", iid=str(u["id"]), values=(nom, auth.ROLES[u["role"]], lien))

        self.etudiants_libres = {f"{e['nom']} {e['prenom']}".strip() + f"  (n° {e['id']})": e["id"]
                                 for e in self.db.etudiants_sans_compte()}
        self.combo_etudiant["values"] = list(self.etudiants_libres)
        if self.var_etudiant.get() not in self.etudiants_libres:
            self.var_etudiant.set("")

        self.matieres = self.db.lister_matieres()
        self.liste_matieres.delete(0, "end")
        for m in self.matieres:
            suffixe = f"   (actuellement : {m['enseignant']})" if m["enseignant"] else ""
            self.liste_matieres.insert("end", m["nom"] + suffixe)
        self._maj_options_role()

    def _selection(self):
        sel = self.tableau.selection()
        if not sel:
            messagebox.showinfo("Utilisateurs", "Sélectionnez d'abord un compte dans la liste.", parent=self)
            return None
        return self.comptes[int(sel[0])]

    def _signaler_changement(self):
        self.charger()
        if self.on_change:
            self.on_change()

    def creer(self):
        role = self.roles_par_libelle.get(self.var_role.get())
        if self.var_mdp.get() != self.var_conf.get():
            messagebox.showerror("Mot de passe", "Les deux mots de passe ne correspondent pas.", parent=self)
            return
        etudiant_id = self.etudiants_libres.get(self.var_etudiant.get()) if role == "etudiant" else None
        if role == "etudiant" and etudiant_id is None:
            messagebox.showerror("Compte étudiant", "Choisissez l'étudiant à rattacher à ce compte.", parent=self)
            return
        matieres = [self.matieres[i]["id"] for i in self.liste_matieres.curselection()] if role == "enseignant" else []
        deja = [self.matieres[i] for i in self.liste_matieres.curselection() if self.matieres[i]["enseignant"]]
        if role == "enseignant" and deja and not messagebox.askyesno(
                "Réattribution", "Ces matières ont déjà un enseignant et lui seront retirées :\n• "
                + "\n• ".join(f"{m['nom']} ({m['enseignant']})" for m in deja) + "\n\nContinuer ?", parent=self):
            return
        try:
            self.db.creer_utilisateur(self.var_id.get(), self.var_mdp.get(), role, etudiant_id, matieres)
        except ValueError as erreur:
            messagebox.showerror("Création impossible", str(erreur), parent=self)
            return
        messagebox.showinfo("Compte créé", f"Le compte « {self.var_id.get().strip()} » "
                                           f"({auth.ROLES[role]}) a été créé.", parent=self)
        for var in (self.var_id, self.var_mdp, self.var_conf, self.var_etudiant):
            var.set("")
        self.liste_matieres.selection_clear(0, "end")
        self._signaler_changement()
        self.champ_id.focus_set()

    def supprimer(self):
        u = self._selection()
        if u is None:
            return
        if u["id"] == self.utilisateur.id:
            messagebox.showerror("Suppression", "Vous ne pouvez pas supprimer votre propre compte.", parent=self)
            return
        if u["role"] == "admin" and self.db.nombre_admins() <= 1:
            messagebox.showerror("Suppression", "Impossible de supprimer le dernier administrateur.", parent=self)
            return
        detail = "\nSes matières n'auront plus d'enseignant responsable." if u["role"] == "enseignant" else ""
        if messagebox.askyesno("Confirmer la suppression",
                               f"Supprimer le compte « {u['username']} » ?{detail}", icon="warning", parent=self):
            self.db.supprimer_utilisateur(u["id"])
            self._signaler_changement()

    def reinitialiser(self):
        u = self._selection()
        if u is None:
            return
        mdp = simpledialog.askstring("Nouveau mot de passe", f"Nouveau mot de passe pour « {u['username']} » :",
                                     show="•", parent=self)
        if mdp is None:
            return
        confirmation = simpledialog.askstring("Nouveau mot de passe", "Confirmez le mot de passe :",
                                              show="•", parent=self)
        if confirmation is None:
            return
        if mdp != confirmation:
            messagebox.showerror("Mot de passe", "Les deux mots de passe ne correspondent pas.", parent=self)
            return
        try:
            self.db.changer_mot_de_passe(u["id"], mdp)
        except ValueError as erreur:
            messagebox.showerror("Mot de passe", str(erreur), parent=self)
            return
        messagebox.showinfo("Mot de passe", "Le mot de passe a été modifié.", parent=self)

    def attribuer(self):
        u = self._selection()
        if u is None:
            return
        if u["role"] != "enseignant":
            messagebox.showinfo("Matières", "Seuls les comptes enseignants ont des matières attribuées.", parent=self)
            return
        AttributionDialog(self, self.db, u, on_change=self._signaler_changement)


class AttributionDialog(tk.Toplevel):
    """Cases à cocher : matières dont un enseignant est responsable."""

    def __init__(self, parent, db, compte, on_change=None):
        super().__init__(parent)
        self.db, self.compte, self.on_change = db, compte, on_change
        preparer_fenetre(self, parent, f"Matières de {compte['username']}")
        self.resizable(False, False)
        cadre = ttk.LabelFrame(self, text=f"Matières attribuées à « {compte['username']} »", padding=14)
        cadre.pack(fill="both", expand=True, padx=16, pady=16)
        self.cases = {}
        for m in db.lister_matieres():
            var = tk.BooleanVar(value=m["enseignant_id"] == compte["id"])
            texte = m["nom"]
            if m["enseignant_id"] not in (None, compte["id"]):
                texte += f"   (actuellement : {m['enseignant']})"
            ttk.Checkbutton(cadre, text=texte, variable=var).pack(anchor="w", pady=2)
            self.cases[m["id"]] = var
        if not self.cases:
            ttk.Label(cadre, text="Aucune matière définie.", style="CarteSous.TLabel").pack()
        f_btn = ttk.Frame(cadre, style="Carte.TFrame")
        f_btn.pack(fill="x", pady=(12, 0))
        ttk.Button(f_btn, text="Enregistrer", style="Succes.TButton", command=self.valider).pack(side="left")
        ttk.Button(f_btn, text="Annuler", style="Neutre.TButton", command=self.destroy).pack(side="right")
        centrer_et_bloquer(self, parent)

    def valider(self):
        self.db.attribuer_matieres(self.compte["id"], [mid for mid, var in self.cases.items() if var.get()])
        self.destroy()
        if self.on_change:
            self.on_change()

    def destroy(self):
        parent = self.master
        super().destroy()
        try:
            parent.grab_set()  # rendre la main à la fenêtre « Gestion des utilisateurs »
        except tk.TclError:
            pass
