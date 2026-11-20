"""Écran de connexion affiché au démarrage (et après une déconnexion)."""

import tkinter as tk
from tkinter import ttk

import theme


class LoginWindow(ttk.Frame):
    """Formulaire de connexion. Appelle `on_success(utilisateur)` si les identifiants sont valides."""

    def __init__(self, master, db, on_success):
        super().__init__(master, padding=30)
        self.db = db
        self.on_success = on_success
        self.echecs = 0
        self.var_identifiant = tk.StringVar()
        self.var_mdp = tk.StringVar()
        self.var_afficher = tk.BooleanVar(value=False)
        self.var_message = tk.StringVar()
        self._construire()

    def _construire(self):
        carte = ttk.Frame(self, style="Carte.TFrame", padding=(36, 28))
        carte.place(relx=0.5, rely=0.5, anchor="center")

        ttk.Label(carte, text="🎓", style="Carte.TLabel", font=(theme.POLICE, 34)).pack()
        ttk.Label(carte, text="Carnet de notes", style="CarteTitre.TLabel").pack()
        ttk.Label(carte, text="Master 1 DAT — Connexion", style="CarteSous.TLabel").pack(pady=(0, 18))

        ttk.Label(carte, text="Identifiant", style="Carte.TLabel").pack(anchor="w")
        self.champ_identifiant = ttk.Entry(carte, textvariable=self.var_identifiant, width=32)
        self.champ_identifiant.pack(fill="x", pady=(2, 10))

        ttk.Label(carte, text="Mot de passe", style="Carte.TLabel").pack(anchor="w")
        self.champ_mdp = ttk.Entry(carte, textvariable=self.var_mdp, show="•", width=32)
        self.champ_mdp.pack(fill="x", pady=(2, 4))

        ttk.Checkbutton(carte, text="Afficher le mot de passe", variable=self.var_afficher,
                        command=self._basculer_affichage).pack(anchor="w", pady=(0, 12))

        self.bouton = ttk.Button(carte, text="Se connecter", style="Primaire.TButton",
                                 command=self.connexion)
        self.bouton.pack(fill="x")

        ttk.Label(carte, textvariable=self.var_message, style="Erreur.TLabel",
                  wraplength=260, justify="center").pack(pady=(10, 0))

        if self.db.mot_de_passe_par_defaut_actif():
            ttk.Label(carte, text="Premier lancement : admin / admin123\n"
                                  "(pensez à changer ce mot de passe)",
                      style="CarteSous.TLabel", justify="center").pack(pady=(6, 0))

        for champ in (self.champ_identifiant, self.champ_mdp):
            champ.bind("<Return>", lambda e: self.connexion())
        self.after(100, self.champ_identifiant.focus_set)

    def _basculer_affichage(self):
        self.champ_mdp.configure(show="" if self.var_afficher.get() else "•")

    def connexion(self):
        if str(self.bouton["state"]) == "disabled":
            return
        identifiant = self.var_identifiant.get().strip()
        mot_de_passe = self.var_mdp.get()
        if not identifiant or not mot_de_passe:
            self.var_message.set("Veuillez saisir votre identifiant et votre mot de passe.")
            return

        utilisateur = self.db.authentifier(identifiant, mot_de_passe)
        if utilisateur is None:
            self.echecs += 1
            self.var_mdp.set("")
            self.champ_mdp.focus_set()
            if self.echecs >= 3:
                # Temporisation croissante contre les essais en série
                self._bloquer(min(30, 5 * (self.echecs - 2)))
            else:
                self.var_message.set("Identifiant ou mot de passe incorrect.")
            return

        self.on_success(utilisateur)

    def _bloquer(self, secondes):
        if secondes <= 0:
            self.bouton.state(["!disabled"])
            self.var_message.set("Identifiant ou mot de passe incorrect.")
            return
        self.bouton.state(["disabled"])
        self.var_message.set(f"Trop de tentatives échouées. Réessayez dans {secondes} s.")
        self.after(1000, self._bloquer, secondes - 1)
