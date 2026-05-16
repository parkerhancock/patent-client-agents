"""Shared fixtures for LPI statutes tests."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from patent_client_agents.inpi_br_statutes.corpus.schema import DDL, SCHEMA_VERSION


def _row(
    slug: str,
    article_number: str | None,
    title_pt: str,
    title_en: str | None,
    title_section: str | None,
    text_pt: str,
    text_en: str | None,
) -> tuple:
    return (
        slug,
        article_number,
        title_pt,
        title_en,
        title_section,
        text_pt,
        text_en,
        f"<p>{text_pt}</p>",
        f"<p>{text_en}</p>" if text_en else None,
    )


@pytest.fixture(scope="session")
def lpi_corpus_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("inpi-br-statutes-corpus") / "inpi_br_statutes.db"
    rows = [
        _row(
            "art6",
            "Art. 6",
            "Ao autor de invenção ou de modelo de utilidade será assegurado o direito de obter a patente.",
            "The author of an invention or utility model shall be assured the right to obtain the patent.",
            "Title I — Patents",
            "Art. 6º Ao autor de invenção ou de modelo de utilidade será assegurado o direito de obter a patente que lhe garanta a propriedade, nas condições estabelecidas nesta Lei.",
            "Article 6. The author of an invention or utility model shall be assured the right to obtain the patent that guarantees its ownership, under the conditions established in this Law.",
        ),
        _row(
            "art10",
            "Art. 10",
            "Não se considera invenção nem modelo de utilidade: I - descobertas, teorias científicas e métodos matemáticos.",
            "The following shall not be considered inventions or utility models: I - discoveries, scientific theories, and mathematical methods.",
            "Title I — Patents",
            "Art. 10. Não se considera invenção nem modelo de utilidade: I - descobertas, teorias científicas e métodos matemáticos; II - concepções puramente abstratas; III - esquemas, planos, princípios ou métodos comerciais, contábeis, financeiros, educativos, publicitários, de sorteio e de fiscalização.",
            "Article 10. The following shall not be considered inventions or utility models: I - discoveries, scientific theories, and mathematical methods; II - purely abstract concepts; III - schemes, plans, principles or commercial, accounting, financial, educational, advertising, lottery, and inspection methods.",
        ),
        _row(
            "art125",
            "Art. 125",
            "À marca registrada no Brasil considerada de alto renome será assegurada proteção especial.",
            "A trademark registered in Brazil that is considered to be well-known shall be assured special protection.",
            "Title III — Trade Marks",
            "Art. 125. À marca registrada no Brasil considerada de alto renome será assegurada proteção especial, em todos os ramos de atividade.",
            "Article 125. A trademark registered in Brazil that is considered to be well-known shall be assured special protection in all fields of activity.",
        ),
        _row(
            "art195",
            "Art. 195",
            "Comete crime de concorrência desleal quem: ... XI - divulga, explora ou utiliza-se, sem autorização, de conhecimentos, informações ou dados confidenciais, utilizáveis na indústria, comércio ou prestação de serviços.",
            "Whoever commits unfair competition: ... XI - discloses, exploits or uses, without authorization, confidential knowledge, information or data, usable in industry, commerce or rendering of services, is guilty of a crime of unfair competition.",
            "Title V — Crimes Against Industrial Property",
            "Art. 195. Comete crime de concorrência desleal quem: ... XI - divulga, explora ou utiliza-se, sem autorização, de conhecimentos, informações ou dados confidenciais, utilizáveis na indústria, comércio ou prestação de serviços, excluídos aqueles que sejam de conhecimento público ou que sejam evidentes para um técnico no assunto, a que teve acesso mediante relação contratual ou empregatícia, mesmo após o término do contrato.",
            "Article 195. Whoever commits unfair competition: ... XI - discloses, exploits or uses, without authorization, confidential knowledge, information or data, usable in industry, commerce or rendering of services, except those that are public knowledge or that would be evident to a technician on the subject, to which it had access through a contractual or employment relationship, even after the termination of the contract.",
        ),
    ]
    conn = sqlite3.connect(out)
    try:
        conn.executescript(DDL)
        for key, val in (
            ("schema_version", str(SCHEMA_VERSION)),
            ("source_pt", "https://www.planalto.gov.br/ccivil_03/leis/l9279.htm"),
            ("source_en", "https://www.wipo.int/wipolex/en/legislation/details/16774"),
            ("snapshot_date", datetime.now(UTC).strftime("%Y-%m-%d")),
            ("lpi_year", "1996"),
        ):
            conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", (key, val))
        conn.executemany(
            "INSERT INTO sections (href, article_number, title_pt, title_en, title_section, "
            "text_pt, text_en, html_pt, html_en) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
    finally:
        conn.close()
    return out
