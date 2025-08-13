import csv
import os
import re
from pathlib import Path

import requests
import yaml
from django.core.management.base import BaseCommand
from django.db import transaction

from sapy.models import Icon


BI_DEFAULT_VERSION = os.getenv("BI_VERSION", "latest")
FA_DEFAULT_VERSION = os.getenv("FA_VERSION", "latest")

BI_CSS_URL = "https://unpkg.com/bootstrap-icons@{ver}/font/bootstrap-icons.css"
FA_YML_URL = "https://unpkg.com/@fortawesome/fontawesome-free@{ver}/metadata/icons.yml"

# .bi-<name>::before{content:"\F3E8"}
RE_BI = re.compile(
    r"\.bi-([a-z0-9-]+)::before\s*\{\s*content:\s*['\"]\\([A-Fa-f0-9]+)['\"]\s*;\s*\}",
    re.IGNORECASE,
)

ALLOWED_STYLES_FA = ("solid", "regular", "brands")


def fetch_text(url: str, timeout=30) -> str:
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    # Normalizar a UTF-8 y filtrar bytes no imprimibles para YAML robusto
    text = resp.content.decode('utf-8', errors='ignore')
    return text


def parse_bootstrap_icons(css_text: str, version: str):
    rows = []
    for m in RE_BI.finditer(css_text):
        name = m.group(1)
        uni = m.group(2).upper()
        # Heurísticas de sinónimos para búsqueda (BI no publica tags)
        extra_tags: list[str] = []
        if name.startswith('person') or name.startswith('people'):
            extra_tags += ['user', 'users', 'account', 'profile']
        if 'trash' in name or 'bin' in name:
            extra_tags += ['delete', 'remove']
        if 'gear' in name or 'tools' in name:
            extra_tags += ['settings', 'config']
        tags = ' '.join(sorted(set(extra_tags)))
        rows.append(
            {
                "library": "bootstrap-icons",
                "version": version,
                "name": name,
                "style": "",
                "css_class": f"bi bi-{name}",
                "unicode": uni,
                "provider": Icon.Provider.BOOTSTRAP,
                "label": name.replace('-', ' ').title(),
                "tags": tags,
            }
        )
    return rows


def parse_fontawesome_free(yml_text: str, version: str):
    data = yaml.safe_load(yml_text) or {}
    rows = []

    def style_prefix(style: str) -> str:
        if style == "brands":
            return "fa-brands"
        if style == "regular":
            return "fa-regular"
        return "fa-solid"

    for name, info in data.items():
        if not isinstance(info, dict):
            continue
        free_styles = info.get("free") or []
        styles = [s for s in free_styles if s in ALLOWED_STYLES_FA]
        if not styles:
            styles = [s for s in info.get("styles", []) if s in ALLOWED_STYLES_FA]
        unicode_val = str(info.get("unicode", "")).upper()
        label = str(info.get("label", ""))
        # términos de búsqueda (FA free expone 'search': {'terms': [...]})
        terms = []
        try:
            terms = list(info.get('search', {}).get('terms', []))
        except Exception:
            terms = []
        tags = ' '.join(sorted(set([str(t) for t in terms if t])))
        for st in styles:
            rows.append(
                {
                    "library": "fontawesome6",
                    "version": version,
                    "name": name,
                    "style": st,
                    "css_class": f"{style_prefix(st)} fa-{name}",
                    "unicode": unicode_val,
                    "provider": Icon.Provider.FONTAWESOME,
                    "label": label,
                    "tags": tags,
                }
            )
    return rows


def write_csv(rows, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "library",
                "version",
                "name",
                "style",
                "css_class",
                "unicode",
                "provider",
            ],
        )
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


class Command(BaseCommand):
    help = "Sincroniza íconos de Bootstrap Icons y Font Awesome 6 Free (DB y/o CSV)."

    def add_arguments(self, parser):
        parser.add_argument("--bs-version", default=BI_DEFAULT_VERSION)
        parser.add_argument("--fa-version", default=FA_DEFAULT_VERSION)
        parser.add_argument("--csv-dir", default="")
        parser.add_argument("--save-db", action="store_true")
        parser.add_argument("--replace", action="store_true")

    def handle(self, *args, **opts):
        bs_ver = opts["bs_version"]
        fa_ver = opts["fa_version"]
        csv_dir = Path(opts["csv_dir"]) if opts["csv_dir"] else None
        to_db = bool(opts["save_db"])
        replace = bool(opts["replace"])

        self.stdout.write(self.style.NOTICE(f"→ Bootstrap Icons @{bs_ver}"))
        self.stdout.write(self.style.NOTICE(f"→ Font Awesome Free @{fa_ver}"))
        if not to_db and not csv_dir:
            self.stdout.write(
                self.style.WARNING(
                    "Ni --save-db ni --csv-dir especificados. No habrá salida."
                )
            )
            return

        bi_css = fetch_text(BI_CSS_URL.format(ver=bs_ver))
        fa_yml = fetch_text(FA_YML_URL.format(ver=fa_ver))

        bi_rows = parse_bootstrap_icons(bi_css, bs_ver)
        fa_rows = parse_fontawesome_free(fa_yml, fa_ver)

        self.stdout.write(f"Bootstrap Icons: {len(bi_rows)} íconos")
        self.stdout.write(f"Font Awesome 6 Free: {len(fa_rows)} íconos")

        if csv_dir:
            write_csv(bi_rows, csv_dir / "bootstrap_icons.csv")
            write_csv(fa_rows, csv_dir / "fontawesome6_free.csv")
            self.stdout.write(self.style.SUCCESS(f"CSV guardados en {csv_dir}"))

        if to_db:
            with transaction.atomic():
                if replace:
                    Icon.objects.filter(library="bootstrap-icons").delete()
                    Icon.objects.filter(library="fontawesome6").delete()
                Icon.objects.bulk_create(
                    [
                        Icon(
                            provider=r["provider"],
                            class_name=r["css_class"],
                            library=r["library"],
                            version=r["version"],
                            name=r["name"],
                            style=r["style"],
                            unicode=r["unicode"],
                            label=r.get("label", ""),
                            tags=r.get("tags", ""),
                        )
                        for r in bi_rows
                    ],
                    ignore_conflicts=True,
                    batch_size=1000,
                )
                Icon.objects.bulk_create(
                    [
                        Icon(
                            provider=r["provider"],
                            class_name=r["css_class"],
                            library=r["library"],
                            version=r["version"],
                            name=r["name"],
                            style=r["style"],
                            unicode=r["unicode"],
                            label=r.get("label", ""),
                            tags=r.get("tags", ""),
                        )
                        for r in fa_rows
                    ],
                    ignore_conflicts=True,
                    batch_size=1000,
                )
            self.stdout.write(self.style.SUCCESS("Íconos guardados en DB."))

        self.stdout.write(self.style.SUCCESS("✓ Terminado"))

