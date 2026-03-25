# Bandeco Unicamp API

REST API that scrapes the daily menu from the [Unicamp university restaurants](https://www.prefeitura.unicamp.br/cardapio/) and exposes it in a structured JSON format.

## Features

- Daily scraping scheduled at 07:00 (configurable), covering all days visible on the page (current day through Sunday)
- Structured response: almoço and jantar, each with regular and vegano options
- Menu categories: prato principal, arroz e feijão, guarnição, salada, sobremesa, suco, observações
- SQLite persistence — data survives server restarts
- Swagger UI auto-documentation at `/docs`
- Manual scrape trigger via `POST /cardapio/scrape`

## Requirements

- Python 3.10+
- A `.venv` virtual environment (see setup below)

## Setup

```bash
# 1. Create and activate the virtual environment
python3 -m venv .venv
source .venv/bin/activate  # macOS / Linux
# .venv\Scripts\activate   # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Optional) copy and edit the environment file
cp .env.example .env
```

## Configuration

All settings can be overridden via environment variables or a `.env` file:

| Variable | Default | Description |
|---|---|---|
| `CARDAPIO_URL` | `https://www.prefeitura.unicamp.br/cardapio/` | Source URL |
| `DATABASE_URL` | `sqlite:///./bandeco.db` | SQLite database path |
| `SCRAPE_HOUR` | `7` | Hour of the daily scrape job (24h local time) |
| `SCRAPE_MINUTE` | `0` | Minute of the daily scrape job |
| `SCRAPE_TIMEOUT_S` | `15` | HTTP request timeout in seconds |
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8000` | Server port |

## Running

```bash
# Activate the venv first
source .venv/bin/activate

# Start the server
python -m app.main
```

The API will be available at `http://localhost:8000`.  
Interactive docs: `http://localhost:8000/docs`

## API Endpoints

### `GET /cardapio/{data}`

Returns the full menu for a given date.

- **Path parameter:** `data` — date in `YYYY-MM-DD` format
- **Returns:** menu broken down by meal (almoço / jantar) and type (regular / vegano)

**Example request:**
```
GET /cardapio/2026-03-25
```

**Example response:**
```json
{
  "data": "2026-03-25",
  "almoco": {
    "regular": {
      "prato_principal": "ISCAS BOVINAS AO SHOYO",
      "arroz_feijao": "ARROZ E FEIJÃO",
      "guarnicao": "CENOURA NA SALSA",
      "salada": "SALADA DE TOMATE E CEBOLA",
      "sobremesa": "BARRA DE CEREAL",
      "suco": "REFRESCO DE LARANJA",
      "observacoes": "CONTÉM GLÚTEN NO PÃO FRANCÊS E NA BARRA DE CEREAL"
    },
    "vegano": {
      "prato_principal": "ERVILHA ORIENTAL",
      "arroz_feijao": "ARROZ E FEIJÃO",
      "guarnicao": "...",
      "salada": "...",
      "sobremesa": "...",
      "suco": "...",
      "observacoes": "NÃO CONTÉM LACTOSE NEM OVOS"
    }
  },
  "jantar": {
    "regular": { "...": "..." },
    "vegano": { "...": "..." }
  }
}
```

### `GET /cardapio/`

Returns all dates that have at least one scraped menu entry.

```json
{
  "datas": ["2026-03-25", "2026-03-26", "2026-03-27"]
}
```

### `POST /cardapio/scrape`

Triggers a manual scraping run in the background. Useful for the first run or to refresh data outside the scheduled time.

```
POST /cardapio/scrape
→ 202 Accepted
{ "detail": "Scraping started in the background." }
```

## First run

After starting the server, trigger an initial scrape manually:

```bash
curl -X POST http://localhost:8000/cardapio/scrape
```

Then query a date:

```bash
curl http://localhost:8000/cardapio/2026-03-25
```

## Project structure

```
bandeco-unicamp-api/
  app/
    __init__.py
    main.py        # FastAPI app, lifespan, APScheduler setup
    config.py      # Settings via pydantic-settings
    database.py    # SQLite engine and session
    models.py      # SQLModel table + Pydantic response schemas
    scraper.py     # httpx + BeautifulSoup scraping logic
    tasks.py       # Shared scrape-and-upsert task
    routes/
      __init__.py
      cardapio.py  # REST endpoints
  pyproject.toml
  requirements.txt
  README.md
```
