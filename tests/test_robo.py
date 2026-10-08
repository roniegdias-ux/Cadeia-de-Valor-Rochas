import csv
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
import biblio  # noqa: E402
import cadeia  # noqa: E402
import dados  # noqa: E402
import noticias  # noqa: E402
import rede  # noqa: E402

FIX = os.path.join(RAIZ, "tests", "fixtures")


def ler(n):
    with open(os.path.join(FIX, n), "rb") as f:
        return f.read()


class TestRede(unittest.TestCase):
    def test_rss_e_atom(self):
        itens = rede.extrair_itens(ler("gn.xml"))
        self.assertEqual(len(itens), 4)
        self.assertEqual(itens[0]["fonte_declarada"], "A Gazeta")
        atom = rede.extrair_itens(ler("atom.xml"))[0]
        self.assertEqual(atom["link"], "https://ex.com/1")          # ignora enclosure
        self.assertTrue(atom["data_bruta"].startswith("2026-01-01"))  # published vence updated

    def test_html_rotulado(self):
        with self.assertRaisesRegex(ValueError, "HTML"):
            rede.extrair_itens(b"<!DOCTYPE html><html><body>bloqueio</body></html>")

    def test_normalizar_tira_veiculo(self):
        a = rede.normalizar("Exportações de rochas crescem - A Gazeta")
        b = rede.normalizar("Exportacoes de rochas crescem - Folha Vitória")
        self.assertEqual(a, b)


class TestCadeia(unittest.TestCase):
    def test_forte(self):
        ok, motivo, elos = cadeia.avaliar("Resíduo de rochas ornamentais na construção civil")
        self.assertTrue(ok)
        self.assertIn("E8", elos)
        self.assertIn("E7", elos)

    def test_petrologia_fora(self):
        ok, _, _ = cadeia.avaliar("Petrogenesis of A-type granites in the Borborema Province",
                                  "U-Pb zircon ages and Nd isotopes constrain magma sources")
        self.assertFalse(ok)

    def test_composto(self):
        ok, motivo, elos = cadeia.avaliar("Granite slab sawing with diamond wire")
        self.assertTrue(ok)
        self.assertTrue(motivo.startswith("composto"))
        self.assertIn("E2", elos)

    def test_silicose(self):
        ok, _, elos = cadeia.avaliar("Silicose em trabalhadores de marmorarias")
        self.assertTrue(ok)
        self.assertIn("E9", elos)


class TestNoticias(unittest.TestCase):
    def test_coletar_generalista_filtra(self):
        fim = datetime(2026, 10, 7, tzinfo=timezone.utc)
        with mock.patch.object(rede, "buscar", return_value=(200, ler("gn.xml"), None, 1)):
            linha, itens = noticias.coletar("Feed", "u", True, fim - timedelta(days=7), fim)
        self.assertEqual(linha["sem_data"], 1)
        self.assertEqual(linha["na_janela"], 3)
        self.assertEqual(len(itens), 2)                 # praça descartada
        self.assertEqual(itens[0]["chave"], itens[1]["chave"])

    def test_falha_registrada(self):
        fim = datetime(2026, 10, 7, tzinfo=timezone.utc)
        with mock.patch.object(rede, "buscar", return_value=(403, b"", "HTTPError 403", 1)):
            linha, itens = noticias.coletar("Feed", "u", True, fim, fim)
        self.assertEqual(linha["erro"], "HTTPError 403")
        self.assertEqual(itens, [])


