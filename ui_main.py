"""Fenêtre principale : ajout rapide, tableau Treeview, filtres, actions et statistiques en temps réel.

On conserve l'ergonomie de la version d'origine (saisie en haut, tableau au centre,
boutons d'action et ligne de statistiques en bas, podium 🥇🥈🥉).
"""

from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import filedialog, messagebox, ttk

import calculs
import export
import theme
from ui_dialogs import MatieresDialog, StudentDialog, UsersDialog, ouvrir_releve
from ui_stats import StatsWindow

TOUTES = "Toutes les matières / Moyenne générale"


class MainWindow(ttk.Frame):
    TITRES = {"rang": "Rang", "nom": "Nom", "prenom": "Prénom", "note": "Note /20"}

    def __init__(self, master, db, utilisateur, on_logout):
        super().__init__(master, padding=(20, 14, 20, 16))
        self.db, self.utilisateur, self.on_logout = db, utilisateur, on_logout
        self.promotion: list[dict] = []
        self.libelles: dict[str, int] = {}          # libellé de matière -> id
        self.libelles_saisie: dict[str, int] = {}   # matières notables par l'utilisateur
        self.filtre_id: int | None = None
        self.tri_colonne, self.tri_decroissant = "rang", False

        self.var_filtre = tk.StringVar(value=TOUTES)
        self.var_recherche = tk.StringVar()
        self.var_statut = tk.StringVar(value="Aucun étudiant")
        self.var_nom, self.var_prenom = tk.StringVar(), tk.StringVar()
        self.var_matiere, self.var_note = tk.StringVar(), tk.StringVar()

        self._construire_menu()
        self._construire()
        self.var_recherche.trace_add("write", lambda *a: self.afficher())
        racine = self.winfo_toplevel()
        racine.bind("<F5>", lambda e: self.rafraichir())
        racine.bind("<Control-f>", lambda e: self.champ_recherche.focus_set())
        self.rafraichir()

    def destroy(self):
        racine = self.winfo_toplevel()
        for sequence in ("<F5>", "<Control-f>"):
            racine.unbind(sequence)
        racine.config(menu="")
        super().destroy()

    # ================================================================ interface
    def _construire_menu(self):
        u = self.utilisateur
        etat = lambda autorise: "normal" if autorise else "disabled"
        barre = tk.Menu(self.winfo_toplevel())

        fichier = tk.Menu(barre, tearoff=False)
        fichier.add_command(label="Exporter la promotion (CSV / Excel)…", command=self.exporter_csv,
                            state=etat(u.peut_exporter_promotion))
        fichier.add_command(label="Relevé de notes individuel (HTML)…", command=self.releve)
        fichier.add_separator()
        fichier.add_command(label="Importer un ancien carnet (JSON)…", command=self.importer_json,
                            state=etat(u.est_admin))
        fichier.add_separator()
        fichier.add_command(label="Déconnexion", command=self.deconnexion)
        fichier.add_command(label="Quitter", command=self.winfo_toplevel().destroy)
        barre.add_cascade(label="Fichier", menu=fichier)

        gestion = tk.Menu(barre, tearoff=False)
        gestion.add_command(label="Matières & coefficients…", command=self.matieres,
                            state=etat(not u.est_etudiant))
        gestion.add_command(label="Gestion des utilisateurs…", command=self.utilisateurs,
                            state=etat(u.peut_gerer_utilisateurs))
        barre.add_cascade(label="Gestion", menu=gestion)

        affichage = tk.Menu(barre, tearoff=False)
        affichage.add_command(label="Statistiques & graphiques…", command=self.statistiques,
                              state=etat(u.peut_voir_statistiques))
        affichage.add_command(label="Actualiser", accelerator="F5", command=self.rafraichir)
        barre.add_cascade(label="Affichage", menu=affichage)
        self.winfo_toplevel().config(menu=barre)

    def _construire(self):
        u = self.utilisateur

        # --- En-tête : titre + utilisateur connecté
        entete = ttk.Frame(self)
        entete.pack(fill="x", pady=(0, 10))
        titres = ttk.Frame(entete)
        titres.pack(side="left")
        ttk.Label(titres, text="Carnet de notes - Master 1 DAT", style="Entete.TLabel").pack(anchor="w")
        ttk.Label(titres, text="Moyennes pondérées, classement et bulletins", style="Sous.TLabel").pack(anchor="w")
        ttk.Button(entete, text="Déconnexion", style="Neutre.TButton",
                   command=self.deconnexion).pack(side="right")
        if u.peut_gerer_utilisateurs:
            ttk.Button(entete, text="👥 Gestion des utilisateurs", style="Primaire.TButton",
                       command=self.utilisateurs).pack(side="right", padx=8)
        ttk.Label(entete, text=f"👤 {u.username}  ·  {u.libelle_role}",
                  style="Utilisateur.TLabel").pack(side="right", padx=12)

        # --- SECTION 1 : ajout rapide (masquée pour les comptes étudiants)
        if u.peut_ajouter_etudiant:
            saisie = ttk.LabelFrame(self, text="Nouvel étudiant / ajout rapide d'une note", padding=(14, 10))
            saisie.pack(fill="x", pady=(0, 10))
            champs = (("Nom :", ttk.Entry(saisie, textvariable=self.var_nom, width=22)),
                      ("Prénom :", ttk.Entry(saisie, textvariable=self.var_prenom, width=20)),
                      ("Matière :", ttk.Combobox(saisie, textvariable=self.var_matiere,
                                                 state="readonly", width=24)),
                      ("Note :", ttk.Entry(saisie, textvariable=self.var_note, width=8, justify="center")))
            for i, (texte, widget) in enumerate(champs):
                ttk.Label(saisie, text=texte, style="Carte.TLabel").grid(row=0, column=2 * i, sticky="e",
                                                                       padx=(0 if i == 0 else 14, 5))
                widget.grid(row=0, column=2 * i + 1)
                widget.bind("<Return>", lambda e: self.ajouter())
            self.champ_nom, _, self.combo_saisie, self.champ_note = (w for _, w in champs)
            ttk.Button(saisie, text="Ajouter", style="Primaire.TButton",
                       command=self.ajouter).grid(row=0, column=8, padx=(16, 0))
            ttk.Label(saisie, text="La note est facultative. Si l'étudiant existe déjà, la note est ajoutée "
                                   "à sa fiche (virgule ou point acceptés, de 0 à 20).",
                      style="CarteSous.TLabel").grid(row=1, column=0, columnspan=9, sticky="w", pady=(8, 0))

        # --- SECTION 2 : filtres + tableau
        cadre_tableau = ttk.LabelFrame(self, text="Promotion", padding=(12, 8))
        cadre_tableau.pack(fill="both", expand=True)
        filtres = ttk.Frame(cadre_tableau, style="Carte.TFrame")
        filtres.pack(fill="x", pady=(0, 8))
        ttk.Label(filtres, text="📚 Matière :", style="Carte.TLabel").pack(side="left")
        self.combo_filtre = ttk.Combobox(filtres, textvariable=self.var_filtre, state="readonly", width=40)
        self.combo_filtre.pack(side="left", padx=(5, 20))
        self.combo_filtre.bind("<<ComboboxSelected>>", self._changer_filtre)
        ttk.Label(filtres, text="🔍 Rechercher :", style="Carte.TLabel").pack(side="left")
        self.champ_recherche = ttk.Entry(filtres, textvariable=self.var_recherche, width=26)
        self.champ_recherche.pack(side="left", padx=5)
        ttk.Button(filtres, text="✕", width=3, style="Neutre.TButton",
                   command=lambda: self.var_recherche.set("")).pack(side="left")
        ttk.Label(filtres, text="Double-clic : fiche détaillée  ·  Clic sur un en-tête : trier",
                  style="CarteSous.TLabel").pack(side="right")

        zone = ttk.Frame(cadre_tableau, style="Carte.TFrame")
        zone.pack(fill="both", expand=True)
        self.tableau = ttk.Treeview(zone, columns=tuple(self.TITRES), show="headings", height=12)
        for col, largeur, ancre in (("rang", 90, "center"), ("nom", 260, "w"),
                                    ("prenom", 220, "w"), ("note", 110, "center")):
            self.tableau.heading(col, anchor=ancre, command=lambda c=col: self.trier(c))
            self.tableau.column(col, width=largeur, anchor=ancre, stretch=col in ("nom", "prenom"))
        defil = ttk.Scrollbar(zone, orient="vertical", command=self.tableau.yview)
        self.tableau.configure(yscrollcommand=defil.set)
        self.tableau.pack(side="left", fill="both", expand=True)
        defil.pack(side="right", fill="y")
        self.tableau.tag_configure("pair", background=theme.LIGNE_PAIRE)
        self.tableau.tag_configure("echec", foreground=theme.DANGER)
        self.tableau.tag_configure("absent", foreground=theme.TEXTE_DOUX)
        self.tableau.bind("<Double-1>", self.ouvrir_details)
        self.tableau.bind("<Return>", self.ouvrir_details)
        self.tableau.bind("<Delete>", lambda e: self.supprimer())

        # --- SECTION 3 : boutons d'action + statistiques
        bas = ttk.Frame(self)
        bas.pack(fill="x", pady=(12, 0))
        boutons = (
            ("✏ Modifier", "Info", self.ouvrir_details, True),
            ("Supprimer", "Danger", self.supprimer, u.peut_supprimer_etudiant),
            ("📊 Statistiques & Graphiques", "Violet", self.statistiques, u.peut_voir_statistiques),
            ("Exporter CSV", "Succes", self.exporter_csv, u.peut_exporter_promotion),
            ("📄 Relevé HTML", "Neutre", self.releve, True),
            ("Matières", "Primaire", self.matieres, not u.est_etudiant),
        )
        for texte, style, commande, autorise in boutons:
            b = ttk.Button(bas, text=texte, style=f"{style}.TButton", command=commande)
            b.pack(side="left", padx=(0, 8))
            if not autorise:
                b.state(["disabled"])
        ttk.Label(self, textvariable=self.var_statut, style="Statut.TLabel").pack(anchor="w", pady=(10, 0))

    # ================================================================== données
    def rafraichir(self):
        """Recharge tout depuis la base (après chaque modification)."""
        utilisateur = self.db.charger_utilisateur(self.utilisateur.id)
        if utilisateur is None:  # compte supprimé entre-temps
            messagebox.showwarning("Session", "Votre compte n'existe plus.", parent=self)
            self.on_logout()
            return
        self.utilisateur = utilisateur
        matieres = self.db.lister_matieres()
        self.libelles = {f"{m['nom']} (coef {m['coefficient']:g})": m["id"] for m in matieres}
        self.combo_filtre["values"] = [TOUTES, *self.libelles]
        libelle_filtre = next((l for l, mid in self.libelles.items() if mid == self.filtre_id), None)
        if libelle_filtre is None:
            self.filtre_id = None
            libelle_filtre = TOUTES
        self.var_filtre.set(libelle_filtre)

        if self.utilisateur.peut_ajouter_etudiant:
            self.libelles_saisie = {l: mid for l, mid in self.libelles.items() if self.utilisateur.peut_noter(mid)}
            self.combo_saisie["values"] = list(self.libelles_saisie)
            if self.var_matiere.get() not in self.libelles_saisie:
                self.var_matiere.set(next(iter(self.libelles_saisie), ""))

        self.promotion = self.db.tableau_promotion()
        self.afficher()

    def _changer_filtre(self, _event=None):
        self.filtre_id = self.libelles.get(self.var_filtre.get())
        self.afficher()

    def afficher(self):
        """Filtre (matière + recherche), trie et remplit le Treeview, puis met à jour les stats."""
        mid = self.filtre_id
        valeurs = {l["id"]: (l["moyenne"] if mid is None else l["notes"].get(mid)) for l in self.promotion}
        rangs = calculs.classer(valeurs)  # rang dans toute la promotion, indépendant de la recherche
        terme = " ".join(self.var_recherche.get().split()).casefold()

        lignes = []
        for l in self.promotion:
            if not self.utilisateur.peut_voir_etudiant(l["id"]):
                continue
            if terme and terme not in f"{l['nom']} {l['prenom']}".casefold() \
                    and terme not in f"{l['prenom']} {l['nom']}".casefold():
                continue
            lignes.append((l, valeurs[l["id"]], rangs.get(l["id"])))
        lignes = self._trier(lignes)

        selection = self.tableau.selection()
        self.tableau.delete(*self.tableau.get_children())
        for i, (l, valeur, rang) in enumerate(lignes):
            tags = ["pair"] if i % 2 else []
            if valeur is None:
                tags.append("absent")
            elif valeur < calculs.SEUIL_ADMISSION:
                tags.append("echec")
            self.tableau.insert("", "end", iid=str(l["id"]), tags=tags, values=(
                calculs.libelle_rang(rang), l["nom"], l["prenom"], calculs.fmt(valeur)))
        conservees = [s for s in selection if self.tableau.exists(s)]
        if conservees:
            self.tableau.selection_set(conservees)

        for col, titre in self.TITRES.items():
            fleche = (" ▼" if self.tri_decroissant else " ▲") if col == self.tri_colonne else ""
            self.tableau.heading(col, text=titre + fleche)
        self._maj_statistiques([v for _, v, _ in lignes if v is not None], len(lignes))

    def _trier(self, lignes):
        col, desc = self.tri_colonne, self.tri_decroissant
        if col in ("nom", "prenom"):
            autre = "prenom" if col == "nom" else "nom"
            return sorted(lignes, key=lambda x: (x[0][col].casefold(), x[0][autre].casefold()), reverse=desc)
        indice = 1 if col == "note" else 2
        avec = [x for x in lignes if x[indice] is not None]
        sans = [x for x in lignes if x[indice] is None]  # toujours en fin de liste
        avec.sort(key=lambda x: (x[indice], x[0]["nom"].casefold()), reverse=desc)
        return avec + sorted(sans, key=lambda x: x[0]["nom"].casefold())

    def trier(self, colonne):
        if colonne == self.tri_colonne:
            self.tri_decroissant = not self.tri_decroissant
        else:
            self.tri_colonne, self.tri_decroissant = colonne, colonne == "note"
        self.afficher()

    def _maj_statistiques(self, notes, affiches):
        mode = "Moyenne générale" if self.filtre_id is None else self.var_filtre.get()
        ind = calculs.indicateurs(notes)
        if not affiches:
            self.var_statut.set("Aucun étudiant")
        elif ind is None:
            self.var_statut.set(f"👥 {affiches} étudiant(s)  |  aucune note  |  {mode}")
        else:
            effectif = f"{affiches} étudiant(s)" + (f" ({ind['effectif']} noté(s))" if ind["effectif"] != affiches else "")
            self.var_statut.set(f"👥 {effectif}  |  Moyenne : {ind['moyenne']:.2f}  |  "
                                f"Écart-type : {ind['ecart_type']:.2f}  |  Réussite : {ind['taux_reussite']:.0f} %"
                                f"  |  {mode}")

    def _selection(self, avertir=True):
        selection = self.tableau.selection()
        if selection:
            return [int(s) for s in selection]
        if self.utilisateur.est_etudiant and self.utilisateur.etudiant_id:
            return [self.utilisateur.etudiant_id]
        if avertir:
            messagebox.showinfo("Sélection", "Sélectionnez d'abord une ligne dans le tableau.", parent=self)
        return []

    # ================================================================== actions
    def ajouter(self):
        """Contrôle la saisie puis ajoute l'étudiant (et éventuellement sa note)."""
        nom = " ".join(self.var_nom.get().split())
        prenom = " ".join(self.var_prenom.get().split())
        if not nom:
            messagebox.showwarning("Saisie incomplète", "Le nom est obligatoire.", parent=self)
            self.champ_nom.focus_set()
            return

        note = mid = None
        if self.var_note.get().strip():
            mid = self.libelles_saisie.get(self.var_matiere.get())
            if mid is None:
                messagebox.showerror("Matière manquante", "Choisissez la matière correspondant à la note.",
                                     parent=self)
                return
            try:
                note = calculs.valider_note(self.var_note.get())
            except ValueError as erreur:
                messagebox.showerror("Note invalide", str(erreur), parent=self)
                self.champ_note.focus_set()
                self.champ_note.select_range(0, "end")
                return

        existant = self.db.trouver_etudiant(nom, prenom)
        if existant:
            eid = existant["id"]
            if note is None:
                messagebox.showinfo("Étudiant existant", f"« {nom} {prenom} » figure déjà dans la promotion.",
                                    parent=self)
                self._selectionner(eid)
                return
            ancienne = self.db.notes_etudiant(eid).get(mid)
            if ancienne and not messagebox.askyesno(
                    "Note existante", f"« {nom} {prenom} » a déjà {ancienne['valeur']:.2f} dans cette matière.\n"
                                      f"La remplacer par {note:.2f} ?", parent=self):
                return
        else:
            eid = self.db.ajouter_etudiant(nom, prenom)
        if note is not None:
            self.db.definir_note(eid, mid, note)

        # On vide les champs et on remet le focus (comme dans la version d'origine)
        for var in (self.var_nom, self.var_prenom, self.var_note):
            var.set("")
        self.champ_nom.focus_set()
        self.rafraichir()
        self._selectionner(eid)

    def _selectionner(self, eid):
        iid = str(eid)
        if self.tableau.exists(iid):
            self.tableau.selection_set(iid)
            self.tableau.see(iid)

    def ouvrir_details(self, event=None):
        if event is not None and event.type == tk.EventType.ButtonPress \
                and self.tableau.identify_region(event.x, event.y) != "cell":
            return  # double-clic sur un en-tête : c'est un tri, pas une ouverture
        ids = self._selection()
        if ids:
            StudentDialog(self, self.db, self.utilisateur, ids[0], on_save=self.rafraichir)

    def supprimer(self):
        if not self.utilisateur.peut_supprimer_etudiant:
            return
        ids = self._selection()
        if not ids:
            return
        noms = [f"{l['nom']} {l['prenom']}".strip() for l in self.promotion if l["id"] in ids]
        if messagebox.askyesno("Confirmer la suppression",
                               f"Supprimer définitivement {len(ids)} étudiant(s) et toutes leurs notes ?\n\n• "
                               + "\n• ".join(noms), icon="warning", parent=self):
            for eid in ids:
                self.db.supprimer_etudiant(eid)
            self.rafraichir()

    def statistiques(self):
        if self.utilisateur.peut_voir_statistiques:
            StatsWindow(self, self.db, self.utilisateur, self.filtre_id)

    def matieres(self):
        if not self.utilisateur.est_etudiant:
            MatieresDialog(self, self.db, self.utilisateur, on_change=self.rafraichir)

    def utilisateurs(self):
        if self.utilisateur.peut_gerer_utilisateurs:
            UsersDialog(self, self.db, self.utilisateur, on_change=self.rafraichir)

    def exporter_csv(self):
        if not self.utilisateur.peut_exporter_promotion:
            return
        if not self.promotion:
            messagebox.showwarning("Export", "La promotion est vide : rien à exporter.", parent=self)
            return
        chemin = filedialog.asksaveasfilename(
            parent=self, title="Exporter la promotion", defaultextension=".csv",
            initialdir=export.DOSSIER_EXPORTS if export.DOSSIER_EXPORTS.exists() else None,
            initialfile=f"promotion_M1_DAT_{date.today():%Y-%m-%d}.csv",
            filetypes=[("CSV compatible Excel", "*.csv"), ("Tous les fichiers", "*.*")])
        if not chemin:
            return
        try:
            n = export.exporter_csv(self.db, chemin)
        except OSError as erreur:
            messagebox.showerror("Export", f"Impossible d'écrire le fichier : {erreur}", parent=self)
            return
        messagebox.showinfo("Export réussi", f"{n} étudiant(s) exporté(s) dans :\n{chemin}", parent=self)

    def releve(self):
        ids = self._selection()
        if ids:
            ouvrir_releve(self, self.db, ids[0])

    def importer_json(self):
        if not self.utilisateur.est_admin:
            return
        chemin = filedialog.askopenfilename(parent=self, title="Importer un ancien carnet",
                                            filetypes=[("Carnet JSON", "*.json")])
        if not chemin:
            return
        try:
            importes, ignores = self.db.importer_json(chemin)
        except (OSError, ValueError) as erreur:
            messagebox.showerror("Import", f"Impossible d'importer le fichier : {erreur}", parent=self)
            return
        self.rafraichir()
        messagebox.showinfo("Import terminé", f"{importes} note(s) importée(s)"
                            + (f", {ignores} entrée(s) invalide(s) ignorée(s)." if ignores else "."), parent=self)

    def deconnexion(self):
        if messagebox.askyesno("Déconnexion", "Voulez-vous vous déconnecter ?", parent=self):
            self.on_logout()
