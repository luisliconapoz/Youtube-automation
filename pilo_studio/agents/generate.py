"""Genera el plan con el Agente Guionista y lo corrige con el QA (máx. N rondas).

Flujo: plan -> validate -> si hay ERRORES, se devuelve al agente el plan anterior
y la lista exacta de errores, y pide solo las correcciones. Los avisos (WARN) no
disparan reparación.
"""
from __future__ import annotations

import json
from typing import Callable

from ..qa.validator import Report, validate_plan

Complete = Callable[[str, list[dict]], str]   # (system, messages) -> texto
Extract = Callable[[str], dict]


class PlanRejected(RuntimeError):
    def __init__(self, report: Report):
        super().__init__(f"Plan no válido tras las reparaciones ({len(report.errors)} errores)")
        self.report = report


def repair_message(report: Report) -> str:
    lines = "\n".join(f"- {i}" for i in report.errors)
    return (
        "Tu plan fue rechazado por el control de calidad. Corrige SOLO estos errores "
        "y devuelve el plan COMPLETO en JSON válido (sin markdown, sin comentarios):\n"
        f"{lines}\n\nReglas que no debes romper: personajes solo de la marca, "
        "expresiones y poses de la lista oficial, sin repetir pose/expresión en escenas "
        "seguidas, sin texto/números/comillas/3D en campos visuales, fondo negro, "
        "duración total dentro del rango del formato."
    )


def generate_valid_plan(complete: Complete, extract: Extract, system: str, user: str,
                        max_repairs: int = 2, on_attempt: Callable[[int, Report], None] | None = None):
    messages = [{"role": "user", "content": user}]
    for attempt in range(max_repairs + 1):
        text = complete(system, messages)
        plan = extract(text)
        report = validate_plan(plan)
        if on_attempt:
            on_attempt(attempt, report)
        if report.ok:
            return plan, attempt
        messages += [
            {"role": "assistant", "content": json.dumps(plan, ensure_ascii=False)},
            {"role": "user", "content": repair_message(report)},
        ]
    raise PlanRejected(report)
