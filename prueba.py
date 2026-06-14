import engine
data = engine.load_data("data.json")

# Cambia "E" por el grupo que quieras inspeccionar
info = data["groups"]["E"]
print("Pendientes:", engine.pending_matches(info))
for nombre, d in engine.group_status(info).items():
    print(f"{nombre}: posiciones {d['posiciones']} -> {d['estado']}")