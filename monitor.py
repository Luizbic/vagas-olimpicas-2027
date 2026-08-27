#!/usr/bin/env python3
"""Monitora páginas oficiais de ingresso olímpico para o ciclo 2027."""
from datetime import datetime, timezone
import json
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

SITES = [
    {"universidade": "USP (FUVEST)", "url": "https://www.fuvest.br/olimpiadas/", "previsao": "Ciclo 2026: 05–16/01/2026; 2027 ainda depende de edital oficial."},
    {"universidade": "UNICAMP (Comvest)", "url": "https://www.comvest.unicamp.br/ingresso-2026/vagas-olimpicas-2026/", "previsao": "Usualmente publicado no fim do ano anterior; confirme no edital 2027."},
    {"universidade": "UFC (PROGRAD)", "url": "https://olimpiadas.prograd.ufc.br/", "previsao": "Ciclo 2026: 06–12/01/2026; 2027 ainda depende de edital oficial."},
    {"universidade": "UNESP (VUNESP)", "url": "https://www.vunesp.com.br/", "previsao": "Acompanhe a página oficial da VUNESP; não há data oficial 2027 confirmada."},
]
USER_AGENT = "Mozilla/5.0 (compatible; VagasOlimpicasMonitor/2.0; +https://github.com/)"
BASE_DIR = Path(__file__).resolve().parent
OUTPUT = BASE_DIR / "status.json"
HISTORY = BASE_DIR / "status.previous.json"


def relevant_term(text: str) -> str | None:
    clean = " ".join(text.lower().split())
    patterns = [
        r"(?:edital|inscri(?:ção|coes)|vagas?|processo seletivo)[^.!?]{0,100}2027",
        r"2027[^.!?]{0,100}(?:edital|inscri(?:ção|coes)|vagas?|processo seletivo)",
        r"inscri(?:ção|coes) abertas",
        r"edital publicado",
    ]
    for pattern in patterns:
        match = re.search(pattern, clean, re.IGNORECASE)
        if match:
            return match.group(0).strip()
    return None


def extract_links(soup: BeautifulSoup, base_url: str) -> tuple[str | None, str | None]:
    edital = inscricao = None
    for anchor in soup.find_all("a", href=True):
        label = " ".join(anchor.get_text(" ", strip=True).lower().split())
        href = anchor["href"]
        if href.startswith("/"):
            from urllib.parse import urljoin
            href = urljoin(base_url, href)
        if not edital and "edital" in label:
            edital = href
        if not inscricao and any(term in label for term in ("inscri", "candidatar", "acesse")):
            inscricao = href
    return edital, inscricao


def monitor_site(site: dict[str, str], session: requests.Session, checked_at: str) -> dict:
    result = {**site, "status": "Aguardando Edital 2027", "termo_identificado": None, "edital_url": None, "inscricao_url": None, "ultima_verificacao": checked_at}
    try:
        response = session.get(site["url"], timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        term = relevant_term(soup.get_text(" ", strip=True))
        edital, inscricao = extract_links(soup, site["url"])
        if term:
            result.update(status="Novidade Detectada", termo_identificado=term, edital_url=edital, inscricao_url=inscricao)
    except requests.RequestException as exc:
        result["erro"] = f"Falha ao acessar a página: {exc}"
    except Exception as exc:
        result["erro"] = f"Erro inesperado: {exc}"
    return result


def main() -> int:
    checked_at = datetime.now(timezone.utc).isoformat()
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    previous = json.loads(HISTORY.read_text(encoding="utf-8")) if HISTORY.exists() else {}
    results = [monitor_site(site, session, checked_at) for site in SITES]
    for result in results:
        old = next((x for x in previous.get("universidades", []) if x.get("universidade") == result["universidade"]), {})
        result["novidade_nova"] = result["status"] == "Novidade Detectada" and result.get("termo_identificado") != old.get("termo_identificado")
    payload = {"ultima_atualizacao": checked_at, "universidades": results}
    if OUTPUT.exists():
        HISTORY.write_text(OUTPUT.read_text(encoding="utf-8"), encoding="utf-8")
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    detected = any(item["novidade_nova"] for item in results)
    print(f"Monitoramento concluído; novidade nova: {'sim' if detected else 'não'}.")
    return 10 if detected else 0


if __name__ == "__main__":
    sys.exit(main())
