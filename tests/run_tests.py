from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path


class ResultadoLegivel(unittest.TextTestResult):
    """Resultado de teste com títulos mais claros para execução manual."""

    def getDescription(self, test):
        descricao = test.shortDescription()
        if descricao:
            return f"{test.id()}\n    ↳ {descricao}"
        return test.id()


class RunnerLegivel(unittest.TextTestRunner):
    resultclass = ResultadoLegivel


def main() -> None:
    raiz = Path(__file__).resolve().parents[1]
    raiz_str = str(raiz)
    if raiz_str not in sys.path:
        sys.path.insert(0, raiz_str)
    suite = unittest.defaultTestLoader.discover(str(raiz / "tests"), top_level_dir=raiz_str)
    resultado = RunnerLegivel(verbosity=2).run(suite)
    # Em alguns ambientes o PyMuPDF mantém estado nativo após importação. A saída
    # já foi impressa neste ponto; a finalização explícita evita travamento no encerramento.
    os._exit(0 if resultado.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
