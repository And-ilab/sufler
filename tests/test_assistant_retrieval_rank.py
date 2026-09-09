import os
import sys
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sufler.settings")

import django  # noqa: E402

django.setup()

from django.test import TestCase  # noqa: E402

from ingest.models import AssistantProductionChunk, CCProductionChunk  # noqa: E402
from ingest.pipeline import deterministic_embedding  # noqa: E402
from qu.assistant_retrieval import permalink_signal, preview_assistant_query  # noqa: E402
from qu.service import topical_relevance_score  # noqa: E402


VISA_Q = (
    "За чей счёт оплачивают въездную визу и страховку "
    "при командировке за границу?"
)
HIRE_Q = (
    "Какие документы входят в электронный пакет "
    "при согласовании приёма на работу?"
)
TRAVEL_TEXT = (
    "При направлении в служебную командировку за границу въездная виза "
    "и медицинская страховка оплачиваются за счёт банка. Работник не "
    "несёт этих расходов самостоятельно."
)
HR_TEXT = (
    "Согласование назначения кандидата осуществляется в электронном виде. "
    "Непосредственный руководитель формирует пакет документов кандидата "
    "и направляет их для согласования приёма на работу."
)
BENEFITS_DUMP = (
    "Перечень документов для назначения государственного пособия семьям "
    "с детьми: заявление, паспорт, свидетельство о рождении, справка "
    "с места работы, сведения об оплате труда. "
) * 40


class TopicalRelevanceScoreTest(unittest.TestCase):
    def test_travel_article_beats_benefits_dump(self):
        travel = topical_relevance_score(
            VISA_Q,
            "Положение 28.9 командировки.doc",
            TRAVEL_TEXT,
            extra="Положение о командировках",
        )
        benefits = topical_relevance_score(
            VISA_Q,
            "10.07.2026_Perechen-AP-rabotniki_.doc",
            BENEFITS_DUMP,
            extra="Нормативные документы и бланки",
        )
        self.assertGreater(travel, benefits)
        self.assertGreaterEqual(travel, 0.45)

    def test_hr_article_beats_benefits_dump(self):
        hr = topical_relevance_score(
            HIRE_Q,
            "Регламент учета персонала.doc",
            HR_TEXT,
            extra="Регламент учета персонала",
        )
        benefits = topical_relevance_score(
            HIRE_Q,
            "10.07.2026_Perechen-AP-rabotniki_.doc",
            BENEFITS_DUMP,
            extra="Нормативные документы и бланки",
        )
        self.assertGreater(hr, benefits)


class AssistantRetrievalRankTest(TestCase):
    def _chunk(self, **kwargs):
        content = kwargs["content"]
        AssistantProductionChunk.objects.create(
            version_id=1,
            permalink="https://kb.local/doc",
            locale="ru",
            visibility_scope=["assistant"],
            checksum=kwargs.get("checksum", f"sha256:{kwargs['article_id']}"),
            embedding_model="deterministic-dev",
            embedding=deterministic_embedding(content),
            **{key: value for key, value in kwargs.items() if key != "checksum"},
        )

    def test_all_kbs_return_travel_not_benefits(self):
        self._chunk(
            kb_slug="assistant_polozhenie_komandirovki",
            article_id=9_100_001,
            chunk_index=0,
            title="Положение 28.9 командировки.doc",
            content=TRAVEL_TEXT,
        )
        self._chunk(
            kb_slug="assistant_7_dokov",
            article_id=9_100_002,
            chunk_index=0,
            title="10.07.2026_Perechen-AP-rabotniki_.doc",
            content=BENEFITS_DUMP,
        )
        CCProductionChunk.objects.create(
            article_id=2000000008,
            version_id=1,
            chunk_index=0,
            title="avtokredit-belarusbank.txt",
            content=(
                "Автокредит: ставка по кредиту 12 % годовых. "
                "Документы для оформления кредита в банке."
            ),
            permalink="https://kb.local/avto",
            locale="ru",
            visibility_scope=["kc_operator"],
            checksum="sha256:avto",
            embedding_model="deterministic-dev",
            embedding=deterministic_embedding("автокредит ставка документы"),
        )
        result = preview_assistant_query(VISA_Q, search_all=True, limit=5)
        titles = [doc["title"] for doc in result["documents"]]
        self.assertIn("Положение 28.9 командировки.doc", titles)
        self.assertEqual(titles[0], "Положение 28.9 командировки.doc")

    def test_all_kbs_return_hr_pack_not_benefits(self):
        self._chunk(
            kb_slug="assistant_reglament_ucheta_personala",
            article_id=9_100_003,
            chunk_index=0,
            title="Регламент учета персонала.doc",
            content=HR_TEXT,
        )
        self._chunk(
            kb_slug="assistant_7_dokov",
            article_id=9_100_004,
            chunk_index=0,
            title="10.07.2026_Perechen-AP-rabotniki_.doc",
            content=BENEFITS_DUMP,
        )
        result = preview_assistant_query(HIRE_Q, search_all=True, limit=5)
        titles = [doc["title"] for doc in result["documents"]]
        self.assertEqual(titles[0], "Регламент учета персонала.doc")


class WebsitePermalinkSignalTest(unittest.TestCase):
    def test_contacts_path_beats_homepage(self):
        query = "Контакты: телефон горячей линии, адрес головного офиса"
        home = permalink_signal(query, "https://belarusbank.by/ru")
        page = permalink_signal(query, "https://belarusbank.by/ru/kontakty")
        self.assertGreater(page, home)
        self.assertGreater(page, 0)
        self.assertLess(home, 0)
