import tkinter as tk
import password_final_code_vstrustee_final as app_module
from vault_theme_injector import apply_exciting_theme

root = tk.Tk()
apply_exciting_theme(root)
app = app_module.VSTrusteeApp(root)
root.mainloop()
