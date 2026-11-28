# Informe de validación · 13 personajes fieles

Mediciones calculadas sobre las imágenes reales: cada reconstrucción se dibuja en el mismo marco y
escala que su guía (×4) y a ambas se les aplica la misma extracción. La cara pintada en cada guía se
sustituye por el rostro maestro (regla del proyecto) y su zona se excluye de la fidelidad de capas.

| Personaje | Silueta IoU | Dist. media contorno (px) | Capa principal IoU (±1 px) | Grosor neón guía / rec. (mediana px) | Halo error | Invasión del rostro | Accesorio recortado (px²) |
|---|---|---|---|---|---|---|---|
| blue | 0.991 | 0.26 | — | 3.5 / 3.5 | 3.0 | 0 | 0.0 |
| green | 0.967 | 0.73 | 0.870 | 2.6 / 2.7 | 3.7 | 0 | 1.0 |
| pink | 0.931 | 0.94 | 0.901 | 2.9 / 2.9 | 5.3 | 0 | 64.4 |
| farmer | 0.840 | 2.41 | 0.820 | 1.5 / 2.5 | 2.9 | 0 | 187.0 |
| rich | 0.935 | 1.22 | 0.893 | 3.5 / 3.6 | 1.6 | 0 | 270.6 |
| cyan | 0.937 | 0.47 | 0.840 | 3.5 / 4.3 | 8.3 | 0 | 11.2 |
| lime | 0.897 | 0.42 | 0.912 | 3.2 / 2.7 | 11.2 | 0 | 6.3 |
| brown | 0.964 | 0.41 | 0.919 | 3.5 / 3.0 | 5.3 | 0 | 11.0 |
| gray | 0.963 | 0.40 | 0.933 | 2.5 / 2.5 | 5.6 | 0 | 5.1 |
| orange | 0.943 | 0.48 | 0.923 | 3.2 / 2.9 | 5.4 | 0 | 66.6 |
| purple | 0.927 | 0.38 | 0.893 | 2.8 / 2.5 | 7.6 | 0 | 71.6 |
| white | 0.953 | 0.46 | 0.932 | 2.9 / 2.8 | 8.8 | 0 | 107.0 |
| teal | 0.970 | 0.47 | 0.941 | 2.8 / 2.5 | 4.3 | 0 | 40.7 |

Blue: medido con su comparación aprobada (ronda 2, en su propio marco de trazado).

## Rostro maestro idéntico

Rasgos del rostro de los 13 dibujados en un marco común (mismo centro y escala): píxeles distintos
(máximo entre los 13) por expresión:

| neutral | happy | talking | surprised | confused | thinking | concerned | skeptical | excited | angry | serious | smug |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
