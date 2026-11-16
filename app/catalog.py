"""Produse fictive pentru catalogul demonstrativ; fotografii ilustrative Unsplash."""

CATALOG = [
    {"id": 1, "name": "Studio One", "price": 749, "category": "Audio", "badge": "Preferatul nostru", "image": "headphones.jpg", "description": "Căști over-ear pentru muzică, concentrare și pauze bine meritate. Design confortabil, sunet echilibrat și până la 30 de ore de autonomie."},
    {"id": 2, "name": "Frame Mini", "price": 2499, "category": "Foto", "badge": "Nou în colecție", "image": "camera.jpg", "description": "O cameră compactă pentru momentele care merită păstrate. Senzor de 24 MP, control manual și un corp ușor de luat oriunde."},
    {"id": 3, "name": "Tempo Watch", "price": 899, "category": "Lifestyle", "badge": "Esențial", "image": "watch.jpg", "description": "Un ceas inteligent cu un design discret. Urmărește mișcarea zilnică, notificările și ritmul tău, cu autonomie de până la 7 zile."},
    {"id": 4, "name": "Orbit Speaker", "price": 449, "category": "Audio", "badge": "Sunet oriunde", "image": "speaker.jpg", "description": "Boxă portabilă pentru birou și weekend. Conexiune Bluetooth, sunet plin și o formă compactă, ușor de integrat în orice spațiu."},
    {"id": 5, "name": "Forma Keyboard", "price": 389, "category": "Workspace", "badge": "Pentru biroul tău", "image": "keyboard.jpg", "description": "Tastatură mecanică într-un format compact. Taste tactile, conexiune USB și un profil confortabil pentru ideile care nu se opresc."},
    {"id": 6, "name": "Arc Mouse", "price": 229, "category": "Workspace", "badge": "Mai puțin, mai bine", "image": "mouse.jpg", "description": "Mouse wireless cu senzor precis și formă minimalistă. Un partener simplu și comod pentru proiectele de zi cu zi."},
    {"id": 7, "name": "Studio Pro", "price": 1099, "category": "Audio", "badge": "Ediția Pro", "image": "headphones.jpg", "description": "Căști pentru sesiunile lungi de ascultare. Anulare activă a zgomotului, pernițe moi și conectare simultană la două dispozitive."},
    {"id": 8, "name": "Frame Explorer", "price": 3299, "category": "Foto", "badge": "Pentru exploratori", "image": "camera.jpg", "description": "Aparat foto pentru povești din afara biroului. Stabilizare de imagine, înregistrare 4K și controale accesibile într-un corp compact."},
]

for product in CATALOG:
    product["image"] = "/static/images/" + product["image"]
