# Ajudes · ajud.es

A free finder for public aid ("ayudas", in Valencian "ajudes") across Spain, for individuals,
self-employed people and companies.

Every day it reads Spain's official grants database (BDNS) and works out who each announcement is
for, where it applies, its topic and its deadline. It then publishes a static website. Visitors fill
in a short profile: who they are, where they live, their age, interests and sector. The site then
shows the aid that fits them. The profile and saved aid stay in the visitor's browser, with no
accounts, cookies or servers.

No AI, no database and no server, so it costs €0 to run.

## How it works

| File | What it does |
|---|---|
| `ayudas/bdns.py` | Downloads announcements from the BDNS public API for all of Spain, for individuals (type 1), SMEs and self-employed (3) and large companies (4). One request at a time, with a pause. |
| `ayudas/store.py` | Keeps a slim copy in `data/convocatorias.jsonl` (one announcement per line) and the progress in `data/estado.json`. Each run reads the last 10 days, then goes further back (up to 180 days) and re-checks open announcements for extended deadlines. It stops after a time budget, and the next run carries on. |
| `ayudas/geo.py`, `ayudas/places.py` | Regions, provinces and islands (NUTS codes). Who publishes each announcement and where it applies. A town hall or regional government only funds within its territory, even when the record says "all of Spain". |
| `ayudas/topics.py` | Keyword rules in Spanish and Valencian/Catalan that sort announcements into topics, for people and for businesses. |
| `ayudas/extract.py` | Beneficiary types, sectors (CNAE), the "who can apply" paragraph and the best official document. |
| `ayudas/deadlines.py` | Works out application windows from official dates, or from periods like "10 días hábiles desde su publicación" counted from the bulletin date (Ley 39/2015, art. 30). |
| `ayudas/text.py` | Readable titles and place names. |
| `ayudas/site.py` | Builds the static site: home page, search page, one page per topic, region, province and town, RSS feeds and sitemap. Also writes the data the browser uses: `public/data/meta.json` and one file per region in `public/data/r/` (`ES.json` for all of Spain). |
| `ayudas/static/app.js` | Runs in the browser: the profile, matching, search filters, saved aid and calendar reminders (`.ics`). The profile is stored in `localStorage` and never leaves the device. |
| `ayudas/static/style.css` | The design, with light and dark modes. |
| `ayudas/telegram.py` | Optional: posts new aid to a Telegram channel. |

Only the Python standard library is used. Tests are in `tests/`.

## Run it locally (WSL)

```bash
cd ~/projects/ayudas-al-dia
python3 -m unittest discover -s tests
python3 -m ayudas update --budget-minutes 60   # can be run again: it carries on where it stopped
python3 -m ayudas build
python3 -m http.server 8765 --directory public
```

Then open http://localhost:8765.

The commands are `update`, `build`, `notify` and `all`. Useful options:

- `--budget-minutes`: how long one download may take. The default is 50.
- `--horizon-days`: how far back to collect. The default is 180.
- `--today`: pretend it's another date.
- `--site-url`: the public address, used for RSS and the sitemap.

A first full download of six months takes a few hours. With the default budget, the daily job
finishes it within a few days and then needs only minutes a day.

## Put it online

The repository is `lodist/ajudes`. GitHub hosts the site and runs the daily job for free, because
the repository is public.

1. In the repository, go to **Settings → Pages → Build and deployment** and set **Source** to
   **GitHub Actions**.
2. In the **Actions** tab, open **Actualizar ayudas** and click **Run workflow**. From then on it runs
   every morning. It tests, downloads for up to an hour, commits `data/` and publishes.
3. The site appears at `https://lodist.github.io/ajudes/`. Links, RSS and the sitemap use that
   address automatically.

### Later: your own domain

1. Buy `ajud.es` from any registrar that sells .es domains, such as GoDaddy, DonDominio, OVHcloud,
   IONOS or Arsys. Compare the renewal price, not only the first year. The .es registry asks for the
   holder's DNI/NIE.
2. In the registrar's DNS settings, add these records:

   | Type | Name | Value |
   |---|---|---|
   | A | @ | 185.199.108.153 |
   | A | @ | 185.199.109.153 |
   | A | @ | 185.199.110.153 |
   | A | @ | 185.199.111.153 |
   | CNAME | www | lodist.github.io |

3. In your GitHub account settings, go to **Pages → Add a verified domain**. Enter `ajud.es` and add
   the TXT record GitHub shows you. This stops anyone else from using your domain on GitHub.
4. In the repository settings, go to **Pages → Custom domain**, enter `ajud.es` and click **Save**.
   When the DNS check turns green, tick **Enforce HTTPS**. The check takes from minutes to a few
   hours.
5. In **Settings → Secrets and variables → Actions → Variables**, add `SITE_URL` with the value
   `https://ajud.es/`, so that links, RSS and the sitemap use the domain.

### After launch

- Add the site to Google Search Console and submit `sitemap.xml`, so Google finds the topic,
  region and town pages.
- **Optional Telegram channel:** create a bot with @BotFather and make it an admin of your channel.
  Then add the secret `TELEGRAM_BOT_TOKEN` and the variables `TELEGRAM_CHAT_ID` (for example
  `@ajudes`) and `TELEGRAM_CHANNEL_URL`.
- **Before adding ads:** Spanish law (LSSI) asks sites with an economic activity to publish an
  "aviso legal" with the owner's name, NIF and contact email. Ads also need a cookie consent banner.
  Today the site uses no cookies.

## Data and terms

The data comes from the Sistema Nacional de Publicidad de Subvenciones y Ayudas Públicas (BDNS)
and is reused under its [terms](https://www.infosubvenciones.es/bdnstrans/GE/es/avisolegal).
Every page credits the source and links to the official announcement.

## Known limits

- Deadlines given in working days ignore public holidays. A real deadline can be a day or two
  later than shown, never earlier.
- Topics come from keywords in the title, so some announcements land in the wrong topic or in
  "Otras ayudas".
- Some town halls tag their announcements as "all of Spain" and name no bulletin. When the town's
  province can't be worked out, the announcement is left out rather than shown everywhere.
- Associations and other non-profit bodies (BDNS type 2) aren't covered yet. Adding them means one
  more value in `PEOPLE_AND_BUSINESSES` in `bdns.py` and a choice in the profile.
- If the BDNS ever blocks GitHub's servers, run `python3 -m ayudas all` from a cron job in WSL
  instead. That is also free.
