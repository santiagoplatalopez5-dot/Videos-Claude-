#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
  CONVERSIÓN DE AFN-ε A AFD
  Lenguajes Formales y Autómatas
===============================================================================

Programa con interfaz gráfica (Tkinter) que:

  1. Captura la quíntupla M = (Q, Σ, δ, q0, F) de un Autómata Finito No
     Determinista con transiciones vacías (AFN-ε).
  2. ETAPA 1: calcula la ε-cláusula de cada estado y elimina las transiciones
     vacías (AFN-ε  ->  AFN).
  3. ETAPA 2: aplica la construcción de subconjuntos partiendo de la
     ε-cláusula del estado inicial (AFN  ->  AFD).
  4. Valida cadenas con el AFD y muestra el recorrido de estados.
  5. (Punto extra) Dibuja el AFD final, anima el recorrido de una cadena y
     exporta el dibujo a SVG y a código DOT (Graphviz).

Requisitos: Python 3.8 o superior. No usa librerías externas.
Tkinter ya viene incluido con Python en Windows y macOS.
En Linux puede instalarse con:   sudo apt install python3-tk

Uso:
    python afn_a_afd.py                       -> abre la interfaz gráfica
    python afn_a_afd.py --reporte 1           -> imprime en consola todas las
                                                 tablas del ejemplo 1
    python afn_a_afd.py --reporte mi.json     -> igual, con un autómata guardado
