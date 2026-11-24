# -*- coding: utf-8 -*-
"""Pruebas automáticas.   Ejecutar:  python -m unittest test_afn_a_afd -v"""

import itertools
import random
import unittest

from afn_a_afd import (AFNE, EJEMPLOS, EPS, VACIO, ErrorAutomata, afd_a_dot, convertir,
                       disposicion_circular, figuras_a_svg, figuras_afd, generar_reporte,
                       parsear_alfabeto, parsear_destinos)


def todas_las_cadenas(alfabeto, largo_max):
    for n in range(largo_max + 1):
        for t in itertools.product(alfabeto, repeat=n):
            yield "".join(t)


def afne_aleatorio(rng):
    n = rng.randint(2, 10)
    estados = [f"q{i}" for i in range(n)]
    alfabeto = rng.sample(["a", "b", "c", "d"], rng.randint(1, 4))
    trans = {q: {s: rng.sample(estados, min(n, rng.choice([0, 0, 1, 1, 2, 3])))
                 for s in alfabeto + [EPS]} for q in estados}
    finales = rng.sample(estados, rng.randint(1, n))
    return AFNE(estados, alfabeto, trans, rng.choice(estados), finales)


class TestConversion(unittest.TestCase):

    def test_ejemplo_clasico(self):
        e1, afd = convertir(AFNE.desde_dict(EJEMPLOS[0]))
        self.assertEqual(e1.clausuras["q0"], {"q0", "q1", "q2"})
        self.assertEqual(e1.clausuras["q1"], {"q1", "q2"})
        self.assertEqual(e1.finales, {"q0", "q1", "q2"})
        self.assertEqual(afd.estados, ["A", "B", "C", VACIO])
        self.assertEqual(afd.delta["A"], {"a": "A", "b": "B", "c": "C"})
        self.assertEqual(afd.delta[VACIO], {"a": VACIO, "b": VACIO, "c": VACIO})
        self.assertNotIn(VACIO, afd.finales)
        self.assertEqual(afd.muerto, VACIO)

    def test_thompson_abb(self):
        _, afd = convertir(AFNE.desde_dict(EJEMPLOS[1]))
        self.assertEqual(len(afd.estados), 5)       # DFA clásico de (a|b)*abb
        self.assertIsNone(afd.muerto)

    def test_equivalencia_aleatoria(self):
        """El AFD debe aceptar exactamente lo mismo que el AFN-ε original."""
        rng = random.Random(2024)
        for _ in range(300):
            afne = afne_aleatorio(rng)
            _, afd = convertir(afne)
            for w in todas_las_cadenas(afne.alfabeto, 5 if len(afne.alfabeto) <= 2 else 3):
                self.assertEqual(afd.evaluar(w).aceptada, afne.acepta(w), (afne.a_dict(), w))
            # determinismo: exactamente una transición por estado y símbolo
            for q in afd.estados:
                self.assertEqual(set(afd.delta[q]), set(afne.alfabeto))

    def test_ejemplos_y_salidas(self):
        for ej in EJEMPLOS:
            afne = AFNE.desde_dict(ej)
            e1, afd = convertir(afne)
            texto = generar_reporte(afne, e1, afd, [afd.evaluar("")])
            self.assertIn("AFD FINAL", texto)
            self.assertIn("digraph", afd_a_dot(afd))
            figs = figuras_afd(afd, disposicion_circular(afd.estados), 900, 500)
            self.assertTrue(figuras_a_svg(figs, 900, 500).startswith("<svg"))

    def test_simbolo_fuera_de_sigma(self):
        _, afd = convertir(AFNE.desde_dict(EJEMPLOS[0]))
        ev = afd.evaluar("abx")
        self.assertFalse(ev.aceptada)
        self.assertIn("no pertenece a Σ", ev.error)


class TestValidaciones(unittest.TestCase):

    def test_limites(self):
        with self.assertRaises(ErrorAutomata):
            AFNE(["q0"], ["a"], {}, "q0", ["q0"])                       # < 2 estados
        with self.assertRaises(ErrorAutomata):
            AFNE([f"q{i}" for i in range(11)], ["a"], {}, "q0", ["q0"])  # > 10 estados
        with self.assertRaises(ErrorAutomata):
            parsear_alfabeto("a,b,c,d,e")                               # > 4 símbolos
        with self.assertRaises(ErrorAutomata):
            parsear_alfabeto("a,@")                                     # @ reservado
        with self.assertRaises(ErrorAutomata):
            AFNE(["q0", "q1"], ["a"], {}, "q0", [])                     # sin finales
        with self.assertRaises(ErrorAutomata):
            AFNE(["q0", "q1"], ["a"], {}, "q0", ["q7"])                 # final fuera de Q

    def test_parseo_de_casillas(self):
        Q = ["q0", "q1", "q2"]
        self.assertEqual(parsear_destinos("q1, q2", Q), ["q1", "q2"])
        self.assertEqual(parsear_destinos("{q2 q0}", Q), ["q2", "q0"])
        self.assertEqual(parsear_destinos("1,2", Q), ["q1", "q2"])
        self.assertEqual(parsear_destinos("", Q), [])
        self.assertEqual(parsear_destinos("∅", Q), [])
        with self.assertRaises(ErrorAutomata) as cm:
            parsear_destinos("q5", Q, ("q0", "a"))
        self.assertEqual(cm.exception.celda, ("q0", "a"))
        self.assertEqual(parsear_alfabeto("01"), ["0", "1"])
        self.assertEqual(parsear_alfabeto("+, -, d, ."), ["+", "-", "d", "."])


if __name__ == "__main__":
    unittest.main()
