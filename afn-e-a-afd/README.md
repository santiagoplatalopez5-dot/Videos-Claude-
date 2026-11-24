# Conversión de AFN-ε a AFD (Python + interfaz gráfica)

Proyecto de **Lenguajes Formales y Autómatas**. El programa recibe un AFN con
transiciones vacías, elimina las ε-transiciones calculando ε-cláusulas (AFN-ε → AFN),
determiniza el resultado por construcción de subconjuntos (AFN → AFD), valida cadenas y
dibuja el AFD final.

## Cómo ejecutarlo

Requisitos: **Python 3.8 o superior**. No hace falta instalar librerías externas.

```bash
python afn_a_afd.py
```

* **Windows / macOS:** Tkinter ya viene con Python.
* **Linux:** si aparece `No module named 'tkinter'`, instala `sudo apt install python3-tk`.

Modo consola (imprime todas las tablas sin abrir ventanas):

```bash
python afn_a_afd.py --reporte 1                          # ejemplo integrado 1..4
python afn_a_afd.py --reporte ejemplos/ejemplo3_decimales.json
```

Pruebas automáticas: `python -m unittest test_afn_a_afd -v`

> Antes de entregar, escriban los nombres del equipo en la constante `INTEGRANTES`, al
> inicio de `afn_a_afd.py`. Aparecen en la ventana, en «Acerca de» y en el reporte.

## Uso de la interfaz

| Pestaña | Qué muestra |
|---|---|
| **Definición del AFN-ε** | Captura de M = (Q, Σ, δ, q0, F): número de estados (2–10), alfabeto (1–4 símbolos), estado inicial (uno solo), estados finales (al menos uno) y la tabla δ. |
| **1 · AFN-ε original** | Tabla de transición capturada, marcando el estado inicial (→) y los finales (*). |
| **2 · ε-cláusulas** | ε-cláusula de cada estado y el recorrido paso a paso con el que se obtuvo. |
| **3 · AFN sin ε** | Tabla con δ'(q,a) = ε-cl(δ(ε-cl(q), a)), el nuevo F' y el desarrollo de cada casilla. |
| **4 · AFD final** | Tabla del AFD con el subconjunto de cada estado, su tipo (inicial / final / muerto) y el detalle de la construcción. |
| **5 · Validar cadenas** | Evalúa una o varias cadenas y muestra ACEPTADA/RECHAZADA y el recorrido de estados. También simula el AFN-ε original para comprobar que ambos coinciden. |
| **6 · Gráfico del AFD** | *(Punto extra)* Dibujo del AFD: flecha de inicio, doble círculo para los finales y estado muerto ∅ punteado. Anima el recorrido de una cadena, permite mover los estados con el ratón y exporta a **SVG** y a código **DOT** de Graphviz. |

Cómo llenar la tabla δ:

* La transición vacía **ε se captura con el carácter fijo `@`** (su columna es la última).
  Por eso `@` no puede formar parte de Σ.
* En cada casilla se escriben los estados destino separados por comas, por ejemplo `q1, q2`
  (también vale `1, 2`). Una casilla vacía significa ∅.
* Si hay un error (un estado que no existe, ningún estado final, etc.), la casilla se pinta de
  rojo y se explica el problema.
* Para la cadena vacía en la validación se escribe `@`.

El menú **Ejemplos** trae cuatro autómatas listos para usar (también están en la carpeta
`ejemplos/`). Con **Archivo → Guardar / Abrir** se guarda el autómata en JSON, y con
**Exportar reporte (.txt)** se obtienen todas las tablas en texto plano.

## Algoritmo

1. **ε-cláusula** de cada estado: recorrido en anchura usando solo las transiciones ε.
2. **AFN sin ε:** δ'(q, a) = ε-cl( ∪ δ(p, a) para p ∈ ε-cl(q) ).  F' = { q | ε-cl(q) ∩ F ≠ ∅ }.
3. **Subconjuntos:** el estado inicial del AFD es ε-cl(q0). Para cada subconjunto T y
   símbolo a, D(T, a) = ∪ δ'(p, a) con p ∈ T. Cada subconjunto nuevo recibe un nombre
   (A, B, C, …). Si el resultado es vacío, se usa el **estado muerto ∅**, que no es de
   aceptación y regresa a sí mismo con todos los símbolos. Un estado del AFD es final si
   contiene algún estado de F'.

## Entregables

* `afn_a_afd.txt`: copia del código fuente en texto plano, como pide la entrega. Si
  modifican `afn_a_afd.py`, vuelvan a copiarlo a `.txt`.
* El video demostrativo y la revisión presencial corren por cuenta del equipo.
  Sugerencia para el video: cargar un ejemplo, recorrer las pestañas 1 a 6, evaluar
  cadenas y animar una en el gráfico.