"""

import json
import math
import re
import string
import sys
from collections import deque, namedtuple
from html import escape

try:
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog
    import tkinter.font as tkfont
except ImportError:  # Permite usar el modo consola aunque falte Tkinter
    tk = None


# =============================================================================
#  CONFIGURACIÓN GENERAL
# =============================================================================

# Escriban aquí los nombres del equipo (2 o 3 integrantes).
INTEGRANTES = ["Integrante 1", "Integrante 2", "Integrante 3"]

EPS = "@"          # Carácter FIJO con el que el usuario captura ε
EPS_TXT = "ε"      # Cómo se muestra ε en las tablas
VACIO = "∅"        # Conjunto vacío / estado muerto del AFD

MIN_ESTADOS = 2
MAX_ESTADOS = 10
MAX_SIMBOLOS = 4

CELDAS_VACIAS = {"", "-", "—", VACIO, "Ø", "ø", "{}"}


class ErrorAutomata(ValueError):
    """Error de validación con un mensaje claro para el usuario.

    `celda` indica la casilla (estado, símbolo) de la tabla de transiciones
    que provocó el error, para poder resaltarla en la interfaz.
    """

    def __init__(self, mensaje, celda=None):
        super().__init__(mensaje)
        self.celda = celda


# =============================================================================
#  UTILIDADES DE FORMATO Y VALIDACIÓN
# =============================================================================

def simbolo_txt(s):
    """Texto que se muestra para un símbolo (ε en lugar de @)."""
    return EPS_TXT if s == EPS else s


def marca(es_inicial, es_final):
    """Marca de la primera columna de las tablas:  →  inicial,  *  final."""
    return ("→" if es_inicial else "") + ("*" if es_final else "")


def tag_fila(es_inicial, es_final, es_muerto=False):
    """Etiqueta de color para cada fila de las tablas."""
    if es_muerto:
        return "muerto"
    if es_inicial and es_final:
        return "inicial_final"
    if es_inicial:
        return "inicial"
    if es_final:
        return "final"
    return ""


def nombre_estado_afd(i):
    """0 -> A, 1 -> B, ..., 25 -> Z, 26 -> A1, 27 -> B1, ..."""
    letra = string.ascii_uppercase[i % 26]
    return letra if i < 26 else letra + str(i // 26)


def validar_estados(estados):
    if not MIN_ESTADOS <= len(estados) <= MAX_ESTADOS:
        raise ErrorAutomata(
            f"El conjunto de estados Q debe tener entre {MIN_ESTADOS} y "
            f"{MAX_ESTADOS} estados (tiene {len(estados)}).")
    for q in estados:
        if (not isinstance(q, str) or not q or re.search(r"[\s,;{}]", q)
                or q in (EPS, EPS_TXT, VACIO)):
            raise ErrorAutomata(f"Nombre de estado no válido: '{q}'.")
    if len(set(estados)) != len(estados):
        raise ErrorAutomata("Hay nombres de estados repetidos en Q.")


def validar_alfabeto(simbolos):
    if not 1 <= len(simbolos) <= MAX_SIMBOLOS:
        raise ErrorAutomata(
            f"El alfabeto Σ debe tener entre 1 y {MAX_SIMBOLOS} símbolos "
            f"(tiene {len(simbolos)}).")
    for s in simbolos:
        if not isinstance(s, str) or len(s) != 1:
            raise ErrorAutomata(
                f"Cada símbolo de Σ debe ser UN solo carácter: '{s}' no es válido.")
        if s in (EPS, EPS_TXT):
            raise ErrorAutomata(
                f"'{s}' está reservado para la transición vacía ε; "
                "no puede pertenecer a Σ.")
        if s.isspace() or s in ",;" or s in (VACIO, "Ø", "ø"):
            raise ErrorAutomata(f"El carácter '{s}' no puede usarse como símbolo de Σ.")
    if len(set(simbolos)) != len(simbolos):
        raise ErrorAutomata("Hay símbolos repetidos en el alfabeto Σ.")


def parsear_alfabeto(texto):
    """'a, b'  o  'a b'  o  'ab'  ->  ['a', 'b']"""
    texto = texto.strip()
    if not texto:
        raise ErrorAutomata("Escribe el alfabeto Σ (por ejemplo:  a, b   o   0, 1).")
    if re.search(r"[,;\s]", texto):
        simbolos = [p for p in re.split(r"[,;\s]+", texto) if p]
    else:
        simbolos = list(texto)
    validar_alfabeto(simbolos)
    return simbolos


def parsear_destinos(texto, estados, celda=None):
    """Convierte el texto de una casilla de δ en una lista de estados.

    Acepta:  'q1, q2'   'q1 q2'   '{q1,q2}'   '1,2' (se entiende q1,q2)
    Vacío, '-' o '∅' significan que no hay transición.
    """
    t = (texto or "").strip()
    if t in CELDAS_VACIAS:
        return []
    t = t.replace("{", " ").replace("}", " ")
    partes = [p for p in re.split(r"[,;\s]+", t) if p]
    conocidos = {q.lower(): q for q in estados}
    destinos = []
    for p in partes:
        q = conocidos.get(p.lower()) or conocidos.get("q" + p.lower())
        if q is None:
            donde = (f"En δ({celda[0]}, {simbolo_txt(celda[1])}): " if celda else "")
            raise ErrorAutomata(
                f"{donde}'{p}' no es un estado de Q = {{{', '.join(estados)}}}.", celda)
        if q not in destinos:
            destinos.append(q)
    return destinos


# =============================================================================
#  MODELO:  AFN-ε
# =============================================================================

class AFNE:
    """Autómata finito no determinista con transiciones vacías.

    M = (Q, Σ, δ, q0, F)   con   δ: Q × (Σ ∪ {ε}) -> P(Q)
    """

    def __init__(self, estados, alfabeto, transiciones, inicial, finales):
        self.estados = list(estados)
        self.alfabeto = list(alfabeto)
        self.inicial = inicial
        self.finales = set(finales)

        validar_estados(self.estados)
        validar_alfabeto(self.alfabeto)
        self.indice = {q: i for i, q in enumerate(self.estados)}
        if self.inicial not in self.indice:
            raise ErrorAutomata("Selecciona exactamente UN estado inicial que pertenezca a Q.")
        if not self.finales:
            raise ErrorAutomata("Marca al menos un estado final (de aceptación).")
        for q in self.finales:
            if q not in self.indice:
                raise ErrorAutomata(f"El estado final '{q}' no pertenece a Q.")

        transiciones = transiciones or {}
        for q in transiciones:
            if q not in self.indice:
                raise ErrorAutomata(f"Hay transiciones definidas para '{q}', que no pertenece a Q.")

        # δ completa: para cada estado y cada símbolo (incluido ε) un conjunto
        self.delta = {}
        for q in self.estados:
            fila = transiciones.get(q) or {}
            for s in fila:
                if s not in self.alfabeto and s != EPS:
                    raise ErrorAutomata(
                        f"δ({q}, {s}) usa el símbolo '{s}', que no pertenece a Σ.", (q, s))
            self.delta[q] = {}
            for s in self.alfabeto + [EPS]:
                destinos = fila.get(s) or []
                if isinstance(destinos, str):
                    destinos = parsear_destinos(destinos, self.estados, (q, s))
                for p in destinos:
                    if p not in self.indice:
                        raise ErrorAutomata(
                            f"δ({q}, {simbolo_txt(s)}) contiene '{p}', que no pertenece a Q.",
                            (q, s))
                self.delta[q][s] = frozenset(destinos)

    # ---- formato ------------------------------------------------------------
    def ordenar(self, conjunto):
        return sorted(conjunto, key=self.indice.__getitem__)

    def fmt(self, conjunto):
        """{q0, q1}  o  ∅"""
        if not conjunto:
            return VACIO
        return "{" + ", ".join(self.ordenar(conjunto)) + "}"

    # ---- semántica ----------------------------------------------------------
    def clausura(self, conjunto):
        """ε-cláusula de un conjunto de estados."""
        resultado = set(conjunto)
        pila = list(conjunto)
        while pila:
            p = pila.pop()
            for r in self.delta[p][EPS]:
                if r not in resultado:
                    resultado.add(r)
                    pila.append(r)
        return frozenset(resultado)

    def acepta(self, cadena):
        """Simulación directa del AFN-ε (se usa para verificar al AFD)."""
        actuales = self.clausura({self.inicial})
        for c in cadena:
            if c not in self.alfabeto:
                return False
            siguientes = set()
            for p in actuales:
                siguientes |= self.delta[p][c]
            actuales = self.clausura(siguientes)
        return bool(actuales & self.finales)

    # ---- persistencia -------------------------------------------------------
    def a_dict(self):
        return {
            "estados": self.estados,
            "alfabeto": self.alfabeto,
            "inicial": self.inicial,
            "finales": self.ordenar(self.finales),
            "transiciones": {
                q: {s: self.ordenar(self.delta[q][s])
                    for s in self.alfabeto + [EPS] if self.delta[q][s]}
                for q in self.estados
            },
        }

    @classmethod
    def desde_dict(cls, d):
        try:
            trans = {}
            for q, fila in (d.get("transiciones") or {}).items():
                # se acepta "ε" o "e" como sinónimos de "@" en archivos
                trans[q] = {(EPS if s in (EPS_TXT, "eps") else s): v for s, v in fila.items()}
            return cls(d["estados"], d["alfabeto"], trans, d["inicial"], d["finales"])
        except KeyError as e:
            raise ErrorAutomata(f"Al archivo le falta el campo {e}.") from None


# =============================================================================
#  ETAPA 1:  AFN-ε  ->  AFN   (eliminación de transiciones vacías)
# =============================================================================

class Etapa1:
    """Calcula ε-cláusulas, la nueva función δ' y los nuevos finales F'.

    δ'(q, a) = ε-cl( δ( ε-cl(q), a ) )
    F'       = { q ∈ Q  |  ε-cl(q) ∩ F ≠ ∅ }
    """

    def __init__(self, afne):
        self.afne = afne
        self.estados = afne.estados
        self.alfabeto = afne.alfabeto
        self.inicial = afne.inicial
        fmt = afne.fmt

        # --- ε-cláusulas, con la traza del recorrido ---
        self.clausuras = {}
        self.traza_clausuras = []
        for q in afne.estados:
            cl, pasos = self._clausura_con_traza(q)
            self.clausuras[q] = cl
            self.traza_clausuras.append(f"ε-cl({q}):")
            self.traza_clausuras.append(f"   se inicia con {{{q}}}")
            self.traza_clausuras.extend("   " + p for p in pasos)
            self.traza_clausuras.append(f"   ⇒ ε-cl({q}) = {fmt(cl)}")
            self.traza_clausuras.append("")

        # --- nueva función de transición δ' ---
        self.delta = {}
        self.traza_delta = []
        for q in afne.estados:
            self.delta[q] = {}
            cl_q = self.clausuras[q]
            for a in afne.alfabeto:
                orden = afne.ordenar(cl_q)
                movs = [afne.delta[p][a] for p in orden]
                mov = frozenset().union(*movs)
                res = frozenset().union(*(self.clausuras[p] for p in mov))
                self.delta[q][a] = res

                self.traza_delta.append(f"δ'({q}, {a}) = ε-cl( δ( ε-cl({q}), {a} ) ):")
                self.traza_delta.append(f"   ε-cl({q}) = {fmt(cl_q)}")
                if len(orden) == 1:
                    self.traza_delta.append(f"   δ({fmt(cl_q)}, {a}) = δ({orden[0]}, {a}) = {fmt(mov)}")
                else:
                    union = " ∪ ".join(f"δ({p},{a})" for p in orden)
                    valores = " ∪ ".join(fmt(m) for m in movs)
                    self.traza_delta.append(
                        f"   δ({fmt(cl_q)}, {a}) = {union} = {valores} = {fmt(mov)}")
                self.traza_delta.append(f"   {self._texto_clausura_conjunto(mov)}")
                self.traza_delta.append(f"   ⇒ δ'({q}, {a}) = {fmt(res)}")
                self.traza_delta.append("")

        # --- nuevos estados finales F' ---
        self.finales = {q for q in afne.estados if self.clausuras[q] & afne.finales}
        self.traza_finales = [
            f"F' = estados cuya ε-cláusula contiene algún estado de F = {fmt(afne.finales)}:"]
        for q in afne.estados:
            inter = self.clausuras[q] & afne.finales
            veredicto = "→ FINAL" if inter else "→ no final"
            self.traza_finales.append(
                f"   {q}: ε-cl({q}) ∩ F = {fmt(self.clausuras[q])} ∩ {fmt(afne.finales)}"
                f" = {fmt(inter)}   {veredicto}")
        self.traza_finales.append(f"   ⇒ F' = {fmt(self.finales)}")

    def _clausura_con_traza(self, q):
        afne = self.afne
        visitados = [q]
        conjunto = {q}
        pasos = []
        i = 0
        while i < len(visitados):          # recorrido en anchura por arcos ε
            p = visitados[i]
            i += 1
            destinos = afne.delta[p][EPS]
            nuevos = [r for r in afne.ordenar(destinos) if r not in conjunto]
            for r in nuevos:
                conjunto.add(r)
                visitados.append(r)
            if not destinos:
                pasos.append(f"desde {p} por ε → ∅")
            elif nuevos:
                pasos.append(f"desde {p} por ε → {afne.fmt(destinos)}   (se agrega {', '.join(nuevos)})")
            else:
                pasos.append(f"desde {p} por ε → {afne.fmt(destinos)}   (ya estaban incluidos)")
        return frozenset(conjunto), pasos

    def _texto_clausura_conjunto(self, conjunto):
        fmt = self.afne.fmt
        if not conjunto:
            return f"ε-cl({VACIO}) = {VACIO}"
        orden = self.afne.ordenar(conjunto)
        total = frozenset().union(*(self.clausuras[p] for p in orden))
        if len(orden) == 1:
            return f"ε-cl({fmt(conjunto)}) = ε-cl({orden[0]}) = {fmt(total)}"
        partes = " ∪ ".join(f"ε-cl({p})" for p in orden)
        valores = " ∪ ".join(fmt(self.clausuras[p]) for p in orden)
        return f"ε-cl({fmt(conjunto)}) = {partes} = {valores} = {fmt(total)}"


# =============================================================================
#  ETAPA 2:  AFN  ->  AFD   (construcción de subconjuntos)
# =============================================================================

Evaluacion = namedtuple("Evaluacion", "cadena aceptada pasos final error")


class AFD:
    """AFD obtenido por construcción de subconjuntos sobre el AFN de la etapa 1.

    Se parte de ε-cl(q0). Para cada estado T (subconjunto) y símbolo a:
        D(T, a) = ∪ { δ'(p, a)  |  p ∈ T }
    Si D(T, a) = ∅ se usa el estado muerto ∅ (no de aceptación).
    """

    def __init__(self, etapa1):
        afne = etapa1.afne
        self.etapa1 = etapa1
        self.alfabeto = list(afne.alfabeto)
        self.fmt = afne.fmt
        self.estados = []          # nombres: A, B, C, ..., ∅
        self.subconjunto = {}      # nombre -> frozenset de estados del AFN
        self.delta = {}            # nombre -> {símbolo: nombre}
        self.pasos = []
        nombres = {}               # frozenset -> nombre

        def registrar(conjunto):
            nombre = nombre_estado_afd(len(self.estados))
            self.estados.append(nombre)
            self.subconjunto[nombre] = conjunto
            nombres[conjunto] = nombre
            return nombre

        inicio = etapa1.clausuras[afne.inicial]
        self.inicial = registrar(inicio)
        self.pasos.append(
            f"Estado inicial del AFD:  {self.inicial} = ε-cl({afne.inicial}) = {self.fmt(inicio)}")
        self.pasos.append("")

        hay_muerto = False
        cola = deque([inicio])
        while cola:
            T = cola.popleft()
            nT = nombres[T]
            self.delta[nT] = {}
            self.pasos.append(f"Procesando {nT} = {self.fmt(T)}:")
            orden = afne.ordenar(T)
            for a in self.alfabeto:
                partes = [etapa1.delta[p][a] for p in orden]
                U = frozenset().union(*partes)
                if not U:
                    destino, nota = VACIO, "conjunto vacío → estado muerto ∅"
                    hay_muerto = True
                elif U in nombres:
                    destino, nota = nombres[U], f"ya existe: es {nombres[U]}"
                else:
                    destino = registrar(U)
                    cola.append(U)
                    nota = f"NUEVO estado {destino}"
                self.delta[nT][a] = destino
                union = " ∪ ".join(f"δ'({p},{a})" for p in orden)
                if len(orden) > 1:
                    union += " = " + " ∪ ".join(self.fmt(x) for x in partes)
                self.pasos.append(
                    f"   con '{a}':  {union} = {self.fmt(U)}   →  {destino}   ({nota})")
            self.pasos.append("")

        if hay_muerto:
            self.estados.append(VACIO)
            self.subconjunto[VACIO] = frozenset()
            self.delta[VACIO] = {a: VACIO for a in self.alfabeto}
            self.pasos.append(
                "Estado muerto ∅: NO es de aceptación y con cualquier símbolo regresa a ∅.")
            self.pasos.append("")
        self.muerto = VACIO if hay_muerto else None

        self.finales = [n for n in self.estados if self.subconjunto[n] & etapa1.finales]
        self.pasos.append(
            f"Estados finales del AFD: los subconjuntos que contienen algún estado de "
            f"F' = {self.fmt(etapa1.finales)}")
        for n in self.finales:
            self.pasos.append(f"   ⇒ {n} = {self.fmt(self.subconjunto[n])}")

    def tipo(self, q):
        if q == self.muerto:
            return "Muerto (no aceptación)"
        ini, fin = q == self.inicial, q in self.finales
        if ini and fin:
            return "Inicial y final"
        if ini:
            return "Inicial"
        if fin:
            return "Final (aceptación)"
        return "No final"

    def evaluar(self, cadena):
        """Recorre el AFD con la cadena.  Devuelve un objeto Evaluacion."""
        actual = self.inicial
        pasos = []
        for i, c in enumerate(cadena):
            if c not in self.alfabeto:
                return Evaluacion(cadena, False, pasos, actual,
                                  f"el símbolo '{c}' (posición {i + 1}) no pertenece a Σ")
            siguiente = self.delta[actual][c]
            pasos.append((actual, c, siguiente))
            actual = siguiente
        return Evaluacion(cadena, actual in self.finales, pasos, actual, None)

    def texto_recorrido(self, ev):
        texto = self.inicial
        for _, c, destino in ev.pasos:
            texto += f" ─{c}→ {destino}"
        if ev.error:
            texto += "  ✖"
        return texto

    def aristas(self):
        """Agrupa las transiciones: {(origen, destino): [símbolos]}."""
        res = {}
        for q in self.estados:
            for a in self.alfabeto:
                res.setdefault((q, self.delta[q][a]), []).append(a)
        return res


def convertir(afne):
    """Ejecuta las dos etapas y devuelve (etapa1, afd)."""
    e1 = Etapa1(afne)
    return e1, AFD(e1)


# =============================================================================
#  DATOS DE LAS TABLAS (compartidos por la interfaz y el reporte de texto)
# =============================================================================

def tabla_afne(afne):
    enc = ["", "Estado"] + afne.alfabeto + [f"{EPS_TXT} ({EPS})"]
    filas, tags = [], []
    for q in afne.estados:
        ini, fin = q == afne.inicial, q in afne.finales
        filas.append([marca(ini, fin), q]
                     + [afne.fmt(afne.delta[q][s]) for s in afne.alfabeto + [EPS]])
        tags.append(tag_fila(ini, fin))
    return enc, filas, tags


def tabla_clausuras(e1):
    afne = e1.afne
    enc = ["Estado", "ε-cláusula", "¿Contiene un estado de F?"]
    filas, tags = [], []
    for q in afne.estados:
        inter = e1.clausuras[q] & afne.finales
        filas.append([q, afne.fmt(e1.clausuras[q]),
                      f"Sí: {afne.fmt(inter)}" if inter else "No"])
        tags.append(tag_fila(False, bool(inter)))
    return enc, filas, tags


def tabla_afn(e1):
    afne = e1.afne
    enc = ["", "Estado"] + afne.alfabeto
    filas, tags = [], []
    for q in afne.estados:
        ini, fin = q == e1.inicial, q in e1.finales
        filas.append([marca(ini, fin), q] + [afne.fmt(e1.delta[q][a]) for a in afne.alfabeto])
        tags.append(tag_fila(ini, fin))
    return enc, filas, tags


def tabla_afd(afd, como_subconjuntos=False):
    enc = ["", "Estado", "Subconjunto del AFN"] + afd.alfabeto + ["Tipo"]
    filas, tags = [], []
    for q in afd.estados:
        ini, fin, muerto = q == afd.inicial, q in afd.finales, q == afd.muerto
        destinos = []
        for a in afd.alfabeto:
            d = afd.delta[q][a]
            destinos.append(afd.fmt(afd.subconjunto[d]) if como_subconjuntos else d)
        filas.append([marca(ini, fin), q, afd.fmt(afd.subconjunto[q])] + destinos + [afd.tipo(q)])
        tags.append(tag_fila(ini, fin, muerto))
    return enc, filas, tags


def resumen_afne(afne):
    return (f"Q = {{{', '.join(afne.estados)}}}     Σ = {{{', '.join(afne.alfabeto)}}}     "
            f"Estado inicial: {afne.inicial}     F = {afne.fmt(afne.finales)}     "
            f"Símbolo de ε: '{EPS}'")


def resumen_afn(e1):
    afne = e1.afne
    return (f"Q = {{{', '.join(afne.estados)}}}     Σ = {{{', '.join(afne.alfabeto)}}}     "
            f"Estado inicial: {e1.inicial}     F' = {afne.fmt(e1.finales)}")


def resumen_afd(afd):
    lineas = [
        f"Estados del AFD:  {{{', '.join(afd.estados)}}}      Σ = {{{', '.join(afd.alfabeto)}}}",
        f"Estado inicial:   {afd.inicial} = {afd.fmt(afd.subconjunto[afd.inicial])}"
        f"   (= ε-cl({afd.etapa1.inicial}))",
        "Estados finales:  " + ",   ".join(
            f"{n} = {afd.fmt(afd.subconjunto[n])}" for n in afd.finales),
    ]
    if afd.muerto:
        lineas.append("Estado muerto:    ∅  (sí existe; NO es de aceptación y se queda en ∅ con todo símbolo)")
    else:
        lineas.append("Estado muerto:    no existe (ninguna transición lleva al conjunto vacío)")
    return "\n".join(lineas)


def tabla_texto(encabezados, filas):
    """Tabla en texto plano con bordes, para consola y reportes."""
    anchos = [max(len(str(x)) for x in col) for col in zip(encabezados, *filas)]
    sep = "+" + "+".join("-" * (w + 2) for w in anchos) + "+"
    sep2 = "+" + "+".join("=" * (w + 2) for w in anchos) + "+"

    def linea(celdas):
        return "|" + "|".join(f" {str(c):^{w}} " for c, w in zip(celdas, anchos)) + "|"

    return "\n".join([sep, linea(encabezados), sep2] + [linea(f) for f in filas] + [sep])


def generar_reporte(afne, e1, afd, evaluaciones=()):
    S = "=" * 78
    r = [S, "  CONVERSIÓN DE AFN-ε A AFD — Lenguajes Formales y Autómatas",
         "  Integrantes: " + ", ".join(INTEGRANTES), S, "",
         "Notación:  →  estado inicial    *  estado final    ∅  conjunto vacío"
         f"    ε se captura como '{EPS}'", ""]

    r += ["1) TABLA DE TRANSICIÓN DEL AFN-ε ORIGINAL", "-" * 78, resumen_afne(afne), ""]
    r += [tabla_texto(*tabla_afne(afne)[:2]), ""]

    r += ["2) CÁLCULO DE LAS ε-CLÁUSULAS", "-" * 78]
    r += [tabla_texto(*tabla_clausuras(e1)[:2]), "", "Detalle del cálculo:", ""]
    r += e1.traza_clausuras

    r += ["3) AFN SIN TRANSICIONES VACÍAS  (δ'(q,a) = ε-cl(δ(ε-cl(q), a)))", "-" * 78,
          resumen_afn(e1), ""]
    r += [tabla_texto(*tabla_afn(e1)[:2]), "", "Detalle del cálculo:", ""]
    r += e1.traza_delta + e1.traza_finales + [""]

    r += ["4) AFD FINAL (construcción de subconjuntos)", "-" * 78, resumen_afd(afd), ""]
    r += [tabla_texto(*tabla_afd(afd)[:2]), "", "Detalle de la construcción:", ""]
    r += afd.pasos + [""]

    if evaluaciones:
        r += ["5) VALIDACIÓN DE CADENAS", "-" * 78]
        for ev in evaluaciones:
            res = "ACEPTADA" if ev.aceptada else "RECHAZADA"
            cad = ev.cadena if ev.cadena else EPS_TXT
            extra = f"  ({ev.error})" if ev.error else ""
            r.append(f"   {cad:<16} {res:<10} {afd.texto_recorrido(ev)}{extra}")
        r.append("")
    return "\n".join(r)


def afd_a_dot(afd):
    """Código DOT (Graphviz) del AFD:  dot -Tpng afd.dot -o afd.png"""
    def q(x):
        return '"' + x.replace('"', '\\"') + '"'

    l = ["digraph AFD {", "  rankdir=LR;",
         '  node [shape=circle, fontname="Helvetica"];',
         '  edge [fontname="Helvetica"];',
         '  __inicio [shape=point, width=0.01, label=""];']
    for n in afd.estados:
        attrs = []
        if n == afd.muerto:
            attrs += ['label="∅"', "style=dashed", "color=gray50", "fontcolor=gray40"]
        else:
            attrs.append(f'label="{n}\\n{afd.fmt(afd.subconjunto[n])}"')
        if n in afd.finales:
            attrs.append("shape=doublecircle")
        l.append(f"  {q(n)} [{', '.join(attrs)}];")
    l.append(f"  __inicio -> {q(afd.inicial)};")
    for (o, d), simbolos in afd.aristas().items():
        l.append(f'  {q(o)} -> {q(d)} [label="{", ".join(simbolos)}"];')
    l.append("}")
    return "\n".join(l)


# =============================================================================
#  EJEMPLOS PRECARGADOS
# =============================================================================

EJEMPLOS = [
    {
        "nombre": "Ejemplo 1 · a*b*c*  (clásico; genera estado muerto)",
        "estados": ["q0", "q1", "q2"],
        "alfabeto": ["a", "b", "c"],
        "inicial": "q0",
        "finales": ["q2"],
        "transiciones": {
            "q0": {"a": ["q0"], "@": ["q1"]},
            "q1": {"b": ["q1"], "@": ["q2"]},
            "q2": {"c": ["q2"]},
        },
        "pruebas": ["@", "abc", "aabbcc", "ac", "cb", "ba"],
    },
    {
        "nombre": "Ejemplo 2 · (a|b)*abb  (construcción de Thompson, 9 estados)",
        "estados": [f"q{i}" for i in range(9)],
        "alfabeto": ["a", "b"],
        "inicial": "q0",
        "finales": ["q8"],
        "transiciones": {
            "q0": {"@": ["q1", "q5"]},
            "q1": {"@": ["q2", "q3"]},
            "q2": {"a": ["q4"]},
            "q3": {"b": ["q4"]},
            "q4": {"@": ["q1", "q5"]},
            "q5": {"a": ["q6"]},
            "q6": {"b": ["q7"]},
            "q7": {"b": ["q8"]},
        },
        "pruebas": ["abb", "aabb", "babb", "ab", "abba", "@"],
    },
    {
        "nombre": "Ejemplo 3 · Números decimales  (signo +/-, dígito d, punto)",
        "estados": [f"q{i}" for i in range(6)],
        "alfabeto": ["+", "-", "d", "."],
        "inicial": "q0",
        "finales": ["q5"],
        "transiciones": {
            "q0": {"+": ["q1"], "-": ["q1"], "@": ["q1"]},
            "q1": {"d": ["q1", "q4"], ".": ["q2"]},
            "q2": {"d": ["q3"]},
            "q3": {"d": ["q3"], "@": ["q5"]},
            "q4": {".": ["q3"]},
        },
        "pruebas": ["d.d", "+dd.", "-.d", ".", "d", "+-d.d"],
    },
    {
        "nombre": "Ejemplo 4 · Σ={0,1}: termina en 01 o sólo tiene unos",
        "estados": [f"q{i}" for i in range(5)],
        "alfabeto": ["0", "1"],
        "inicial": "q0",
        "finales": ["q3", "q4"],
        "transiciones": {
            "q0": {"@": ["q1", "q4"]},
            "q1": {"0": ["q1", "q2"], "1": ["q1"]},
            "q2": {"1": ["q3"]},
            "q4": {"1": ["q4"]},
        },
        "pruebas": ["@", "111", "1101", "001", "10", "0"],
    },
]


# =============================================================================
#  GEOMETRÍA DEL DIBUJO DEL AFD (independiente de Tkinter: sirve para la
#  pantalla y para exportar SVG)
# =============================================================================

COLOR_ARISTA = "#546E7A"
COLOR_ARISTA_MUERTO = "#A0A0A0"
COLOR_RESALTE = "#E65100"


def _unit(dx, dy):
    d = math.hypot(dx, dy)
    return (dx / d, dy / d) if d > 1e-9 else (0.0, -1.0)


def _bezier2(p0, c, p1, n=28):
    pts = []
    for i in range(n + 1):
        t = i / n
        a, b, e = (1 - t) ** 2, 2 * (1 - t) * t, t * t
        pts.append((a * p0[0] + b * c[0] + e * p1[0], a * p0[1] + b * c[1] + e * p1[1]))
    return pts


def _bezier3(p0, c1, c2, p1, n=36):
    pts = []
    for i in range(n + 1):
        t = i / n
        a, b, c, e = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
        pts.append((a * p0[0] + b * c1[0] + c * c2[0] + e * p1[0],
                    a * p0[1] + b * c1[1] + c * c2[1] + e * p1[1]))
    return pts


def _linea_con_flecha(pts, color, grosor, guion, largo, ancho):
    """Devuelve [figura línea, figura punta de flecha] para una curva."""
    tip = pts[-1]
    linea = list(pts[:-1])
    while len(linea) > 1 and math.dist(linea[-1], tip) < largo:
        linea.pop()
    ref = linea[-1]
    ux, uy = _unit(tip[0] - ref[0], tip[1] - ref[1])
    base = (tip[0] - ux * largo, tip[1] - uy * largo)
    linea.append(base)
    punta = [tip, (base[0] - uy * ancho, base[1] + ux * ancho),
             (base[0] + uy * ancho, base[1] - ux * ancho)]
    return [{"t": "linea", "pts": linea, "color": color, "grosor": grosor, "guion": guion},
            {"t": "poligono", "pts": punta, "color": color}]


def disposicion_circular(estados):
    """Posiciones normalizadas (0..1) en círculo; el primero queda a la izquierda."""
    n = len(estados)
    if n == 1:
        return {estados[0]: (0.5, 0.5)}
    if n == 2:
        return {estados[0]: (0.3, 0.5), estados[1]: (0.7, 0.5)}
    pos = {}
    for i, q in enumerate(estados):
        ang = math.pi + 2 * math.pi * i / n
        pos[q] = (0.5 + 0.38 * math.cos(ang), 0.5 + 0.33 * math.sin(ang))
    return pos


def _caja(p, texto, esc, tam):
    """Rectángulo aproximado que ocupa un texto centrado en p."""
    w = (len(texto) * tam * 0.62 + 8) * esc
    h = tam * 1.7 * esc
    return (p[0] - w / 2, p[1] - h / 2, p[0] + w / 2, p[1] + h / 2)


def _solape(a, b):
    dx = min(a[2], b[2]) - max(a[0], b[0])
    dy = min(a[3], b[3]) - max(a[1], b[1])
    return dx * dy if dx > 0 and dy > 0 else 0.0


def figuras_afd(afd, pos, ancho, alto, esc=1.0, mostrar_sub=True, resaltar=(None, None)):
    """Lista de figuras simples (líneas, polígonos, círculos, textos)."""
    r = 25 * esc
    P = {q: (pos[q][0] * ancho, pos[q][1] * alto) for q in afd.estados}
    cx = sum(p[0] for p in P.values()) / len(P)
    cy = sum(p[1] for p in P.values()) / len(P)
    nodo_res, arista_res = resaltar
    aristas = afd.aristas()
    lineas, etiquetas, nodos = [], [], []

    # --- 1. Geometría de las aristas (curvas) ---
    geo = []   # (origen, destino, texto, puntos, posiciones candidatas para la etiqueta)
    for (o, d), simbolos in aristas.items():
        x, y = P[o]
        if o == d:                                   # lazo: sale hacia afuera del dibujo
            ux, uy = _unit(x - cx, y - cy)
            if math.hypot(x - cx, y - cy) < 1:
                ux, uy = 0.0, -1.0
            if o == afd.inicial and ux < -0.5:       # no chocar con la flecha de inicio
                ux, uy = 0.0, -1.0
            ang = math.atan2(uy, ux)
            p0 = (x + r * math.cos(ang + 0.5), y + r * math.sin(ang + 0.5))
            p3 = (x + r * math.cos(ang - 0.5), y + r * math.sin(ang - 0.5))
            c1 = (x + 3.1 * r * math.cos(ang + 0.8), y + 3.1 * r * math.sin(ang + 0.8))
            c2 = (x + 3.1 * r * math.cos(ang - 0.8), y + 3.1 * r * math.sin(ang - 0.8))
            pts = _bezier3(p0, c1, c2, p3)
            medio = pts[len(pts) // 2]
            candidatos = [(medio[0] + ux * 11 * esc, medio[1] + uy * 11 * esc)]
        else:
            x2, y2 = P[d]
            dist = math.hypot(x2 - x, y2 - y)
            if dist < 2 * r:
                continue
            ux, uy = _unit(x2 - x, y2 - y)
            curva = min(0.32 * dist, 90 * esc) if (d, o) in aristas else 0.0
            c = ((x + x2) / 2 - uy * curva, (y + y2) / 2 + ux * curva)
            a1 = _unit(c[0] - x, c[1] - y)
            a2 = _unit(c[0] - x2, c[1] - y2)
            ini = (x + a1[0] * r, y + a1[1] * r)
            fin = (x2 + a2[0] * (r + 1), y2 + a2[1] * (r + 1))
            pts = _bezier2(ini, c, fin)
            candidatos = [pts[i] for i in (14, 11, 17, 8, 20, 6, 22)]   # centro primero
        geo.append((o, d, ", ".join(simbolos), pts, candidatos))

    # --- 2. Obstáculos fijos: nodos, flecha de inicio y etiquetas de los lazos ---
    obstaculos = [(x - r - 2, y - r - 2, x + r + 2, y + r + 2) for x, y in P.values()]
    xi, yi = P[afd.inicial]
    obstaculos.append((xi - r - 50 * esc, yi - 20 * esc, xi - r, yi + 6 * esc))
    for o, d, texto, _, cand in geo:
        if o == d:
            obstaculos.append(_caja(cand[0], texto, esc, 10))
    puntos_curvas = [p for g in geo for p in g[3]]

    def costo(caja):
        dentro = sum(1 for (px, py) in puntos_curvas
                     if caja[0] - 2 <= px <= caja[2] + 2 and caja[1] - 2 <= py <= caja[3] + 2)
        return dentro * 400 + sum(_solape(caja, b) for b in obstaculos)

    # --- 3. Texto del subconjunto de cada estado, en el lado más despejado ---
    textos_sub = {}
    if mostrar_sub:
        for q in afd.estados:
            if q == afd.muerto:
                continue
            x, y = P[q]
            texto = afd.fmt(afd.subconjunto[q])
            mw = (len(texto) * 8 * 0.62 + 8) * esc / 2
            dy, dx, dg = r + 12 * esc, r + 4 * esc + mw, r * 0.72
            lados = [(x, y + dy), (x, y - dy), (x + dx, y), (x - dx, y),
                     (x + dg + mw, y + dg + 6 * esc), (x - dg - mw, y + dg + 6 * esc),
                     (x + dg + mw, y - dg - 6 * esc), (x - dg - mw, y - dg - 6 * esc)]
            mejor = min(enumerate(lados),
                        key=lambda il: costo(_caja(il[1], texto, esc, 8)) + il[0])[1]
            textos_sub[q] = (mejor, texto)
            obstaculos.append(_caja(mejor, texto, esc, 8))

    # --- 4. Dibujo de aristas y colocación de sus etiquetas (sin encimarse) ---
    for o, d, texto, pts, candidatos in sorted(geo, key=lambda g: g[0] != g[1]):
        activa = arista_res == (o, d)
        color = COLOR_RESALTE if activa else (COLOR_ARISTA_MUERTO if d == afd.muerto else COLOR_ARISTA)
        grosor = (3.4 if activa else 1.7) * esc
        guion = d == afd.muerto and o != d and not activa
        if o == d:
            mejor = candidatos[0]
        else:
            mejor = min(candidatos, key=lambda p: sum(_solape(_caja(p, texto, esc, 10), b)
                                                      for b in obstaculos))
            obstaculos.append(_caja(mejor, texto, esc, 10))
        lineas += _linea_con_flecha(pts, color, grosor, guion, 12 * esc, 5.5 * esc)
        etiquetas.append({"t": "texto", "p": mejor, "texto": texto, "tam": 10,
                          "negrita": True, "color": COLOR_RESALTE if activa else "#0D47A1",
                          "fondo": "#FFFFFF"})

    # --- 5. Nodos ---
    for q in afd.estados:
        x, y = P[q]
        muerto, final = q == afd.muerto, q in afd.finales
        if muerto:
            relleno, borde = "#EEEEEE", "#9E9E9E"
        elif final:
            relleno, borde = "#E8F5E9", "#2E7D32"
        else:
            relleno, borde = "#E3F2FD", "#1565C0"
        grosor = 2 * esc
        if q == nodo_res:
            relleno, borde, grosor = "#FFE082", COLOR_RESALTE, 3.5 * esc
        nodos.append({"t": "circulo", "c": (x, y), "r": r, "relleno": relleno, "borde": borde,
                      "grosor": grosor, "guion": muerto, "nodo": q})
        if final:
            nodos.append({"t": "circulo", "c": (x, y), "r": r - 5 * esc, "relleno": "",
                          "borde": borde, "grosor": grosor * 0.8, "guion": False, "nodo": q})
        nodos.append({"t": "texto", "p": (x, y), "texto": q, "tam": 12, "negrita": True,
                      "color": "#616161" if muerto else "#263238", "fondo": None, "nodo": q})
        if q in textos_sub:
            p, texto = textos_sub[q]
            nodos.append({"t": "texto", "p": p, "texto": texto, "tam": 8, "negrita": False,
                          "color": "#37474F", "fondo": "#FFFDE7"})
        if q == afd.inicial:                           # flecha de entrada
            pts = [(x - r - 46 * esc, y), (x - r - 1, y)]
            lineas += _linea_con_flecha(pts, "#263238", 2.2 * esc, False, 13 * esc, 6 * esc)
            etiquetas.append({"t": "texto", "p": (x - r - 30 * esc, y - 11 * esc),
                              "texto": "inicio", "tam": 8, "negrita": False,
                              "color": "#263238", "fondo": None})
    return lineas + nodos + etiquetas


def figuras_a_svg(figuras, ancho, alto):
    """Convierte las figuras a un documento SVG."""
    px = 96 / 72  # puntos tipográficos -> píxeles
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{ancho:.0f}" height="{alto:.0f}" '
         f'viewBox="0 0 {ancho:.0f} {alto:.0f}" font-family="Helvetica, Arial, sans-serif">',
         '<rect width="100%" height="100%" fill="white"/>']

    def pts_txt(pts):
        return " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)

    for f in figuras:
        if f["t"] == "linea":
            dash = ' stroke-dasharray="6,4"' if f["guion"] else ""
            s.append(f'<polyline points="{pts_txt(f["pts"])}" fill="none" stroke="{f["color"]}" '
                     f'stroke-width="{f["grosor"]:.1f}" stroke-linecap="round" '
                     f'stroke-linejoin="round"{dash}/>')
        elif f["t"] == "poligono":
            s.append(f'<polygon points="{pts_txt(f["pts"])}" fill="{f["color"]}"/>')
        elif f["t"] == "circulo":
            (x, y), dash = f["c"], ' stroke-dasharray="5,3"' if f["guion"] else ""
            s.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{f["r"]:.1f}" '
                     f'fill="{f["relleno"] or "none"}" stroke="{f["borde"]}" '
                     f'stroke-width="{f["grosor"]:.1f}"{dash}/>')
        elif f["t"] == "texto":
            (x, y), tam = f["p"], f["tam"] * px
            if f["fondo"]:
                w, h = len(f["texto"]) * tam * 0.6 + 6, tam * 1.35
                s.append(f'<rect x="{x - w / 2:.1f}" y="{y - h / 2:.1f}" width="{w:.1f}" '
                         f'height="{h:.1f}" rx="3" fill="{f["fondo"]}"/>')
            peso = ' font-weight="bold"' if f["negrita"] else ""
            s.append(f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="middle" '
                     f'dominant-baseline="central" font-size="{tam:.1f}"{peso} '
                     f'fill="{f["color"]}">{escape(f["texto"])}</text>')
    s.append("</svg>")
    return "\n".join(s)


# =============================================================================
#  INTERFAZ GRÁFICA (Tkinter)
# =============================================================================

COLORES_FILA = {
    "inicial": "#DCEBFB",
    "final": "#DFF3E1",
    "inicial_final": "#CDEDEA",
    "muerto": "#ECECEC",
    "aceptada": "#D4EFD6",
    "rechazada": "#FBD9D9",
}
FONDO = "#F4F6F9"
AZUL = "#1565C0"
AZUL_OSCURO = "#0D47A1"

if tk is not None:

    class MarcoDesplazable(ttk.Frame):
        """Frame con barras de desplazamiento (para la tabla de captura)."""

        def __init__(self, padre, fondo):
            super().__init__(padre)
            self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0, background=fondo)
            vs = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
            hs = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
            self.canvas.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
            self.canvas.grid(row=0, column=0, sticky="nsew")
            vs.grid(row=0, column=1, sticky="ns")
            hs.grid(row=1, column=0, sticky="ew")
            self.rowconfigure(0, weight=1)
            self.columnconfigure(0, weight=1)
            self.interior = ttk.Frame(self.canvas)
            self.canvas.create_window(0, 0, window=self.interior, anchor="nw")
            self.interior.bind("<Configure>", lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")))
            self.bind("<Enter>", lambda e: self._rueda(True))
            self.bind("<Leave>", lambda e: self._rueda(False))

        def _rueda(self, activar):
            if activar:
                self.bind_all("<MouseWheel>", self._girar)
                self.bind_all("<Button-4>", self._girar)
                self.bind_all("<Button-5>", self._girar)
            else:
                for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                    self.unbind_all(ev)

        def _girar(self, e):
            if getattr(e, "num", None) == 4 or getattr(e, "delta", 0) > 0:
                self.canvas.yview_scroll(-1, "units")
            else:
                self.canvas.yview_scroll(1, "units")

    class Tabla(ttk.Frame):
        """Treeview con columnas dinámicas y filas coloreadas."""

        def __init__(self, padre, app, altura=8):
            super().__init__(padre)
            self.app = app
            self.tv = ttk.Treeview(self, show="headings", height=altura, selectmode="browse")
            vs = ttk.Scrollbar(self, orient="vertical", command=self.tv.yview)
            hs = ttk.Scrollbar(self, orient="horizontal", command=self.tv.xview)
            self.tv.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
            self.tv.grid(row=0, column=0, sticky="nsew")
            vs.grid(row=0, column=1, sticky="ns")
            hs.grid(row=1, column=0, sticky="ew")
            self.rowconfigure(0, weight=1)
            self.columnconfigure(0, weight=1)
            for tag, color in COLORES_FILA.items():
                self.tv.tag_configure(tag, background=color)
            self.tv.tag_configure("muerto", foreground="#616161")
            self.tv.tag_configure("rechazada", foreground="#B71C1C")
            self.tv.tag_configure("aceptada", foreground="#1B5E20")

        def mostrar(self, encabezados, filas, tags=None, alinear_izq=()):
            f, fn = self.app.f_tabla, self.app.f_tabla_neg
            ids = [f"c{i}" for i in range(len(encabezados))]
            self.tv.delete(*self.tv.get_children())
            self.tv["columns"] = ids
            for i, (cid, enc) in enumerate(zip(ids, encabezados)):
                ancho = max([fn.measure(enc)] + [f.measure(str(fila[i])) for fila in filas]) + 30
                self.tv.heading(cid, text=enc, anchor="center")
                self.tv.column(cid, width=max(ancho, int(46 * self.app.esc)), minwidth=40,
                               anchor="w" if i in alinear_izq else "center", stretch=False)
            tags = tags or [""] * len(filas)
            for i, (fila, tag) in enumerate(zip(filas, tags)):
                self.tv.insert("", "end", iid=str(i), values=[str(x) for x in fila],
                               tags=(tag,) if tag else ())

    class App(tk.Tk):

        VELOCIDADES = {"Lenta": 1400, "Normal": 850, "Rápida": 400}

        def __init__(self):
            super().__init__()
            self.title("Conversión AFN-ε → AFD  ·  Lenguajes Formales y Autómatas")
            self.esc = max(1.0, self.winfo_fpixels("1i") / 96.0)
            ancho = min(int(1180 * self.esc), self.winfo_screenwidth() - 40)
            alto = min(int(780 * self.esc), self.winfo_screenheight() - 80)
            self.geometry(f"{ancho}x{alto}")
            self.minsize(int(900 * self.esc), int(580 * self.esc))
            self._estilos()

            self.afne = self.e1 = self.afd = None
            self.evaluaciones = []
            self.estados_grilla, self.alfabeto_grilla = [], []
            self.celdas = {}
            self.pos = {}
            self.resaltado = (None, None)
            self.arrastre = None
            self._anim = None
            self._anim_id = None

            self._menu()
            self._encabezado()
            self.barra = tk.Label(self, anchor="w", padx=10, pady=4, background="#E3E8EE",
                                  foreground="#37474F", font=self.f_normal)
            self.barra.pack(side="bottom", fill="x")
            self.nb = ttk.Notebook(self)
            self.nb.pack(fill="both", expand=True, padx=8, pady=(6, 4))

            self._tab_definicion()
            self._tab_afne()
            self._tab_clausuras()
            self._tab_afn()
            self._tab_afd()
            self._tab_validacion()
            self._tab_grafico()

            self.construir_grilla(["q0", "q1", "q2"], ["a", "b"])
            self.estado("Captura el AFN-ε o elige un ejemplo y presiona «Convertir» (F5).")
            self.bind("<F5>", lambda e: self.convertir())
            self.bind("<Control-o>", lambda e: self.abrir())
            self.bind("<Control-s>", lambda e: self.guardar())

        # ------------------------------------------------------------------
        #  Estilos
        # ------------------------------------------------------------------
        def _estilos(self):
            st = ttk.Style(self)
            if "clam" in st.theme_names():
                st.theme_use("clam")
            base = tkfont.nametofont("TkDefaultFont")
            base.configure(size=10)
            for nombre in ("TkTextFont", "TkMenuFont", "TkHeadingFont"):
                try:
                    tkfont.nametofont(nombre).configure(size=10)
                except tk.TclError:
                    pass
            fam = base.actual("family")
            self.f_normal = tkfont.Font(family=fam, size=10)
            self.f_negrita = tkfont.Font(family=fam, size=10, weight="bold")
            self.f_titulo = tkfont.Font(family=fam, size=17, weight="bold")
            self.f_grande = tkfont.Font(family=fam, size=13, weight="bold")
            self.f_tabla = tkfont.Font(family=fam, size=11)
            self.f_tabla_neg = tkfont.Font(family=fam, size=11, weight="bold")
            self.f_mono = tkfont.nametofont("TkFixedFont").copy()
            self.f_mono.configure(size=10)
            self.f_mono_neg = self.f_mono.copy()
            self.f_mono_neg.configure(weight="bold")
            self.familia = fam

            self.configure(background=FONDO)
            st.configure(".", background=FONDO, font=self.f_normal)
            for w in ("TFrame", "TLabel", "TCheckbutton", "TRadiobutton", "TLabelframe"):
                st.configure(w, background=FONDO)
            st.configure("TLabelframe.Label", background=FONDO, foreground=AZUL_OSCURO,
                         font=self.f_negrita)
            st.configure("Titulo.TLabel", font=self.f_grande, foreground=AZUL_OSCURO)
            st.configure("Sub.TLabel", foreground="#455A64")
            st.configure("Resumen.TLabel", font=self.f_mono_neg, foreground="#263238",
                         background="#FFFFFF", padding=(10, 8), relief="solid", borderwidth=1)
            st.configure("Eps.TLabel", font=self.f_negrita, foreground="#6A1B9A")
            st.configure("Error.TLabel", foreground="#C62828", font=self.f_negrita)
            st.configure("Ok.TLabel", foreground="#2E7D32", font=self.f_negrita)
            st.configure("Enc.TLabel", background=AZUL, foreground="white", font=self.f_negrita,
                         anchor="center", padding=(8, 5))
            st.configure("Estado.TLabel", font=self.f_tabla_neg, foreground=AZUL_OSCURO,
                         anchor="center")
            st.configure("Accent.TButton", font=self.f_grande, foreground="white",
                         background=AZUL, padding=(18, 8))
            st.map("Accent.TButton", background=[("pressed", AZUL_OSCURO), ("active", "#1976D2")])
            st.configure("TButton", padding=(10, 4))
            st.configure("Treeview", font=self.f_tabla, background="white",
                         fieldbackground="white",
                         rowheight=self.f_tabla.metrics("linespace") + int(10 * self.esc))
            st.configure("Treeview.Heading", font=self.f_tabla_neg, background=AZUL,
                         foreground="white", relief="flat", padding=(4, 5))
            st.map("Treeview.Heading", background=[("active", "#1976D2")])
            st.map("Treeview", background=[("selected", "#90CAF9")],
                   foreground=[("selected", "black")])
            st.configure("Error.TEntry", fieldbackground="#FFCDD2")
            st.configure("TNotebook", background=FONDO)
            st.configure("TNotebook.Tab", padding=(12, 6), font=self.f_negrita)

        # ------------------------------------------------------------------
        #  Menú, encabezado, barra de estado
        # ------------------------------------------------------------------
        def _menu(self):
            m = tk.Menu(self)
            arch = tk.Menu(m, tearoff=False)
            arch.add_command(label="Nuevo autómata", command=self.limpiar)
            arch.add_command(label="Abrir autómata…", accelerator="Ctrl+O", command=self.abrir)
            arch.add_command(label="Guardar autómata…", accelerator="Ctrl+S", command=self.guardar)
            arch.add_separator()
            arch.add_command(label="Exportar reporte de tablas (.txt)…", command=self.exportar_reporte)
            arch.add_command(label="Exportar gráfico del AFD (.svg)…", command=self.exportar_svg)
            arch.add_command(label="Exportar código DOT / Graphviz (.dot)…", command=self.exportar_dot)
            arch.add_separator()
            arch.add_command(label="Salir", command=self.destroy)
            m.add_cascade(label="Archivo", menu=arch)
            ej = tk.Menu(m, tearoff=False)
            for i, e in enumerate(EJEMPLOS):
                ej.add_command(label=e["nombre"], command=lambda i=i: self.cargar_ejemplo(i))
            m.add_cascade(label="Ejemplos", menu=ej)
            ay = tk.Menu(m, tearoff=False)
            ay.add_command(label="Cómo usar el programa", command=self.ayuda)
            ay.add_command(label="Acerca de", command=self.acerca)
            m.add_cascade(label="Ayuda", menu=ay)
            self.config(menu=m)

        def _encabezado(self):
            enc = tk.Frame(self, background=AZUL_OSCURO)
            enc.pack(fill="x")
            tk.Label(enc, text="Conversión de AFN-ε a AFD", font=self.f_titulo,
                     background=AZUL_OSCURO, foreground="white").pack(side="left", padx=16, pady=10)
            tk.Label(enc, text="Lenguajes Formales y Autómatas\nIntegrantes: " + ", ".join(INTEGRANTES),
                     font=self.f_normal, background=AZUL_OSCURO, foreground="#BBDEFB",
                     justify="right").pack(side="right", padx=16)

        def estado(self, texto, tipo="info"):
            colores = {"info": "#37474F", "ok": "#1B5E20", "error": "#B71C1C"}
            self.barra.configure(text=texto, foreground=colores.get(tipo, "#37474F"))

        # ------------------------------------------------------------------
        #  Widgets auxiliares
        # ------------------------------------------------------------------
        def _texto(self, padre, alto=8):
            marco = ttk.Frame(padre)
            txt = tk.Text(marco, wrap="none", height=alto, font=self.f_mono, relief="solid",
                          borderwidth=1, padx=10, pady=8, background="#FFFFFF",
                          foreground="#263238")
            vs = ttk.Scrollbar(marco, orient="vertical", command=txt.yview)
            hs = ttk.Scrollbar(marco, orient="horizontal", command=txt.xview)
            txt.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
            txt.grid(row=0, column=0, sticky="nsew")
            vs.grid(row=0, column=1, sticky="ns")
            hs.grid(row=1, column=0, sticky="ew")
            marco.rowconfigure(0, weight=1)
            marco.columnconfigure(0, weight=1)
            txt.tag_configure("titulo", font=self.f_mono_neg, foreground=AZUL_OSCURO)
            txt.tag_configure("resultado", font=self.f_mono_neg, foreground="#2E7D32")
            txt.tag_configure("ok", font=self.f_mono_neg, foreground="#1B5E20")
            txt.tag_configure("mal", font=self.f_mono_neg, foreground="#B71C1C")
            txt.configure(state="disabled")
            return marco, txt

        @staticmethod
        def _poner_texto(txt, lineas):
            """Escribe líneas en un Text; aplica estilo según su forma."""
            txt.configure(state="normal")
            txt.delete("1.0", "end")
            for linea in lineas:
                if isinstance(linea, tuple):
                    texto, tag = linea
                elif "⇒" in linea:
                    texto, tag = linea, "resultado"
                elif linea and not linea.startswith(" "):
                    texto, tag = linea, "titulo"
                else:
                    texto, tag = linea, ""
                txt.insert("end", texto + "\n", tag)
            txt.configure(state="disabled")

        def _leyenda(self, padre, muerto=False):
            f = ttk.Frame(padre)
            items = [("inicial", "→  estado inicial"), ("final", "*  estado final (aceptación)"),
                     ("inicial_final", "→*  inicial y final")]
            if muerto:
                items.append(("muerto", "∅  estado muerto (no aceptación)"))
            ttk.Label(f, text="Simbología:", style="Sub.TLabel").pack(side="left", padx=(0, 6))
            for tag, texto in items:
                tk.Label(f, text="   ", background=COLORES_FILA[tag], relief="solid",
                         borderwidth=1).pack(side="left", padx=(8, 4))
                ttk.Label(f, text=texto).pack(side="left")
            ttk.Label(f, text=f"      ∅ = conjunto vacío      ε se captura como '{EPS}'",
                      style="Sub.TLabel").pack(side="left")
            return f

        def _pestana(self, texto, titulo, explicacion):
            f = ttk.Frame(self.nb, padding=(12, 10))
            self.nb.add(f, text=texto, state="disabled")
            ttk.Label(f, text=titulo, style="Titulo.TLabel").pack(anchor="w")
            ttk.Label(f, text=explicacion, style="Sub.TLabel", wraplength=int(1050 * self.esc),
                      justify="left").pack(anchor="w", pady=(2, 8))
            return f

        # ------------------------------------------------------------------
        #  Pestaña 0: definición del AFN-ε
        # ------------------------------------------------------------------
        def _tab_definicion(self):
            f = ttk.Frame(self.nb, padding=(12, 10))
            self.nb.add(f, text=" Definición del AFN-ε ")

            p1 = ttk.LabelFrame(f, text=" Paso 1 · Quíntupla M = (Q, Σ, δ, q0, F): estados y alfabeto ",
                                padding=(12, 8))
            p1.pack(fill="x")
            ttk.Label(p1, text="Número de estados |Q|  (2 a 10):").grid(row=0, column=0, sticky="w")
            self.var_n = tk.StringVar(value="3")
            ttk.Spinbox(p1, from_=MIN_ESTADOS, to=MAX_ESTADOS, textvariable=self.var_n, width=5,
                        command=self.generar_tabla).grid(row=0, column=1, sticky="w", padx=(6, 22))
            ttk.Label(p1, text="Alfabeto Σ  (1 a 4 símbolos, separados por comas):").grid(
                row=0, column=2, sticky="w")
            self.var_alfa = tk.StringVar(value="a, b")
            e = ttk.Entry(p1, textvariable=self.var_alfa, width=16, font=self.f_tabla)
            e.grid(row=0, column=3, sticky="w", padx=(6, 12))
            e.bind("<Return>", lambda ev: self.generar_tabla())
            ttk.Button(p1, text="Generar / actualizar tabla", command=self.generar_tabla).grid(
                row=0, column=4, sticky="w")
            ttk.Label(p1, text=f"Transición vacía:  ε  se escribe con el carácter  ' {EPS} '  "
                               f"(reservado, no puede estar en Σ)", style="Eps.TLabel").grid(
                row=1, column=0, columnspan=5, sticky="w", pady=(8, 0))

            fila = ttk.Frame(p1)
            fila.grid(row=2, column=0, columnspan=5, sticky="w", pady=(8, 0))
            ttk.Label(fila, text="Ejemplos:").pack(side="left")
            self.var_ej = tk.StringVar()
            cb = ttk.Combobox(fila, textvariable=self.var_ej, state="readonly", width=58,
                              values=[e["nombre"] for e in EJEMPLOS])
            cb.pack(side="left", padx=6)
            cb.bind("<<ComboboxSelected>>", lambda ev: self.cargar_ejemplo(cb.current()))
            ttk.Button(fila, text="Abrir…", command=self.abrir).pack(side="left", padx=(14, 4))
            ttk.Button(fila, text="Guardar…", command=self.guardar).pack(side="left", padx=4)
            ttk.Button(fila, text="Limpiar", command=self.limpiar).pack(side="left", padx=4)

            abajo = ttk.Frame(f)
            abajo.pack(side="bottom", fill="x", pady=(8, 0))
            ttk.Button(abajo, text="Convertir  AFN-ε  →  AFD   ▶", style="Accent.TButton",
                       command=self.convertir).pack(side="left")
            self.lbl_error = ttk.Label(abajo, text="", style="Error.TLabel",
                                       wraplength=int(760 * self.esc), justify="left")
            self.lbl_error.pack(side="left", padx=14)

            p2 = ttk.LabelFrame(f, text=" Paso 2 · Función de transición δ, estado inicial q0 y "
                                        "estados finales F ", padding=(12, 8))
            p2.pack(fill="both", expand=True, pady=(10, 0))
            ttk.Label(p2, style="Sub.TLabel", justify="left", text=(
                "•  Elige UN estado inicial (columna «Inicial») y marca uno o más estados finales "
                "(columna «Final»).\n"
                "•  En cada casilla escribe los estados destino separados por comas, por ejemplo:  "
                "q1, q2     (también se acepta  1, 2).\n"
                f"•  Deja la casilla vacía si no hay transición (∅).   La última columna es ε ({EPS})."
            )).pack(anchor="w", pady=(0, 8))
            self.marco_grilla = MarcoDesplazable(p2, FONDO)
            self.marco_grilla.pack(fill="both", expand=True)

        def construir_grilla(self, estados, alfabeto, valores=None, inicial=None, finales=()):
            """(Re)construye la tabla de captura conservando lo que se pueda."""
            g = self.marco_grilla.interior
            for w in g.winfo_children():
                w.destroy()
            valores = valores or {}
            self.estados_grilla, self.alfabeto_grilla = list(estados), list(alfabeto)
            self.var_n.set(str(len(estados)))
            self.var_alfa.set(", ".join(alfabeto))

            simbolos = alfabeto + [EPS]
            encabezados = ["Estado", "Inicial", "Final"] + \
                          [f"δ( · , {a})" for a in alfabeto] + [f"δ( · , ε)   [{EPS}]"]
            for j, t in enumerate(encabezados):
                ttk.Label(g, text=t, style="Enc.TLabel").grid(row=0, column=j, sticky="nsew",
                                                              padx=1, pady=(0, 3))
            self.var_inicial = tk.StringVar(value=inicial if inicial in estados else estados[0])
            self.vars_final = {}
            self.celdas = {}
            for i, q in enumerate(estados, start=1):
                ttk.Label(g, text=q, style="Estado.TLabel", width=6).grid(row=i, column=0, padx=1, pady=2)
                ttk.Radiobutton(g, variable=self.var_inicial, value=q).grid(row=i, column=1)
                v = tk.BooleanVar(value=q in finales)
                self.vars_final[q] = v
                ttk.Checkbutton(g, variable=v).grid(row=i, column=2)
                for j, s in enumerate(simbolos):
                    e = ttk.Entry(g, width=15, font=self.f_tabla, justify="center")
                    e.insert(0, valores.get((q, s), ""))
                    e.grid(row=i, column=3 + j, padx=2, pady=2, ipady=2)
                    e.bind("<Return>", lambda ev: ev.widget.tk_focusNext().focus_set())
                    e.bind("<Key>", lambda ev: ev.widget.configure(style="TEntry"))
                    self.celdas[(q, s)] = e

        def _valores_grilla(self):
            return {k: e.get() for k, e in self.celdas.items()}

        def generar_tabla(self):
            """Aplica el número de estados y el alfabeto, conservando lo capturado."""
            try:
                try:
                    n = int(self.var_n.get())
                except ValueError:
                    raise ErrorAutomata("El número de estados debe ser un entero entre 2 y 10.")
                if not MIN_ESTADOS <= n <= MAX_ESTADOS:
                    raise ErrorAutomata(f"El número de estados debe estar entre {MIN_ESTADOS} "
                                        f"y {MAX_ESTADOS}.")
                alfabeto = parsear_alfabeto(self.var_alfa.get())
            except ErrorAutomata as ex:
                self._error(str(ex))
                return False
            estados = self.estados_grilla[:n]
            i = 0
            while len(estados) < n:
                if f"q{i}" not in estados:
                    estados.append(f"q{i}")
                i += 1
            finales = [q for q, v in self.vars_final.items() if v.get()]
            self.construir_grilla(estados, alfabeto, self._valores_grilla(),
                                  self.var_inicial.get(), finales)
            self.lbl_error.configure(text="")
            return True

        def _configuracion_cambio(self):
            try:
                return (int(self.var_n.get()) != len(self.estados_grilla)
                        or parsear_alfabeto(self.var_alfa.get()) != self.alfabeto_grilla)
            except (ValueError, ErrorAutomata):
                return True

        def leer_afne(self):
            estados, alfabeto = self.estados_grilla, self.alfabeto_grilla
            trans = {}
            for q in estados:
                trans[q] = {}
                for s in alfabeto + [EPS]:
                    trans[q][s] = parsear_destinos(self.celdas[(q, s)].get(), estados, (q, s))
            finales = [q for q in estados if self.vars_final[q].get()]
            if not finales:
                raise ErrorAutomata("Marca al menos un estado final en la columna «Final».")
            return AFNE(estados, alfabeto, trans, self.var_inicial.get(), finales)

        def _invalidar_resultados(self):
            """Oculta resultados de una conversión anterior (ya no corresponden)."""
            self._detener_animacion()
            self.afne = self.e1 = self.afd = None
            self.evaluaciones = []
            for i in range(1, 7):
                self.nb.tab(i, state="disabled")

        def _error(self, mensaje, celda=None):
            self._invalidar_resultados()
            self.lbl_error.configure(text="⚠ " + mensaje)
            self.estado(mensaje, "error")
            if celda and celda in self.celdas:
                e = self.celdas[celda]
                e.configure(style="Error.TEntry")
                e.focus_set()
            self.nb.select(0)
            self.bell()

        def limpiar(self):
            try:
                n = min(max(int(self.var_n.get()), MIN_ESTADOS), MAX_ESTADOS)
            except ValueError:
                n = 3
            try:
                alfabeto = parsear_alfabeto(self.var_alfa.get())
            except ErrorAutomata:
                alfabeto = ["a", "b"]
            self.construir_grilla([f"q{i}" for i in range(n)], alfabeto)
            self._invalidar_resultados()
            self.var_ej.set("")
            self.lbl_error.configure(text="")
            self.estado("Tabla limpia. Captura un nuevo AFN-ε.")

        def cargar_dict(self, d, nombre="archivo"):
            afne = AFNE.desde_dict(d)          # valida antes de mostrar
            valores = {(q, s): ", ".join(afne.ordenar(afne.delta[q][s]))
                       for q in afne.estados for s in afne.alfabeto + [EPS]}
            self.construir_grilla(afne.estados, afne.alfabeto, valores, afne.inicial, afne.finales)
            self._invalidar_resultados()
            if d.get("pruebas"):
                self.txt_cadenas.delete("1.0", "end")
                self.txt_cadenas.insert("1.0", "\n".join(d["pruebas"]))
            self.lbl_error.configure(text="")
            self.nb.select(0)
            self.estado(f"Se cargó: {nombre}.  Revisa la tabla y presiona «Convertir» (F5).", "ok")

        def cargar_ejemplo(self, i):
            if i < 0:
                return
            self.var_ej.set(EJEMPLOS[i]["nombre"])
            self.cargar_dict(EJEMPLOS[i], EJEMPLOS[i]["nombre"])

        def abrir(self):
            ruta = filedialog.askopenfilename(
                title="Abrir autómata", filetypes=[("Autómata (JSON)", "*.json"), ("Todos", "*.*")])
            if not ruta:
                return
            try:
                with open(ruta, encoding="utf-8") as fh:
                    self.cargar_dict(json.load(fh), ruta)
            except (OSError, ValueError) as ex:
                messagebox.showerror("No se pudo abrir el archivo", str(ex))

        def guardar(self):
            try:
                if self._configuracion_cambio() and not self.generar_tabla():
                    return
                afne = self.leer_afne()
            except ErrorAutomata as ex:
                self._error(str(ex), ex.celda)
                return
            ruta = filedialog.asksaveasfilename(
                title="Guardar autómata", defaultextension=".json",
                filetypes=[("Autómata (JSON)", "*.json")])
            if ruta:
                with open(ruta, "w", encoding="utf-8") as fh:
                    json.dump(afne.a_dict(), fh, ensure_ascii=False, indent=2)
                self.estado(f"Autómata guardado en {ruta}", "ok")

        # ------------------------------------------------------------------
        #  Conversión
        # ------------------------------------------------------------------
        def convertir(self):
            for e in self.celdas.values():
                e.configure(style="TEntry")
            if self._configuracion_cambio() and not self.generar_tabla():
                return
            try:
                afne = self.leer_afne()
                e1, afd = convertir(afne)
            except ErrorAutomata as ex:
                self._error(str(ex), ex.celda)
                return
            self.lbl_error.configure(text="")
            self.afne, self.e1, self.afd = afne, e1, afd
            self.evaluaciones = []
            self._detener_animacion()
            self.pos = disposicion_circular(afd.estados)
            self.resaltado = (None, None)
            self._llenar_resultados()
            for i in range(1, 7):
                self.nb.tab(i, state="normal")
            self.nb.select(1)
            muerto = " (incluye estado muerto ∅)" if afd.muerto else ""
            self.estado(f"Conversión completada: AFN-ε de {len(afne.estados)} estados → AFD de "
                        f"{len(afd.estados)} estados{muerto}.  Revisa las pestañas 1 a 6.", "ok")

        def _llenar_resultados(self):
            afne, e1, afd = self.afne, self.e1, self.afd
            self.lbl_res_afne.configure(text=resumen_afne(afne))
            self.tabla_afne.mostrar(*tabla_afne(afne))
            self.tabla_cl.mostrar(*tabla_clausuras(e1), alinear_izq=(1,))
            self._poner_texto(self.txt_cl, e1.traza_clausuras)
            self.lbl_res_afn.configure(text=resumen_afn(e1))
            self.tabla_afn.mostrar(*tabla_afn(e1))
            self._poner_texto(self.txt_afn, e1.traza_finales + [""] + e1.traza_delta)
            self.lbl_res_afd.configure(text=resumen_afd(afd))
            self._mostrar_tabla_afd()
            self._poner_texto(self.txt_afd, afd.pasos)
            self.lbl_val_info.configure(
                text=f"Σ = {{{', '.join(afd.alfabeto)}}}.  Escribe una o más cadenas (una por línea, "
                     f"o separadas por espacios o comas).  Para la cadena vacía escribe  {EPS}  .")
            self.tabla_val.mostrar(["#", "Cadena", "Resultado", "Recorrido en el AFD",
                                    "Verificación AFN-ε"], [])
            self._poner_texto(self.txt_val, [])
            self.lbl_anim.configure(text="Escribe una cadena y presiona «Animar recorrido».",
                                    foreground="#37474F")
            self.dibujar()

        def _mostrar_tabla_afd(self):
            if self.afd:
                self.tabla_afd.mostrar(*tabla_afd(self.afd, self.var_como_sub.get()),
                                       alinear_izq=(2,))

        # ------------------------------------------------------------------
        #  Pestañas de resultados
        # ------------------------------------------------------------------
        def _tab_afne(self):
            f = self._pestana(" 1 · AFN-ε original ", "Tabla de transición del AFN-ε original",
                              "Así quedó capturado el autómata. Cada casilla es el conjunto "
                              "δ(q, símbolo); la última columna son las transiciones vacías ε.")
            self.lbl_res_afne = ttk.Label(f, style="Resumen.TLabel")
            self.lbl_res_afne.pack(anchor="w", fill="x", pady=(0, 8))
            self.tabla_afne = Tabla(f, self, altura=11)
            self.tabla_afne.pack(fill="both", expand=True)
            self._leyenda(f).pack(anchor="w", pady=(8, 0))

        def _tab_clausuras(self):
            f = self._pestana(" 2 · ε-cláusulas ", "Cálculo de las ε-cláusulas (Etapa 1)",
                              "ε-cl(q) es el conjunto de estados alcanzables desde q usando sólo "
                              "transiciones vacías (incluye al propio q). Abajo se muestra el "
                              "recorrido seguido para calcular cada una.")
            pan = ttk.PanedWindow(f, orient="vertical")
            pan.pack(fill="both", expand=True)
            self.tabla_cl = Tabla(pan, self, altura=8)
            marco, self.txt_cl = self._texto(pan)
            pan.add(self.tabla_cl, weight=1)
            pan.add(marco, weight=1)

        def _tab_afn(self):
            f = self._pestana(" 3 · AFN sin ε ", "AFN resultante, sin transiciones vacías (Etapa 1)",
                              "δ'(q, a) = ε-cl( δ( ε-cl(q), a ) ).   F' contiene a todo estado "
                              "cuya ε-cláusula incluye algún estado final original.   El estado "
                              "inicial se conserva.")
            self.lbl_res_afn = ttk.Label(f, style="Resumen.TLabel")
            self.lbl_res_afn.pack(anchor="w", fill="x", pady=(0, 8))
            pan = ttk.PanedWindow(f, orient="vertical")
            pan.pack(fill="both", expand=True)
            arriba = ttk.Frame(pan)
            self.tabla_afn = Tabla(arriba, self, altura=8)
            self.tabla_afn.pack(fill="both", expand=True)
            self._leyenda(arriba).pack(anchor="w", pady=(6, 4))
            marco, self.txt_afn = self._texto(pan)
            pan.add(arriba, weight=1)
            pan.add(marco, weight=1)

        def _tab_afd(self):
            f = self._pestana(" 4 · AFD final ", "AFD final: construcción de subconjuntos (Etapa 2)",
                              "Se parte de ε-cl(q0). Cada estado del AFD es un subconjunto de "
                              "estados del AFN; es final si contiene algún estado de F'. Si una "
                              "transición lleva al conjunto vacío aparece el estado muerto ∅.")
            self.lbl_res_afd = ttk.Label(f, style="Resumen.TLabel", justify="left")
            self.lbl_res_afd.pack(anchor="w", fill="x", pady=(0, 6))
            barra = ttk.Frame(f)
            barra.pack(fill="x", pady=(0, 6))
            self.var_como_sub = tk.BooleanVar(value=False)
            ttk.Checkbutton(barra, text="Mostrar los destinos como subconjuntos",
                            variable=self.var_como_sub,
                            command=self._mostrar_tabla_afd).pack(side="left")
            ttk.Button(barra, text="Ver gráfico del AFD ▶",
                       command=lambda: self.nb.select(6)).pack(side="right")
            ttk.Button(barra, text="Probar cadenas ▶",
                       command=lambda: self.nb.select(5)).pack(side="right", padx=6)
            ttk.Button(barra, text="Exportar reporte (.txt)…",
                       command=self.exportar_reporte).pack(side="right")
            pan = ttk.PanedWindow(f, orient="vertical")
            pan.pack(fill="both", expand=True)
            arriba = ttk.Frame(pan)
            self.tabla_afd = Tabla(arriba, self, altura=8)
            self.tabla_afd.pack(fill="both", expand=True)
            self._leyenda(arriba, muerto=True).pack(anchor="w", pady=(6, 4))
            marco, self.txt_afd = self._texto(pan)
            pan.add(arriba, weight=3)
            pan.add(marco, weight=2)

        # ------------------------------------------------------------------
        #  Pestaña 5: validación de cadenas
        # ------------------------------------------------------------------
        def _tab_validacion(self):
            f = self._pestana(" 5 · Validar cadenas ", "Validación de cadenas con el AFD",
                              "Cada cadena se recorre en el AFD desde el estado inicial. Es "
                              "ACEPTADA si termina en un estado final. Como comprobación, también "
                              "se simula el AFN-ε original: ambos deben coincidir.")
            self.lbl_val_info = ttk.Label(f, text="", style="Eps.TLabel")
            self.lbl_val_info.pack(anchor="w")
            fila = ttk.Frame(f)
            fila.pack(fill="x", pady=(6, 8))
            self.txt_cadenas = tk.Text(fila, height=4, width=40, font=self.f_tabla, relief="solid",
                                       borderwidth=1, padx=8, pady=6)
            self.txt_cadenas.pack(side="left")
            self.txt_cadenas.bind("<Control-Return>", lambda e: (self.evaluar_cadenas(), "break")[1])
            botones = ttk.Frame(fila)
            botones.pack(side="left", padx=12, anchor="n")
            ttk.Button(botones, text="Evaluar cadenas  (Ctrl+Enter)", style="Accent.TButton",
                       command=self.evaluar_cadenas).pack(fill="x")
            ttk.Button(botones, text="Ver recorrido animado en el gráfico ▶",
                       command=self.animar_seleccion).pack(fill="x", pady=(8, 0))
            ttk.Button(botones, text="Borrar cadenas",
                       command=lambda: self.txt_cadenas.delete("1.0", "end")).pack(fill="x", pady=(6, 0))

            pan = ttk.PanedWindow(f, orient="vertical")
            pan.pack(fill="both", expand=True)
            self.tabla_val = Tabla(pan, self, altura=6)
            self.tabla_val.tv.bind("<<TreeviewSelect>>", lambda e: self._detalle_cadena())
            self.tabla_val.tv.bind("<Double-1>", lambda e: self.animar_seleccion())
            marco, self.txt_val = self._texto(pan, alto=7)
            pan.add(self.tabla_val, weight=1)
            pan.add(marco, weight=1)

        def evaluar_cadenas(self):
            if not self.afd:
                return
            texto = self.txt_cadenas.get("1.0", "end").strip()
            if not texto:
                self.estado("Escribe al menos una cadena (usa @ para la cadena vacía).", "error")
                return
            cadenas = ["" if t in (EPS, EPS_TXT) else t for t in re.split(r"[\s,]+", texto) if t]
            self.evaluaciones = [self.afd.evaluar(c) for c in cadenas]
            filas, tags = [], []
            for i, ev in enumerate(self.evaluaciones, start=1):
                ok_afne = self.afne.acepta(ev.cadena)
                res = "✔ ACEPTADA" if ev.aceptada else "✖ RECHAZADA"
                if ev.error:
                    res += " (símbolo fuera de Σ)"
                verif = ("ACEPTADA" if ok_afne else "RECHAZADA") + \
                        (" ✓ coincide" if ok_afne == ev.aceptada else " ✗ NO coincide")
                filas.append([i, ev.cadena or EPS_TXT, res, self.afd.texto_recorrido(ev), verif])
                tags.append("aceptada" if ev.aceptada else "rechazada")
            self.tabla_val.mostrar(["#", "Cadena", "Resultado", "Recorrido en el AFD",
                                    "Verificación AFN-ε"], filas, tags, alinear_izq=(3,))
            self.tabla_val.tv.selection_set("0")
            n_ok = sum(ev.aceptada for ev in self.evaluaciones)
            self.estado(f"{len(cadenas)} cadena(s) evaluada(s): {n_ok} aceptada(s), "
                        f"{len(cadenas) - n_ok} rechazada(s).", "ok")

        def _evaluacion_seleccionada(self):
            sel = self.tabla_val.tv.selection()
            if not sel or not self.evaluaciones:
                return None
            return self.evaluaciones[int(sel[0])]

        def _detalle_cadena(self):
            ev = self._evaluacion_seleccionada()
            if not ev:
                return
            afd = self.afd
            lineas = [f"Cadena: \"{ev.cadena}\"  (longitud {len(ev.cadena)})" if ev.cadena
                      else "Cadena vacía ε  (longitud 0)",
                      f"   Estado inicial: {afd.inicial} = {afd.fmt(afd.subconjunto[afd.inicial])}"]
            for k, (o, c, d) in enumerate(ev.pasos, start=1):
                lineas.append(f"   {k:>2}. δ({o}, '{c}') = {d}   {afd.fmt(afd.subconjunto[d])}")
            if ev.error:
                lineas.append((f"   ✖ Se detiene: {ev.error}.", "mal"))
                lineas.append(("Resultado: RECHAZADA", "mal"))
            else:
                es = "SÍ es estado final" if ev.aceptada else "NO es estado final"
                lineas.append(f"   Termina en {ev.final}, que {es}.")
                lineas.append(("Resultado: ACEPTADA ✔", "ok") if ev.aceptada
                              else ("Resultado: RECHAZADA ✖", "mal"))
            ok_afne = self.afne.acepta(ev.cadena)
            lineas.append(f"   Comprobación con el AFN-ε original: "
                          f"{'ACEPTADA' if ok_afne else 'RECHAZADA'}"
                          f"{' (coincide)' if ok_afne == ev.aceptada else ' (NO coincide)'}")
            self._poner_texto(self.txt_val, lineas)

        def animar_seleccion(self):
            ev = self._evaluacion_seleccionada()
            if ev is None:
                self.estado("Primero evalúa las cadenas y selecciona una fila.", "error")
                return
            self.var_cad_graf.set(ev.cadena if ev.cadena else EPS)
            self.nb.select(6)
            self.after(250, self.animar)

        # ------------------------------------------------------------------
        #  Pestaña 6: gráfico del AFD (punto extra)
        # ------------------------------------------------------------------
        def _tab_grafico(self):
            f = self._pestana(" 6 · Gráfico del AFD ", "Representación gráfica del AFD final",
                              "Círculo doble = estado final.  Flecha «inicio» = estado inicial.  "
                              "Gris punteado = estado muerto ∅.  Arrastra los estados con el ratón "
                              "para acomodarlos.")
            barra = ttk.Frame(f)
            barra.pack(fill="x", pady=(0, 6))
            ttk.Label(barra, text="Cadena:").pack(side="left")
            self.var_cad_graf = tk.StringVar()
            e = ttk.Entry(barra, textvariable=self.var_cad_graf, width=18, font=self.f_tabla)
            e.pack(side="left", padx=6)
            e.bind("<Return>", lambda ev: self.animar())
            ttk.Button(barra, text="▶ Animar recorrido", command=self.animar).pack(side="left")
            ttk.Button(barra, text="■ Detener", command=self._detener_animacion).pack(side="left", padx=4)
            ttk.Label(barra, text="Velocidad:").pack(side="left", padx=(10, 4))
            self.var_vel = tk.StringVar(value="Normal")
            ttk.Combobox(barra, textvariable=self.var_vel, values=list(self.VELOCIDADES),
                         state="readonly", width=8).pack(side="left")
            ttk.Button(barra, text="Guardar DOT…", command=self.exportar_dot).pack(side="right")
            ttk.Button(barra, text="Guardar SVG…", command=self.exportar_svg).pack(side="right", padx=4)
            ttk.Button(barra, text="Reacomodar", command=self.reacomodar).pack(side="right", padx=4)

            fila = ttk.Frame(f)
            fila.pack(fill="x", pady=(0, 6))
            self.var_mostrar_sub = tk.BooleanVar(value=True)
            ttk.Checkbutton(fila, text="Mostrar subconjuntos", variable=self.var_mostrar_sub,
                            command=self.dibujar).pack(side="right")
            self.lbl_anim = tk.Label(fila, text="", font=self.f_grande, anchor="w", background=FONDO)
            self.lbl_anim.pack(side="left", fill="x", expand=True)
            self.canvas = tk.Canvas(f, background="white", highlightthickness=1,
                                    highlightbackground="#B0BEC5")
            self.canvas.pack(fill="both", expand=True)
            self.canvas.bind("<Configure>", lambda e: self.dibujar())
            self.canvas.bind("<ButtonPress-1>", self._presionar)
            self.canvas.bind("<B1-Motion>", self._arrastrar)
            self.canvas.bind("<ButtonRelease-1>", lambda e: setattr(self, "arrastre", None))
            self.canvas.bind("<Motion>", self._cursor)

        def _figuras(self, ancho, alto):
            return figuras_afd(self.afd, self.pos, ancho, alto, self.esc,
                               self.var_mostrar_sub.get(), self.resaltado)

        def dibujar(self):
            c = self.canvas
            c.delete("all")
            w, h = c.winfo_width(), c.winfo_height()
            if not self.afd or w < 60 or h < 60:
                return
            for fig in self._figuras(w, h):
                tags = ("nodo", "nodo:" + fig["nodo"]) if "nodo" in fig else ()
                t = fig["t"]
                if t == "linea":
                    pts = [v for p in fig["pts"] for v in p]
                    c.create_line(*pts, fill=fig["color"], width=fig["grosor"],
                                  dash=(6, 4) if fig["guion"] else (), capstyle="round",
                                  joinstyle="round")
                elif t == "poligono":
                    c.create_polygon(*[v for p in fig["pts"] for v in p], fill=fig["color"],
                                     outline=fig["color"])
                elif t == "circulo":
                    (x, y), r = fig["c"], fig["r"]
                    c.create_oval(x - r, y - r, x + r, y + r, fill=fig["relleno"],
                                  outline=fig["borde"], width=fig["grosor"],
                                  dash=(5, 3) if fig["guion"] else (), tags=tags)
                elif t == "texto":
                    fuente = (self.familia, fig["tam"], "bold" if fig["negrita"] else "normal")
                    tid = c.create_text(*fig["p"], text=fig["texto"], fill=fig["color"],
                                        font=fuente, tags=tags)
                    if fig["fondo"]:
                        x1, y1, x2, y2 = c.bbox(tid)
                        rid = c.create_rectangle(x1 - 3, y1 - 1, x2 + 3, y2 + 1,
                                                 fill=fig["fondo"], outline="")
                        c.tag_lower(rid, tid)

        def _nodo_en(self, evento):
            for item in self.canvas.find_overlapping(evento.x - 1, evento.y - 1,
                                                     evento.x + 1, evento.y + 1)[::-1]:
                for t in self.canvas.gettags(item):
                    if t.startswith("nodo:"):
                        return t[5:]
            return None

        def _presionar(self, e):
            self.arrastre = self._nodo_en(e)

        def _arrastrar(self, e):
            if not self.arrastre:
                return
            w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
            m = 30 * self.esc
            x = min(max(e.x, m), w - m)
            y = min(max(e.y, m), h - m)
            self.pos[self.arrastre] = (x / w, y / h)
            self.dibujar()

        def _cursor(self, e):
            self.canvas.configure(cursor="fleur" if self._nodo_en(e) else "")

        def reacomodar(self):
            if self.afd:
                self.pos = disposicion_circular(self.afd.estados)
                self.dibujar()

        def animar(self):
            if not self.afd:
                return
            self._detener_animacion()
            cadena = self.var_cad_graf.get().strip()
            if cadena in (EPS, EPS_TXT):
                cadena = ""
            ev = self.afd.evaluar(cadena)
            if ev.error:
                self.lbl_anim.configure(text=f"✖ No se puede animar: {ev.error}.",
                                        foreground="#B71C1C")
                return
            self._anim = {"ev": ev, "i": 0}
            self._paso_animacion()

        def _paso_animacion(self):
            ev, i = self._anim["ev"], self._anim["i"]
            cad = ev.cadena
            mostrar = cad if cad else EPS_TXT
            if i == 0:
                self.resaltado = (self.afd.inicial, None)
                texto = f"Cadena «{mostrar}»:  inicio en {self.afd.inicial}"
            else:
                o, c, d = ev.pasos[i - 1]
                self.resaltado = (d, (o, d))
                texto = (f"Paso {i}/{len(ev.pasos)}:   δ({o}, '{c}') = {d}        "
                         f"leído: {cad[:i]}  ·  falta: {cad[i:] or '—'}")
            self.lbl_anim.configure(text=texto, foreground=AZUL_OSCURO)
            self.dibujar()
            if i < len(ev.pasos):
                self._anim["i"] += 1
                self._anim_id = self.after(self.VELOCIDADES[self.var_vel.get()], self._paso_animacion)
            else:
                self._anim_id = self.after(self.VELOCIDADES[self.var_vel.get()] // 2,
                                           lambda: self._fin_animacion(ev))

        def _fin_animacion(self, ev):
            mostrar = ev.cadena if ev.cadena else EPS_TXT
            if ev.aceptada:
                self.lbl_anim.configure(text=f"✔ «{mostrar}» ACEPTADA: termina en {ev.final}, "
                                             f"que es estado final.", foreground="#1B5E20")
            else:
                self.lbl_anim.configure(text=f"✖ «{mostrar}» RECHAZADA: termina en {ev.final}, "
                                             f"que no es estado final.", foreground="#B71C1C")
            self._anim_id = None

        def _detener_animacion(self):
            if self._anim_id:
                self.after_cancel(self._anim_id)
                self._anim_id = None
            if self.resaltado != (None, None):
                self.resaltado = (None, None)
                self.dibujar()

        # ------------------------------------------------------------------
        #  Exportaciones
        # ------------------------------------------------------------------
        def _requiere_afd(self):
            if not self.afd:
                messagebox.showinfo("Primero convierte", "Primero presiona «Convertir AFN-ε → AFD».")
                return False
            return True

        def _guardar_texto(self, titulo, ext, tipo, contenido):
            ruta = filedialog.asksaveasfilename(title=titulo, defaultextension=ext,
                                                filetypes=[(tipo, "*" + ext)])
            if ruta:
                with open(ruta, "w", encoding="utf-8") as fh:
                    fh.write(contenido)
                self.estado(f"Archivo guardado: {ruta}", "ok")

        def exportar_reporte(self):
            if self._requiere_afd():
                self._guardar_texto("Exportar reporte", ".txt", "Texto", generar_reporte(
                    self.afne, self.e1, self.afd, self.evaluaciones))

        def exportar_dot(self):
            if self._requiere_afd():
                self._guardar_texto("Guardar código DOT", ".dot", "Graphviz DOT",
                                    afd_a_dot(self.afd))

        def exportar_svg(self):
            if self._requiere_afd():
                w = max(self.canvas.winfo_width(), int(900 * self.esc))
                h = max(self.canvas.winfo_height(), int(520 * self.esc))
                figs = figuras_afd(self.afd, self.pos, w, h, self.esc,
                                   self.var_mostrar_sub.get(), (None, None))
                self._guardar_texto("Guardar imagen SVG", ".svg", "Imagen SVG",
                                    figuras_a_svg(figs, w, h))

        # ------------------------------------------------------------------
        #  Ayuda
        # ------------------------------------------------------------------
        def ayuda(self):
            messagebox.showinfo("Cómo usar el programa", (
                "1. En «Definición del AFN-ε» indica el número de estados (2–10) y el alfabeto Σ "
                "(máx. 4 símbolos) y presiona «Generar / actualizar tabla».\n\n"
                "2. Elige el estado inicial, marca los finales y llena δ: en cada casilla escribe "
                f"los destinos separados por comas (ej. q1, q2). La columna ε usa el carácter '{EPS}'. "
                "Casilla vacía = ∅.\n\n"
                "3. Presiona «Convertir» (o F5). Revisa las pestañas:\n"
                "   1 · tabla del AFN-ε   2 · ε-cláusulas   3 · AFN sin ε\n"
                "   4 · AFD final   5 · validación de cadenas   6 · gráfico\n\n"
                "4. En la pestaña 5 escribe cadenas (una por línea; @ = cadena vacía) y presiona «Evaluar».\n\n"
                "5. En la pestaña 6 puedes animar el recorrido de una cadena, mover los estados con el ratón "
                "y exportar el dibujo (SVG) o el código DOT de Graphviz.\n\n"
                "El menú «Ejemplos» trae autómatas listos para probar."))

        def acerca(self):
            messagebox.showinfo("Acerca de", (
                "Conversión de AFN-ε a AFD\nLenguajes Formales y Autómatas\n\n"
                "Integrantes:\n  " + "\n  ".join(INTEGRANTES) + "\n\n"
                "Etapa 1: eliminación de transiciones vacías mediante ε-cláusulas.\n"
                "Etapa 2: determinización por construcción de subconjuntos."))


# =============================================================================
#  PROGRAMA PRINCIPAL
# =============================================================================

def _modo_reporte(origen):
    if origen.isdigit() and 1 <= int(origen) <= len(EJEMPLOS):
        datos = EJEMPLOS[int(origen) - 1]
    else:
        with open(origen, encoding="utf-8") as fh:
            datos = json.load(fh)
    afne = AFNE.desde_dict(datos)
    e1, afd = convertir(afne)
    pruebas = ["" if c in (EPS, EPS_TXT) else c for c in datos.get("pruebas", [])]
    print(generar_reporte(afne, e1, afd, [afd.evaluar(c) for c in pruebas]))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    if len(sys.argv) >= 3 and sys.argv[1] == "--reporte":
        try:
            _modo_reporte(sys.argv[2])
        except (OSError, ValueError) as ex:
            print(f"Error: {ex}")
            sys.exit(1)
        return
    if tk is None:
        print("No se encontró Tkinter. Instálalo (Linux: sudo apt install python3-tk) o usa:\n"
              "    python afn_a_afd.py --reporte 1")
        sys.exit(1)
    if sys.platform.startswith("win"):       # texto nítido en pantallas con escalado
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    App().mainloop()


if __name__ == "__main__":
    main()
