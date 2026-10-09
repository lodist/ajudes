"""Command line: python -m ayudas update|build|notify|all"""
import argparse
import datetime as dt
import os
import sys
from pathlib import Path

from . import bdns, site, store, telegram

ROOT = Path(__file__).resolve().parent.parent


def github_pages_url(repository: str) -> str:
    """Public address GitHub Pages gives a repository ("owner/name"), or "" outside GitHub."""
    if "/" not in repository:
        return ""
    owner, name = (part.lower() for part in repository.split("/", 1))
    base = f"https://{owner}.github.io/"
    return base if name == f"{owner}.github.io" else f"{base}{name}/"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m ayudas",
        description="Ajudes: ayudas públicas para particulares, autónomos y empresas de toda España.")
    parser.add_argument("command", choices=("update", "build", "notify", "all"),
                        help="update: descarga de la BDNS · build: genera la web · notify: avisa por Telegram")
    parser.add_argument("--budget-minutes", type=float, default=50,
                        help="tiempo máximo de descarga en esta ejecución; la siguiente continúa donde quedó")
    parser.add_argument("--horizon-days", type=int, default=store.HORIZON_DAYS,
                        help="cuántos días hacia atrás reunir convocatorias")
    parser.add_argument("--today", type=dt.date.fromisoformat, default=dt.date.today(),
                        help="fecha de referencia AAAA-MM-DD, para pruebas")
    parser.add_argument("--site-url",
                        default=os.environ.get("SITE_URL") or github_pages_url(os.environ.get("GITHUB_REPOSITORY", "")),
                        help="dirección pública de la web, para el sitemap "
                             "(por defecto, la de GitHub Pages cuando corre en GitHub)")
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    parser.add_argument("--out", type=Path, default=ROOT / "public")
    args = parser.parse_args(argv)

    db = store.load(args.data)
    if args.command in ("update", "all"):
        store.update(db, bdns.search, bdns.detail, args.today, budget_seconds=args.budget_minutes * 60,
                     horizon_days=args.horizon_days, save=lambda current: store.save(current, args.data))
        store.save(db, args.data)
    items = site.items_from(db, args.today)
    if args.command in ("notify", "all") and telegram.notify(db, items, args.today):
        store.save(db, args.data)
    if args.command in ("build", "all"):
        counts = site.build(items, args.out, args.today, site_url=args.site_url,
                            telegram_url=os.environ.get("TELEGRAM_CHANNEL_URL", ""))
        print(f"Web generada en {args.out}: {counts['listed']} ayudas visibles ({counts['open']} abiertas), "
              f"{counts['pages']} páginas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
