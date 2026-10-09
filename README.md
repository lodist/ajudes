# Ajudes · ajud.es

Free daily alerts of public aid ("ayudas", in Valencian "ajudes") for people in the Comunitat Valenciana.

Every day it reads Spain's official grants database (BDNS), keeps the announcements aimed at
individuals, sorts them by topic and town, works out the deadlines, and publishes a static
website with RSS feeds (and, optionally, a Telegram channel).

No AI, no database and no server, so it costs €0 to run.

## How it works

| File | What it does |
|---|---|
| `ayudas/bdns.py` | Downloads announcements from the BDNS public API (Valencian region, aimed at individuals). |
| `ayudas/store.py` | Keeps a slim copy in `data/convocatorias.json`. Each run re-reads the last 45 days to pick up corrections such as extended deadlines. |
| `ayudas/topics.py` | Keyword rules in Spanish and Valencian that sort announcements into topics (babies, school, housing, bills...). |
| `ayudas/deadlines.py` | Works out application windows from official dates, or from periods like "10 días hábiles desde su publicación" counted from the bulletin date (Ley 39/2015, art. 30). |
| `ayudas/text.py`, `ayudas/places.py` | Readable titles and place names. |
| `ayudas/site.py` | Builds the static site: home page with filters, one page per town and per topic, RSS feeds, sitemap. |
| `ayudas/telegram.py` | Optional: posts new aid to a Telegram channel. |

Only the Python standard library is used.

## Run it locally (WSL)

```bash
cd ~/projects/ayudas-al-dia
python3 -m unittest discover -s tests
python3 -m ayudas update   # the first run looks back 180 days and takes a few minutes
python3 -m ayudas build
python3 -m http.server 8765 --directory public
```

Then open http://localhost:8765.

The commands are `update`, `build`, `notify` and `all`. Useful options: `--days` (how far back to
look), `--today` (pretend it's another date) and `--site-url` (public address, for RSS and sitemap).

## Put it online

It can go online for free at a GitHub address first and get its own domain later. Nothing in the
code changes when you add the domain. GitHub hosts the site and runs the daily job for free,
because the repository is public.

### 1. Free, on GitHub (no domain needed)

1. The name `ajudes` is taken on GitHub, so use **`ajud-es`** (names can't contain dots).
   If you already have a personal GitHub account, create a free **organization** called `ajud-es`
   (GitHub allows one free personal account per person). If not, sign up with that username.
2. In WSL, log in to GitHub once with `gh auth login` and follow the prompts.
3. Create the repository and push. Use a personal email for the commits rather than a work one,
   because they're public. GitHub's private address under **Settings → Emails** also works.

   ```bash
   cd ~/projects/ayudas-al-dia
   git init -b main
   git config user.email "YOUR-EMAIL"
   git add . && git commit -m "Primera versión de Ajudes"
   gh repo create ajud-es/ajud-es.github.io --public --source . --push
   ```

4. In the repository, go to **Settings → Pages → Build and deployment** and set **Source** to **GitHub Actions**.
5. In the **Actions** tab, open **Actualizar ayudas** and click **Run workflow**. From then on it runs
   every morning: it tests, downloads, commits `data/` and publishes.
6. The site appears at `https://ajud-es.github.io/`. Links, RSS and sitemap use that address
   automatically.

### 2. Later: your own domain

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
   | CNAME | www | ajud-es.github.io |

3. In the **organization's** settings, go to **Pages → Add a verified domain**, enter `ajud.es`, and
   add the TXT record GitHub shows you. This stops anyone else from using your domain on GitHub.
4. In the **repository's** settings, go to **Pages → Custom domain**, enter `ajud.es` and click Save.
   When the DNS check turns green (minutes to a few hours), tick **Enforce HTTPS**.

5. In **Settings → Secrets and variables → Actions → Variables**, add `SITE_URL` with the value
   `https://ajud.es/`, so links, RSS and sitemap use the domain.

### 3. After launch

- Add `ajud.es` to Google Search Console and submit `https://ajud.es/sitemap.xml`, so Google finds
  the town and topic pages.
- **Optional Telegram channel:** create a bot with @BotFather and make it an admin of your channel.
  Then add the secret `TELEGRAM_BOT_TOKEN` and the variables `TELEGRAM_CHAT_ID` (for example
  `@ajudes`) and `TELEGRAM_CHANNEL_URL`.
- **Before adding ads:** Spanish law (LSSI) asks sites with an economic activity to publish an
  "aviso legal" with the owner's name, NIF and contact email. Ads also need a cookie consent banner.
  Today the site uses no cookies.

## Data and terms

The data comes from the Sistema Nacional de Publicidad de Subvenciones y Ayudas Públicas (BDNS)
and is reused under its [terms](https://www.infosubvenciones.es/bdnstrans/GE/es/avisolegal).
Every page credits the source. The API is a free public service, so the client makes one request
at a time with a short pause.

## Known limits

- Deadlines given in working days ignore public holidays, so a real deadline can be a day or two
  later than shown, never earlier.
- Topics come from keywords in the title, so some announcements land in the wrong topic or in
  "Otras ayudas".
- Only announcements that the BDNS tags as aimed at individuals in the Valencian region are
  included. National programmes such as state scholarships are not covered yet.
- If the BDNS ever blocks GitHub's servers, run `python3 -m ayudas all` from a cron job in WSL
  instead. That is also free.
