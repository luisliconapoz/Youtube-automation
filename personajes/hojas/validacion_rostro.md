# Validación de la cara maestra

Render de sonda a 400 px, sin brillo. Coordenadas en u relativas al centro de la cabeza (caja x0, y0, x1, y1). Zona facial protegida: (-36.0, -50.0, 36.0, 46.0)

## Expresión neutral: medidas comunes a los 13 personajes

| Rasgo | Caja (u) |
|---|---|
| ojo_izq | (-31.2, -26.7, -3.0, 11.2) |
| pupila_izq | (-21.5, -12.2, -6.2, 2.3) |
| ceja_izq | (-28.8, -37.1, -5.4, -33.9) |
| ojo_der | (3.4, -26.7, 30.8, 11.2) |
| pupila_der | (13.1, -12.2, 27.6, 2.3) |
| ceja_der | (5.9, -37.1, 28.4, -33.9) |
| boca | (-11.0, 28.1, 11.5, 34.5) |

## Comparación por expresión

| Expresión | Medidas idénticas en los 13 | Zona facial píxel a píxel idéntica | Distintos |
|---|---|---|---|
| neutral | ✅ | ✅ | — |
| happy | ✅ | ✅ | — |
| talking | ✅ | ✅ | — |
| surprised | ✅ | ✅ | — |
| confused | ✅ | ✅ | — |
| thinking | ✅ | ✅ | — |
| concerned | ✅ | ✅ | — |
| skeptical | ✅ | ✅ | — |
| excited | ✅ | ✅ | — |
| angry | ✅ | ✅ | — |
| serious | ✅ | ✅ | — |
| smug | ✅ | ✅ | — |

**Resultado: APROBADO** — un solo rostro maestro reutilizado por los 13 personajes.
