"""Fenêtre « Statistiques avancées & graphiques », dessinée uniquement avec tk.Canvas."""

from __future__ import annotations

import math
import tkinter as tk
from tkinter import ttk

import calculs
import theme
from ui_dialogs import preparer_fenetre, centrer_et_bloquer

TOUTES = "Toutes les matières / Moyenne générale"


class StatsWindow(tk.Toplevel):
    def __init__(self, parent, db, utilisateur, matiere_id=None):
        super().__init__(parent)
        self.db, self.utilisateur = db, utilisateur
        self.donnees: list[tuple[str, float]] = []  # (nom affiché, note) triées décroissantes
        self._dessin_prevu = None
        preparer_fenetre(self, parent, "Statistiques avancées & graphiques")
        self.geometry("1080x600")
        self.minsize(900, 500)

        self.matieres = db.lister_matieres()
        self.libelles = {f"{m['nom']} (coef {m['coefficient']:g})": m["id"] for m in self.matieres}
        initial = next((l for l, mid in self.libelles.items() if mid == matiere_id), TOUTES)
        self.var_mode = tk.StringVar(value=initial)
        self._construire()
        self.calculer()
        centrer_et_bloquer(self, parent, modale=False)

    # ---------------------------------------------------------------- interface
    def _construire(self):
        haut = ttk.Frame(self, padding=(16, 12, 16, 0))
        haut.pack(fill="x")
        ttk.Label(haut, text="📊 Statistiques de la promotion", style="Entete.TLabel").pack(side="left")
        combo = ttk.Combobox(haut, textvariable=self.var_mode, state="readonly", width=40,
                             values=[TOUTES, *self.libelles])
        combo.pack(side="right")
        combo.bind("<<ComboboxSelected>>", lambda e: self.calculer())
        ttk.Label(haut, text="Données :").pack(side="right", padx=6)

        corps = ttk.Frame(self, padding=16)
        corps.pack(fill="both", expand=True)
        corps.columnconfigure(0, weight=1)
        corps.rowconfigure(0, weight=1)

        self.onglets = onglets = ttk.Notebook(corps)
        onglets.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        self.canvas_hist = tk.Canvas(onglets, bg=theme.CARTE, highlightthickness=0)
        self.canvas_indiv = tk.Canvas(onglets, bg=theme.CARTE, highlightthickness=0)
        onglets.add(self.canvas_hist, text="Répartition par tranches")
        onglets.add(self.canvas_indiv, text="Notes individuelles & seuil")
        for c in (self.canvas_hist, self.canvas_indiv):
            c.bind("<Configure>", lambda e: self._planifier_dessin())

        panneau = ttk.Frame(corps, width=290)
        panneau.grid(row=0, column=1, sticky="ns")

        f_ind = ttk.LabelFrame(panneau, text="Indicateurs", padding=12)
        f_ind.pack(fill="x")
        self.vars = {}
        for i, (cle, texte) in enumerate((("effectif", "Effectif noté"), ("moyenne", "Moyenne"),
                                          ("ecart_type", "Écart-type"), ("mediane", "Médiane"),
                                          ("min", "Note min"), ("max", "Note max"),
                                          ("admis", "Admis / Ajournés"), ("taux", "Taux de réussite"))):
            ttk.Label(f_ind, text=texte, style="CarteSous.TLabel").grid(row=i, column=0, sticky="w", pady=2)
            self.vars[cle] = tk.StringVar(value="—")
            lab = ttk.Label(f_ind, textvariable=self.vars[cle], style="Valeur.TLabel")
            lab.grid(row=i, column=1, sticky="e", padx=(24, 0))
            if cle == "taux":
                self.label_taux = lab
        f_ind.columnconfigure(1, weight=1)

        f_top = ttk.LabelFrame(panneau, text="🏆 Top 3 des étudiants", padding=12)
        f_top.pack(fill="x", pady=(14, 0))
        self.vars_top = []
        for _ in range(3):
            var = tk.StringVar(value="—")
            ttk.Label(f_top, textvariable=var, style="Carte.TLabel", font=(theme.POLICE, 11)).pack(anchor="w", pady=2)
            self.vars_top.append(var)

        ttk.Label(panneau, text=f"Seuil d'admission : {calculs.SEUIL_ADMISSION:g}/20",
                  style="Sous.TLabel").pack(anchor="w", pady=(14, 0))
        ttk.Button(panneau, text="Fermer", style="Neutre.TButton", command=self.destroy).pack(side="bottom", fill="x")

    # ------------------------------------------------------------------ données
    def calculer(self):
        mid = self.libelles.get(self.var_mode.get())
        donnees = []
        for l in self.db.tableau_promotion():
            valeur = l["moyenne"] if mid is None else l["notes"].get(mid)
            if valeur is not None:
                donnees.append((f"{l['prenom']} {l['nom']}".strip(), valeur))
        self.donnees = sorted(donnees, key=lambda d: -d[1])

        ind = calculs.indicateurs([v for _, v in self.donnees])
        if ind is None:
            for var in self.vars.values():
                var.set("—")
        else:
            self.vars["effectif"].set(str(ind["effectif"]))
            for cle in ("moyenne", "ecart_type", "mediane", "min", "max"):
                self.vars[cle].set(f"{ind[cle]:.2f}")
            self.vars["admis"].set(f"{ind['admis']} / {ind['ajournes']}")
            self.vars["taux"].set(f"{ind['taux_reussite']:.1f} %")
        couleur = theme.TEXTE if ind is None else (theme.SUCCES if ind["taux_reussite"] >= 50 else theme.DANGER)
        self.label_taux.configure(foreground=couleur)

        medailles = ("🥇", "🥈", "🥉")
        for i, var in enumerate(self.vars_top):
            if i < len(self.donnees):
                nom, v = self.donnees[i]
                var.set(f"{medailles[i]}  {nom} — {v:.2f}")
            else:
                var.set("—")
        self._planifier_dessin()

    def _planifier_dessin(self):
        if self._dessin_prevu:
            self.after_cancel(self._dessin_prevu)
        self._dessin_prevu = self.after(30, self.dessiner)

    def dessiner(self):
        self._dessin_prevu = None
        self._dessiner_histogramme(self.canvas_hist)
        self._dessiner_individuel(self.canvas_indiv)

    # -------------------------------------------------------------- graphiques
    def _cadre_vide(self, c, titre):
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 100 or h < 100:
            return None
        c.create_text(w / 2, 20, text=titre, font=(theme.POLICE, 12, "bold"), fill=theme.PRIMAIRE)
        if not self.donnees:
            c.create_text(w / 2, h / 2, text="Aucune note disponible pour cette sélection.",
                          font=(theme.POLICE, 11), fill=theme.TEXTE_DOUX)
            return None
        return w, h

    @staticmethod
    def _axe_y(c, x0, y0, x1, y1, maxi, pas, legende):
        for k in range(0, int(maxi) + 1, pas):
            y = y0 - k / maxi * (y0 - y1)
            c.create_line(x0, y, x1, y, fill=theme.GRILLE)
            c.create_text(x0 - 8, y, text=str(k), anchor="e", font=(theme.POLICE, 9), fill=theme.TEXTE_DOUX)
        c.create_line(x0, y1, x0, y0, fill=theme.TEXTE_DOUX)
        c.create_line(x0, y0, x1, y0, fill=theme.TEXTE_DOUX)
        c.create_text(16, (y0 + y1) / 2, text=legende, angle=90, font=(theme.POLICE, 9), fill=theme.TEXTE_DOUX)

    def _dessiner_histogramme(self, c):
        dims = self._cadre_vide(c, f"Répartition des notes par tranches — {self.var_mode.get()}")
        if dims is None:
            return
        w, h = dims
        x0, y0, x1, y1 = 60, h - 70, w - 25, 60
        comptes = [0] * len(calculs.TRANCHES)
        for _, v in self.donnees:
            comptes[calculs.tranche(v)] += 1
        pas = max(1, math.ceil(max(comptes) / 5))
        maxi = pas * (max(comptes) // pas + 1)  # marge au-dessus de la plus haute barre
        self._axe_y(c, x0, y0, x1, y1, maxi, pas, "Effectif")

        slot = (x1 - x0) / len(comptes)
        largeur = slot * 0.62
        total = len(self.donnees)
        for i, ((libelle, _, couleur), n) in enumerate(zip(calculs.TRANCHES, comptes)):
            xa = x0 + i * slot + (slot - largeur) / 2
            yb = y0 - n / maxi * (y0 - y1)
            if n:
                c.create_rectangle(xa, yb, xa + largeur, y0, fill=couleur, outline="")
            c.create_text(xa + largeur / 2, yb - 10, text=str(n), font=(theme.POLICE, 11, "bold"), fill=theme.TEXTE)
            c.create_text(xa + largeur / 2, y0 + 16, text=libelle, font=(theme.POLICE, 10, "bold"), fill=theme.TEXTE)
            c.create_text(xa + largeur / 2, y0 + 34, text=f"{100 * n / total:.0f} %",
                          font=(theme.POLICE, 9), fill=theme.TEXTE_DOUX)

        # Seuil d'admission : frontière entre la tranche « < 10 » et « 10-12 »
        xs = x0 + slot
        c.create_line(xs, y1 - 8, xs, y0 + 4, fill=theme.DANGER, width=2, dash=(6, 4))
        c.create_text(xs + 6, y1 - 8, text=f"Seuil d'admission ({calculs.SEUIL_ADMISSION:g}/20)",
                      anchor="w", font=(theme.POLICE, 9, "bold"), fill=theme.DANGER)
        c.create_text(x0 + slot / 2, y0 + 54, text="Ajournés", font=(theme.POLICE, 9, "italic"), fill=theme.DANGER)
        c.create_text((xs + x1) / 2, y0 + 54, text="Admis", font=(theme.POLICE, 9, "italic"), fill=theme.SUCCES)

    def _dessiner_individuel(self, c):
        dims = self._cadre_vide(c, f"Notes individuelles — {self.var_mode.get()}")
        if dims is None:
            return
        w, h = dims
        n = len(self.donnees)
        slot_estime = (w - 85) / n
        bas = 40 if slot_estime >= 80 else 100  # place pour les noms inclinés
        x0, y0, x1, y1 = 60, h - bas, w - 25, 50
        self._axe_y(c, x0, y0, x1, y1, 20, 4, "Note /20")

        def y_de(note):
            return y0 - note / 20 * (y0 - y1)

        slot = (x1 - x0) / n
        largeur = min(slot * 0.7, 60)
        for i, (nom, v) in enumerate(self.donnees):
            xm = x0 + i * slot + slot / 2
            c.create_rectangle(xm - largeur / 2, y_de(v), xm + largeur / 2, y0,
                               fill=calculs.TRANCHES[calculs.tranche(v)][2], outline="")
            if slot >= 26:
                c.create_text(xm, y_de(v) - 9, text=f"{v:.1f}", font=(theme.POLICE, 8, "bold"), fill=theme.TEXTE)
            court = nom if len(nom) <= 16 else nom[:15] + "…"
            if bas == 40:
                c.create_text(xm, y0 + 14, text=court, font=(theme.POLICE, 9), fill=theme.TEXTE)
            else:
                c.create_text(xm + 4, y0 + 8, text=court, angle=40, anchor="ne",
                              font=(theme.POLICE, 9), fill=theme.TEXTE)

        # Ligne horizontale du seuil d'admission
        ys = y_de(calculs.SEUIL_ADMISSION)
        c.create_line(x0, ys, x1, ys, fill=theme.DANGER, width=2, dash=(8, 4))
        c.create_text(x1, ys - 8, text=f"Seuil d'admission {calculs.SEUIL_ADMISSION:g}/20", anchor="e",
                      font=(theme.POLICE, 9, "bold"), fill=theme.DANGER)
        # Ligne de la moyenne
        moyenne = sum(v for _, v in self.donnees) / n
        ym = y_de(moyenne)
        c.create_line(x0, ym, x1, ym, fill=theme.PRIMAIRE, width=1, dash=(2, 3))
        c.create_text(x0 + 6, ym - 8, text=f"Moyenne {moyenne:.2f}", anchor="w",
                      font=(theme.POLICE, 9, "bold"), fill=theme.PRIMAIRE)
