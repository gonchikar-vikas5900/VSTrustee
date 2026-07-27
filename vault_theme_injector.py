# vault_theme_injector.py
import tkinter as tk
from tkinter import ttk

def apply_exciting_theme(root):
    style = ttk.Style(root)

    # Choose a built-in theme first
    style.theme_use("clam")

    # ------- Sidebar Theme -------
    style.configure("TButton",
                    font=("Segoe UI", 11, "bold"),
                    foreground="#ffffff",
                    background="#00509E",
                    padding=6)

    style.map("TButton",
              background=[("active", "#0A75D3")])

    # ------- Vault Table Theme -------
    style.configure("Treeview",
                    font=("Segoe UI", 11),
                    foreground="#042A2B",
                    background="#E9F5FF",
                    fieldbackground="#E9F5FF",
                    rowheight=28)

    style.configure("Treeview.Heading",
                    font=("Segoe UI", 12, "bold"),
                    background="#00509E",
                    foreground="white")

    # Alternate rows
    style.map("Treeview",
              background=[("selected", "#FFC857")],
              foreground=[("selected", "black")])

    # ------- Entry Fields -------
    style.configure("TEntry",
                    padding=5,
                    relief="flat",
                    foreground="#062743",
                    fieldbackground="#FAFAFA")
