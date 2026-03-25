"""
Scraper for https://sistemas.prefeitura.unicamp.br/apps/cardapio/index.php?d=YYYY-MM-DD

The page is server-side rendered with a clean, stable HTML structure:

  <h2 class="menu-section-title">Almoço</h2>
  <div class="menu-item">
      <div class="menu-item-name">PRATO PRINCIPAL</div>
      <div class="menu-item-description">
          ARROZ E FEIJÃO<br>
          GUARNIÇÃO<br>
          SALADA<br>
          SOBREMESA<br>
          SUCO<br>
          <br>Observações: <br>
          TEXTO DAS OBSERVAÇÕES<br/>
          ...
      </div>
  </div>

Sections: Almoço / Almoço Vegano / Jantar / Jantar Vegano
Encoding: iso-8859-1
"""

import logging
from datetime import date, timedelta
from typing import Optional

import httpx
from bs4 import BeautifulSoup, Tag

from app.config import settings

logger = logging.getLogger(__name__)

# Maps section title text → (refeicao, tipo) keys used in the DB
_SECTION_MAP: dict[str, tuple[str, str]] = {
    "almoço": ("almoco", "regular"),
    "almoco": ("almoco", "regular"),
    "almoço vegano": ("almoco", "vegano"),
    "almoco vegano": ("almoco", "vegano"),
    "jantar": ("jantar", "regular"),
    "jantar vegano": ("jantar", "vegano"),
}

# Fixed order of items inside div.menu-item-description (before "Observações:")
_DESCRIPTION_FIELDS = [
    "arroz_feijao",
    "guarnicao",
    "salada",
    "sobremesa",
    "suco",
]


def _dates_to_scrape() -> list[date]:
    """Return all dates from today through the coming Sunday (inclusive)."""
    today = date.today()
    days_until_sunday = (6 - today.weekday()) % 7  # Sunday = weekday 6
    # Always include at least today
    return [today + timedelta(days=i) for i in range(days_until_sunday + 1)]


def _parse_description(div: Tag) -> dict[str, Optional[str]]:
    """
    Parse a div.menu-item-description into the five fixed fields + observacoes.

    The div contains text nodes and <br> elements interleaved.  We collect
    each text segment between <br> tags, producing an ordered list of lines,
    then assign them to the known fields by position.
    """
    lines: list[str] = []
    current: list[str] = []

    for child in div.children:
        tag_name = getattr(child, "name", None)
        if tag_name in ("br",):
            segment = " ".join(current).strip()
            lines.append(segment)
            current = []
        elif tag_name == "font":
            # The red <font> block only contains the restaurant location notice;
            # we skip it intentionally.
            pass
        elif tag_name is not None:
            # Any other nested tag (e.g. <strong>) — take its text
            current.append(child.get_text(" ", strip=True))
        else:
            # Plain text node
            current.append(str(child))

    # Flush any remaining text
    if current:
        lines.append(" ".join(current).strip())

    # Remove empty lines and the bare "Observações:" marker line
    obs_parts: list[str] = []
    in_obs = False
    data_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        lower = stripped.lower()
        if lower.startswith("observa"):
            in_obs = True
            # Remainder on the same "line" after the colon (usually empty)
            after_colon = stripped.split(":", 1)[1].strip() if ":" in stripped else ""
            if after_colon:
                obs_parts.append(after_colon)
            continue
        if in_obs:
            obs_parts.append(stripped)
        else:
            data_lines.append(stripped)

    result: dict[str, Optional[str]] = {f: None for f in _DESCRIPTION_FIELDS}
    result["observacoes"] = " ".join(obs_parts) if obs_parts else None

    for idx, field in enumerate(_DESCRIPTION_FIELDS):
        if idx < len(data_lines):
            result[field] = data_lines[idx] or None

    return result


def _parse_page(html_bytes: bytes, menu_date: date) -> list[dict]:
    """Parse the full HTML of a cardápio page and return a list of DB-ready dicts."""
    # The page declares iso-8859-1; decode accordingly
    soup = BeautifulSoup(html_bytes, "html.parser", from_encoding="iso-8859-1")

    records: list[dict] = []

    for section in soup.find_all("div", class_="menu-section"):
        title_tag = section.find("h2", class_="menu-section-title")
        if not title_tag:
            continue

        title = title_tag.get_text(" ", strip=True).lower()
        mapping = _SECTION_MAP.get(title)
        if mapping is None:
            logger.debug("Unknown section title '%s', skipping", title)
            continue

        refeicao, tipo = mapping

        name_div = section.find("div", class_="menu-item-name")
        desc_div = section.find("div", class_="menu-item-description")

        if not name_div or not desc_div:
            logger.warning(
                "Section '%s' on %s is missing name or description divs", title, menu_date
            )
            continue

        prato_principal = name_div.get_text(" ", strip=True) or None
        desc_fields = _parse_description(desc_div)

        records.append(
            {
                "data": menu_date,
                "refeicao": refeicao,
                "tipo": tipo,
                "prato_principal": prato_principal,
                **desc_fields,
            }
        )

    return records


async def scrape_cardapio() -> list[dict]:
    """
    Fetch the menu for every date from today through the coming Sunday.
    Returns a flat list of dicts ready for upserting into the Cardapio table.
    """
    dates = _dates_to_scrape()
    all_records: list[dict] = []

    async with httpx.AsyncClient(timeout=settings.scrape_timeout_s) as client:
        for menu_date in dates:
            url = f"{settings.cardapio_url}?d={menu_date}"
            logger.info("Fetching %s", url)
            try:
                response = await client.get(url)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.error("HTTP error for %s: %s", menu_date, exc)
                continue

            records = _parse_page(response.content, menu_date)

            if not records:
                logger.info("No menu found for %s (page may not be published yet)", menu_date)
            else:
                logger.info("Parsed %d records for %s", len(records), menu_date)

            all_records.extend(records)

    return all_records
