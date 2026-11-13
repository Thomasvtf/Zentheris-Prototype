# app/src/

Código de la app, por capas:

```
app/ (rutas)  →  screens/ (vista + hook de datos)  →  api/ (cliente tipado)  →  API
                         ↑
     components/ · theme/ · texts/ · format/ · state/
```

- `app/`: rutas de expo-router, en español (DC-62); solo enrutan.
- `screens/`: una carpeta por pantalla.
- `components/`: los 34 componentes del sistema de diseño (llegan después).
- `theme/`, `texts/`, `format/`, `api/` y `state/`: ver su README.

Las carpetas `constants/` y `hooks/` y parte de `components/` son de la plantilla de Expo; las ramas del equipo todavía las usan y se quitan después de la Fase 4.
