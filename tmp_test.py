import customtkinter as ctk
from app import ConsoleApp

app = ConsoleApp()
app.update_idletasks()
print('initial active', app.content._active)
for route in ['telemetry','ecus','can','ota']:
    app.sidebar._select(route)
    app.update_idletasks()
    print('route', route, 'active', app.content._active, 'mapped', app.content._views[route].winfo_ismapped(), 'visible', app.content._views[route].winfo_viewable())
app._on_close()
