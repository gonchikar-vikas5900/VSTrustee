import tkinter as tk
import password_final_code_vstrustee_final as app_module
from vault_theme_injector import apply_cyberpunk_theme

root = tk.Tk()

# Apply Cyberpunk Theme
apply_cyberpunk_theme(root)

# Start app
app = app_module.VSTrusteeApp(root)
root.mainloop()
