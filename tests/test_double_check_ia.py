import unittest

from domain.dfd import extrair_dfd
from domain.tabela_precos import extrair_tabela_precos
from domain.tr_unificado import extrair_tr
from rules.base import normalizar_rotulo_regra
from rules.ia_rules import (
    _agrupar_blocos_texto,
    _aplicar_revisao_double_check,
    _chave_revisao_double_check,
    _iterar_lotes,
    _montar_contexto_double_check,
    _selecionar_grupos_relevantes,
)
from schemas.responses import Providencia, ResultadoItem, StatusRegra


class DoubleCheckIATests(unittest.TestCase):
    def test_reclassifica_variacao_de_forma_para_conforme(self):
        item = ResultadoItem(
            documento="Termo de Referência",
            item="Fundamentação",
            status=StatusRegra.PENDENCIA,
            descricao="Justificativa não identificada automaticamente.",
            providencia=Providencia.CORRIGIR,
        )

        revisao = {
            "classificacao": "PRESENTE_VARIACAO_FORMA",
            "observacao": "A justificativa está em seção com nomenclatura antiga.",
            "evidencia": "Trecho: 'Motivação da contratação'.",
        }

        atualizado = _aplicar_revisao_double_check(item, revisao)

        self.assertEqual(atualizado.status, StatusRegra.CONFORME)
        self.assertEqual(atualizado.providencia, Providencia.PROSSEGUIR)
        self.assertTrue(atualizado.via_ia)
        self.assertIn("nomenclatura antiga", atualizado.descricao)

    def test_mantem_status_quando_ha_ressalva(self):
        item = ResultadoItem(
            documento="Termo de Referência",
            item="1.6/1.7 – Formalização",
            status=StatusRegra.INCONFORME,
            descricao="Formalização incompatível.",
            providencia=Providencia.CORRIGIR,
        )

        revisao = {
            "classificacao": "PRESENTE_COM_RESSALVA",
            "observacao": "A cláusula existe, mas permanece ambígua.",
            "evidencia": "Trecho: 'formalização por instrumento próprio'.",
        }

        atualizado = _aplicar_revisao_double_check(item, revisao)

        self.assertEqual(atualizado.status, StatusRegra.INCONFORME)
        self.assertTrue(atualizado.via_ia)
        self.assertIn("permanece ambígua", atualizado.descricao)

    def test_contexto_destaca_termos_equivalentes_em_texto_longo(self):
        texto = (
            "Cabeçalho inicial.\n" * 400
            + "Motivação da contratação: a necessidade está plenamente justificada.\n"
            + "Texto intermediário.\n" * 300
            + "Assinatura do responsável ao final.\n"
        )
        itens = [
            ResultadoItem(
                documento="Termo de Referência",
                item="Fundamentação",
                status=StatusRegra.PENDENCIA,
                descricao="Não localizada automaticamente.",
                providencia=Providencia.CORRIGIR,
            )
        ]

        contexto = _montar_contexto_double_check(texto, "Termo de Referência", itens)

        self.assertIn("Motivação da contratação", contexto)
        self.assertIn("[...]", contexto)

    def test_agrupar_blocos_controla_tamanho_e_paginas(self):
        blocos = [
            "Pagina 1 " + ("A" * 1200),
            "Pagina 2 " + ("B" * 1200),
            "Pagina 3 " + ("C" * 1200),
            "Pagina 4 " + ("D" * 1200),
            "Pagina 5 " + ("E" * 1200),
        ]

        grupos = _agrupar_blocos_texto(blocos, max_caracteres=2600, max_paginas_por_grupo=2)

        self.assertEqual(len(grupos), 3)
        self.assertIn("Pagina 1", grupos[0])
        self.assertIn("Pagina 5", grupos[-1])

    def test_seleciona_grupos_relevantes_por_item(self):
        grupos = [
            "Introdução geral do documento.",
            "Cláusula de Motivação da contratação com justificativa detalhada.",
            "Assinatura final.",
        ]
        itens = [
            ResultadoItem(
                documento="Termo de Referência",
                item="Fundamentação",
                status=StatusRegra.PENDENCIA,
                descricao="Não localizada automaticamente.",
                providencia=Providencia.CORRIGIR,
            )
        ]

        selecionados = _selecionar_grupos_relevantes(grupos, "Termo de Referência", itens)

        self.assertEqual(len(selecionados), 1)
        self.assertIn("Motivação da contratação", selecionados[0])

    def test_loteia_itens_para_double_check(self):
        itens = list(range(9))
        lotes = _iterar_lotes(itens, 4)
        self.assertEqual(lotes, [[0, 1, 2, 3], [4, 5, 6, 7], [8]])

    def test_normaliza_tracos_para_casamento_ia(self):
        self.assertEqual(
            normalizar_rotulo_regra("1.1 - Objeto"),
            normalizar_rotulo_regra("1.1 – Objeto"),
        )

    def test_chave_revisao_ignora_espacos_e_traco_ascii(self):
        a = _chave_revisao_double_check(" Termo de Referência ", "1.1 - Objeto ")
        b = _chave_revisao_double_check("Termo de Referência", "1.1 – Objeto")
        self.assertEqual(a, b)

    def test_extratores_preservam_blocos_texto(self):
        dfd = extrair_dfd("Objeto da futura contratação: teste", ["pag1", "pag2"])
        tr = extrair_tr("1.1 Objeto\nAquisição de itens", "TR_AQUISICOES", ["tr1", "tr2"])
        tabela = extrair_tabela_precos("Tabela de preços orçados", ["tb1"])

        self.assertEqual(dfd.blocos_texto, ["pag1", "pag2"])
        self.assertEqual(tr.blocos_texto, ["tr1", "tr2"])
        self.assertEqual(tabela.blocos_texto, ["tb1"])


if __name__ == "__main__":
    unittest.main()
