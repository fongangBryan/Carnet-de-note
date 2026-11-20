"""Point d'entrée : Carnet de notes - Master 1 DAT.

Lancement :  python main.py
Premier lancement : compte administrateur  admin / admin123
"""

import sys
import tkinter as tk
from tkinter import messagebox

import theme
from database import Database
from login_window import LoginWindow
from ui_main import MainWindow


class Application(tk.Tk):
    """Fenêtre racine unique : alterne entre l'écran de connexion et la fenêtre principale."""

    def __init__(self):
        super().__init__()
        theme.appliquer_style(self)
        self.title("Carnet de notes - Master 1 DAT")
        self.protocol("WM_DELETE_WINDOW", self.quitter)
        self.db = Database()
        self.ecran = None
        self.afficher_connexion()
        if self.db.messages:
            self.after(300, lambda: messagebox.showinfo("Initialisation", "\n\n".join(self.db.messages), parent=self))

    def _changer_ecran(self, ecran, geometrie, taille_min):
        if self.ecran is not None:
            self.ecran.destroy()
        self.minsize(*taille_min)
        self.geometry(geometrie)
        self.ecran = ecran
        ecran.pack(fill="both", expand=True)

    def afficher_connexion(self):
        self.title("Carnet de notes - Master 1 DAT — Connexion")
        self._changer_ecran(LoginWindow(self, self.db, self.connecte), "460x540", (420, 500))

    def connecte(self, utilisateur):
        self.title(f"Carnet de notes - Master 1 DAT — {utilisateur.username} ({utilisateur.libelle_role})")
        # La fenêtre principale est construite après la destruction de l'écran de connexion
        if self.ecran is not None:
            self.ecran.destroy()
            self.ecran = None
        self._changer_ecran(MainWindow(self, self.db, utilisateur, self.afficher_connexion),
                            "1100x720", (980, 620))
        if utilisateur.est_admin and self.db.mot_de_passe_par_defaut_actif():
            messagebox.showwarning("Sécurité", "Le mot de passe par défaut « admin123 » est toujours actif.\n"
                                   "Changez-le via « Gestion des utilisateurs » → « Nouveau mot de passe ».",
                                   parent=self)

    def quitter(self):
        self.db.fermer()
        self.destroy()


def activer_haute_resolution():
    """Texte net sur les écrans Windows à mise à l'échelle (125 %, 150 %…)."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass


if __name__ == "__main__":
    activer_haute_resolution()
    Application().mainloop()