class TestBiblio(unittest.TestCase):
    def _r(self, **kw):
        base = {"titulo": "Rochas ornamentais no ES", "ano": 2020, "doi": None, "autores": ["A B"],
                "veiculo": "", "tipo": "article", "resumo": "", "ids": {}, "achado_por": ["x"], "link": None}
        base.update(kw)
        return base

    def test_dedup_doi_e_titulo(self):
        corpus = {}
        n1 = biblio.mesclar(corpus, [self._r(doi="10.1/x", ids={"openalex": "W1"})])
        n2 = biblio.mesclar(corpus, [self._r(titulo="Outro título", doi="10.1/x", ids={"crossref": "10.1/x"},
                                             resumo="tem resumo", achado_por=["y"])])
        n3 = biblio.mesclar(corpus, [self._r(titulo="Rochas Ornamentais no ES!", ids={"bdtd": "B1"})])
        n4 = biblio.mesclar(corpus, [self._r(titulo="Rochas ornamentais no ES", ano=2021)])
        # mesmo título normalizado + mesmo ano funde; ano diferente é outra obra
        self.assertEqual((len(n1), len(n2), len(n3), len(n4)), (1, 0, 0, 1))
        r = corpus[n1[0]]
        self.assertEqual(r["ids"], {"openalex": "W1", "crossref": "10.1/x", "bdtd": "B1"})
        self.assertEqual(r["resumo"], "tem resumo")
        self.assertEqual(r["achado_por"], ["x", "y"])

    def test_resumo_invertido(self):
        self.assertEqual(biblio._resumo_openalex({"rochas": [0], "ornamentais": [1]}), "rochas ornamentais")

    def test_bibtex_deterministico(self):
        r = self._r(elos_pre=["E1"])
        self.assertEqual(biblio.bibtex(r, "k"), biblio.bibtex(r, "k"))

    def test_openalex_paginacao_e_erro(self):
        respostas = [({"results": [{"title": "T", "publication_year": 2021, "doi": "https://doi.org/10.9/AB",
                                    "authorships": [], "abstract_inverted_index": None}],
                       "meta": {"next_cursor": "c2"}}, 200, None, 1),
                     (None, 429, "HTTPError 429", 4)]
        log = []
        with mock.patch.object(rede, "buscar_json", side_effect=respostas):
            out = biblio.openalex("x", 2020, log)
        self.assertEqual(out[0]["doi"], "10.9/ab")
        self.assertEqual(log[-1]["erro"], "HTTPError 429")


class TestDados(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.antigo = dados.SERIES
        dados.SERIES = self.tmp

    def tearDown(self):
        dados.SERIES = self.antigo
        shutil.rmtree(self.tmp)

    def test_revisao_detectada(self):
        l1 = [{"year": "2025", "monthNumber": "1", "headingCode": "6802", "metricFOB": "100", "metricKG": "10", "coletado_em": "a"}]
        l2 = [{"year": "2025", "monthNumber": "1", "headingCode": "6802", "metricFOB": "110", "metricKG": "10", "coletado_em": "b"},
              {"year": "2025", "monthNumber": "2", "headingCode": "6802", "metricFOB": "50", "metricKG": "5", "coletado_em": "b"}]
        self.assertEqual(dados.gravar_serie("s", l1)[:2], (1, 1))
        total, novas, rev = dados.gravar_serie("s", l2)
        self.assertEqual((total, novas, len(rev)), (2, 1, 1))
        self.assertEqual(rev[0][1]["metricFOB"], ("100", "110"))

    def test_lista_aninhada(self):
        self.assertEqual(dados._lista_de_registros({"data": {"list": [{"a": 1}]}}), [{"a": 1}])
        self.assertEqual(dados._lista_de_registros({"data": {"list": []}}), [])
        self.assertIsNone(dados._lista_de_registros({"erro": "x"}))

    def test_painel(self):
        cfg = rede.ler_json(os.path.join(RAIZ, "config.json"))
        linhas = []
        for ano in (2024, 2025):
            for mes in range(1, 13):
                linhas.append({"year": ano, "monthNumber": mes, "headingCode": "6802", "country": "EUA",
                               "metricFOB": 1_000_000 * (1 if ano == 2024 else 1.1), "metricKG": 1_000_000})
        dados.gravar_serie("comex_export_sh4_pais", linhas)
        md = "\n".join(dados.painel_exportacao(cfg))
        self.assertIn("| 2025 | beneficiadas | 13.2 | 12.0 | 1,100 |", md)
        self.assertIn("+10.0%", md)

    def test_num_decimal_br(self):
        self.assertEqual(dados._num("1.234,56"), 1234.56)
        self.assertEqual(dados._num("12.5"), 12.5)


if __name__ == "__main__":
    unittest.main()
