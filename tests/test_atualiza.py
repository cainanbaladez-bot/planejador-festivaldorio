"""Validação do catálogo antes da publicação, sem rede nem Git remoto."""
import copy
import json
import unittest
from pathlib import Path

import atualiza_diario as atualiza


ROOT = Path(__file__).resolve().parents[1]


class ValidacaoPublicacao(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.filmes = json.loads((ROOT / "data/rio_2026_filmes.json").read_text(encoding="utf-8"))
        cls.sessoes = json.loads((ROOT / "data/rio_2026_sessoes.json").read_text(encoding="utf-8"))

    def test_catalogo_local_valido(self):
        self.assertTrue(atualiza.validar(self.filmes, self.sessoes))

    def test_rejeita_sessao_sem_filme(self):
        sessoes = copy.deepcopy(self.sessoes[:1])
        sessoes[0]["filme_id"] = "inexistente"
        with self.assertRaisesRegex(ValueError, "sem filme"):
            atualiza.validar(self.filmes, sessoes)

    def test_rejeita_duplicacao_e_duracao_invalida(self):
        sessoes = copy.deepcopy(self.sessoes[:1])
        with self.assertRaisesRegex(ValueError, "duplicados"):
            atualiza.validar(self.filmes, sessoes + sessoes)
        sessoes[0]["duracao"] = "sem duração"
        with self.assertRaisesRegex(ValueError, "duração"):
            atualiza.validar(self.filmes, sessoes)

    def test_rejeita_horario_e_edicao_invalidos(self):
        sessoes = copy.deepcopy(self.sessoes[:1])
        sessoes[0]["hora"] = "25:00"
        with self.assertRaisesRegex(ValueError, "hora"):
            atualiza.validar(self.filmes, sessoes)
        sessoes[0]["hora"] = "19:00"
        sessoes[0]["data"] = "2025-10-07"
        with self.assertRaisesRegex(ValueError, "edição"):
            atualiza.validar(self.filmes, sessoes)


if __name__ == "__main__":
    unittest.main()
