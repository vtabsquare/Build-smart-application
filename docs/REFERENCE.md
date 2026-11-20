# BuildSmart 360 v1.8

## Manage and rotate API credentials

Open `Edit Settings.cmd` to edit the included `.env` beside `run.py`. Replace the placeholders with your Google and Brevo settings. Keep your private settings when upgrading. Existing operating-system environment variables take precedence over the root file. An older `backend/.env`, if present, supplies keys missing from the root file. Use `--env-file` to select one explicit file instead. Start the server and run diagnostics with the same file and launch options.

```powershell
python run.py --check
python run.py --env-file .env --check
python run.py --env-file .env
```

`--check` shows which settings are present, where they came from, and the effective Google callback. It performs no provider calls. For production diagnostics, pass `--production` and the same port as your normal launch.

- **Brevo:** Update `BREVO_API_KEY` and, if needed, `BREVO_SENDER_EMAIL` and `BREVO_SENDER_NAME`. Restart. `BREVO_MAIL` is a fallback when the canonical sender setting is empty. Use `python run.py --check-email your-test-inbox@example.com` to send one test email, with the same `--env-file` if applicable.
- **Google:** If rotating the secret for the same client ID, update `GOOGLE_OAUTH_CLIENT_SECRET`, restart, and refresh the source. If the client ID changes or the saved grant expires, restart and sign in as a BuildSmart admin. Choose **Google Sheets Source → Reconnect Google**, then refresh. The new grant only replaces the old one after it can open the same spreadsheet. The original spreadsheet, its rates, and PDF links are preserved. A different OAuth project may need separate authorization to access files created by the original project. Use the original project if the new grant cannot open the Sheet.
- **Gemini:** If used, update `GEMINI_API_KEY` and, if needed, `GEMINI_MODEL`, then restart.

## Connect Google on your local installation

Start with `python run.py`. A local installation opens the browser setup first. If your browser is already on the Dashboard, click **Connect Google Sheets** next to the source banner, or open `http://127.0.0.1:5000/setup` directly. **Continue to BuildSmart** opens the existing local sign-in while Google is being configured.

Enable the **Google Sheets API** and **Google Drive API** in the OAuth client's Google Cloud project. For the default local launcher, register `http://127.0.0.1:5000/setup/google/callback` and set `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET` on the server. For another local port, register the callback on that port. You can use `GOOGLE_OAUTH_REDIRECT_URI` to set the exact callback explicitly. Restart the app and select **Connect with Google**. After sign-in, BuildSmart creates the spreadsheet and fills the four master tabs and the Estimates tab. Existing local accounts and estimates stay available.

New estimates created after Google connection are automatically archived as private PDFs in the connected account’s Drive. In the same spreadsheet, the **Estimates** tab records the estimate ID, project, customer, date, total, and PDF link. Files use the estimate ID as their filename. If Google is unavailable, the local estimate is still saved. Open its result and select **Save to Google** to retry. You can also use this button to archive an earlier estimate after connecting.

### Brevo mail configuration

The launcher reads your existing `.env`. Add the following using your actual key and verified sender. `BREVO_SENDER_EMAIL` is also supported and takes precedence when both sender variables are set. Restart BuildSmart after editing these values.

```dotenv
BREVO_API_KEY=
BREVO_MAIL=
BREVO_SENDER_NAME=BuildSmart 360
```

The sender settings are shared by estimate email, password reset, and security notifications.

## Deploy a new installation

The hosting operator configures OAuth and persistent storage once. The installer then completes setup in the browser, starting with Google Sheets. Use a separate persistent data directory for each installation. It holds accounts, projects, estimates, the active rate snapshot, and the Google connection token. Keep it private, restrict access to the app's service account, and back it up.

1. In Google Cloud, enable the **Google Sheets API** and **Google Drive API** and create an OAuth **Web application** client. Configure the Google consent screen for the people who will install BuildSmart. Add the exact callback, for example `https://buildsmart.example.com/setup/google/callback`, to **Authorized redirect URIs**. Use a published OAuth consent configuration for customer installations. Keep the same OAuth client after setup so BuildSmart can refresh its connection.
2. Set the following in the hosting service's environment or secret settings. Do not include secrets in source control.

| Setting | Value |
| --- | --- |
| `BUILDSMART_DATA_DIR` | Absolute path to private persistent storage for this installation |
| `BUILDSMART_SETUP_TOKEN` | Random setup code of at least 32 characters. Generate one with `python -c "import secrets; print(secrets.token_urlsafe(32))"` and share it privately with the installer |
| `GOOGLE_OAUTH_CLIENT_ID` | Google Web application OAuth client ID |
| `GOOGLE_OAUTH_CLIENT_SECRET` | Google OAuth client secret |
| `GOOGLE_OAUTH_REDIRECT_URI` | Exact public callback URL registered in Google Cloud |
| `BREVO_API_KEY` | Brevo API key for transactional email |
| `BREVO_SENDER_EMAIL` | Verified sender address in Brevo |
| `BREVO_SENDER_NAME` | Optional display name |

3. Start BuildSmart behind the host's HTTPS reverse proxy. For a container with a separate reverse proxy, use `--host 0.0.0.0` and the assigned port.

```powershell
python run.py --production --port 8000
```

4. Open your BuildSmart URL and enter the setup code. Select **Connect with Google**, sign in with the account that should own the Sheet, and approve access. BuildSmart creates a private spreadsheet in that account, adds the four tabs and sample rows, then validates the import. Enter the company details and create the first BuildSmart administrator. The company details are saved with new estimates and appear in their PDF exports. The setup screen closes after completion. You can remove the setup token from the host's settings.
5. Use **Admin → Google Sheets Source** to open your Sheet. Replace the illustrative rates with approved values, then refresh the source. Use **Admin → Company Branding** to update the company profile for future estimates. Saved estimates keep the company details captured when they were created.

To test email, use an inbox you control.

```powershell
python run.py --check-email you@example.com
```

The command prints the Brevo message ID when the request is accepted. Check your inbox or Brevo's transactional log for delivery confirmation.

An existing production installation can keep its configured Sheet and data directory. The service-account and preconfigured Sheet modes from v1.4 remain available. For a fresh browser-guided setup, leave `BUILDSMART_SHEET_ID`, `BUILDSMART_SHEETS_CONFIG`, and `BUILDSMART_ADMIN_PASSWORD` blank. A local Windows test can use `http://localhost:8000/setup/google/callback` with the same host and port registered in Google Cloud.

- [Google OAuth web application instructions](https://developers.google.com/identity/protocols/oauth2/web-server)
- [Brevo senders and domains](https://developers.brevo.com/docs/getting-started-with-senders-and-domains)

## Local testing and upgrades

Version 1.3 introduces the architectural sign-in screen, redesigned Builder and Admin dashboards, refreshed navigation and forms, and a keyboard-accessible estimate stepper. It includes the compiled frontend, transactional estimate saving, and PDF export using the rate source captured with each estimate.

To upgrade an existing installation, stop BuildSmart and back up its `data` directory. Extract this release into a new folder, copy your existing `data` directory into it, and run `python run.py`. The database remains in SQLite format. Retain any local `.env` settings you already use.

This version restores the recovered React screens and Python estimation API without requiring the original Supabase database. Google Sheets supplies estimation master data; local SQLite stores accounts, projects, saved estimates, and imported snapshots.

## Start with one command

1. Install a standard **Python 3.11 or 3.12** distribution with Python on PATH.
2. Extract the whole ZIP to a folder. Open a terminal in that folder.
3. Run:

```powershell
python run.py
```

The script creates `.venv`, installs Python packages on the first run, creates local test accounts, starts the server, and opens the application. Internet is required for the first dependency installation. The production frontend is included, so **Node.js is not required for ordinary use**.

The local address is `http://127.0.0.1:5000`. Press **Ctrl+C** in the terminal to stop the server.

### Your configured sign-in

Sign in with **vigneshrajas.vtab@gmail.com** and your configured local password. The local launcher applies this account setup once and preserves subsequent password changes.

For an existing installation: stop the app, replace the code with this update while keeping your `data` folder, and run `python run.py` again. This local sign-in does not change your Gmail account or the old hosted application.

The local launcher also creates `admin@buildsmart.test` and `builder@buildsmart.test`. It displays their random passwords on first launch and saves them to `data/first_run_accounts.txt`. Sign-in opens the workspace associated with the account role.

If port 5000 is busy:

```powershell
python run.py --port 5050
```

Other commands:

```powershell
python run.py --check
python run.py --no-browser
python run.py --test
python run.py --reset-password admin@buildsmart.test
```

Password recovery prompts privately in the terminal and revokes the old sessions. The optional `--no-install` flag uses the current Python environment instead of creating a private environment.

## Connect a Google Sheet

The application starts with clearly labelled **illustrative sample rates**. They are test values, not current supplier quotations.

1. Create a Google spreadsheet.
2. Import each CSV from `app/sample_data` into a separate tab, with headers in row 1.
3. Use the tab names below, or enter your own tab names in the mapping screen.
4. For a public test sheet, share as **Anyone with the link → Viewer**. For private data, use the service-account setup below.
5. Log in as Admin and open **Google Sheets Source**.
6. Choose **Google Sheets**, paste the spreadsheet URL or ID, and select the access mode.
7. Map each application field to the exact header in your sheet. Header matching is case-sensitive.
8. Click **Test connection and mapping**, then **Validate and activate**.

| Default tab | Required header names | Purpose |
| --- | --- | --- |
| `material_master` | `code`, `name`, `category`, `unit` | Material catalogue and display units |
| `material_rates` | `city`, `material_code`, `rate`, `vendor` | Construction package and material rates |
| `system_settings` | `key`, `value` | Add-on rates, inclusions, default contingency |
| `city_indexes` | `city`, `state`, `cost_index` | Preserved city-index configuration |

All four tabs must contain at least one valid row. `vendor` and `state` values can be empty, but their headers must exist. Extra columns are ignored. Avoid merged cells, repeated headers, and summary rows inside these tables.

Mapping example: if your rates tab is `Test Prices` and its headers are `Town`, `Item`, `Price`, and `Supplier`, map:

| Application field | Sheet header |
| --- | --- |
| `city` | `Town` |
| `material_code` | `Item` |
| `rate` | `Price` |
| `vendor` | `Supplier` |

Keep a `Default` city rate for each construction package: `CONSTRUCTION_BASE`, `CONSTRUCTION_STANDARD`, `CONSTRUCTION_PREMIUM`, and `CONSTRUCTION_LUXURY`. A city-specific material rate overrides the matching Default rate. Every material code must exist in `material_master`. Rates must be finite, non-negative numbers; the importer accepts comma-separated numeric text but not currency symbols. For sand and aggregates, the stored rate is INR per cubic foot; the original UI displays 100 cubic feet as one Unit.

The rate for `CONSTRUCTION_STANDARD` in `material_rates`, for example, takes precedence over the `rate_package_standard` fallback in settings. Boolean inclusion settings use `true` or `false`. `city_indexes` remains available for compatibility; the recovered calculation engine does not apply a city multiplier.

After editing a sheet, click **Refresh saved source**. Refresh is manual. All tables, mappings, and provenance are activated together after validation. A failed import keeps the previous snapshot. Saved estimates retain their original costs, inputs, BOQ and source timestamp. Rates and settings are read-only in the app while Google Sheets is active; edit them in the sheet instead. Switching to sample mode replaces only estimation masters, not saved projects or accounts.

## Private Google Sheets

1. Enable Google Sheets API in a Google Cloud project.
2. Create a service account and download its JSON credential file.
3. Store that file outside this source folder.
4. Share only the test spreadsheet with the service-account email as Viewer.
5. Edit the included `.env` in the extracted project root. The relevant settings are:

```dotenv
GOOGLE_APPLICATION_CREDENTIALS=C:/private-keys/buildsmart-reader.json
```

Restart the app, select **Private sheet (service account)**, and validate the connection. This adapter requests read-only Sheets access. No Google credential is stored in the browser or mapping database.

## Optional email and AI

The launcher reads an existing root `.env` or `backend/.env`. It does not create or overwrite either. No external API credentials are included in this package; the requested local test login is provisioned from a password hash. Supabase variables from the previous deployment are unused in this edition. The supplied configuration template has placeholders only.

To enable optional services, configure your current keys privately:

```dotenv
BREVO_API_KEY=YOUR_CURRENT_KEY
BREVO_SENDER_EMAIL=YOUR_VERIFIED_SENDER
BREVO_SENDER_NAME="Vtab square"
GEMINI_API_KEY=YOUR_CURRENT_API_KEY
GEMINI_MODEL=gemini-2.5-flash
```

Brevo email sharing and email OTP recovery require a configured sender and a working gateway. Without them, the app returns an explicit configuration error; local password recovery remains available through `run.py`. Gemini is used only for recommendations. Arithmetic runs locally, and static recommendations are used if AI is unconfigured or unavailable. Set `GEMINI_MODEL` to a model available to your API project. These external services are not required to create estimates or download PDF/Excel files.

## Data, calculations, and source changes

- Local data is in `data/buildsmart.sqlite3`. Stop the app before copying the whole `data` folder for backup. Do not delete that folder to upgrade code.
- The recovered engine uses a construction package rate per built-up sqft. Listed materials are included in the package and are not added again. Add-on items are priced separately unless marked included.
- Built-up area includes floor area, portico and staircase area. Legacy `totalSqft` input now works when no floor list is provided. Invalid or non-finite geometry is rejected before a project is saved. A zero contingency is preserved.
- The original engine keeps GST and builder margin at zero. This recovery does not introduce new tax or pricing rules.
- The source boundary is `app/services/db.py`. Its local implementation is `local_db.py`. Supabase-style variable names preserve the recovered route contracts.
- `sheets_source.py` implements tab/header mapping, validation, public CSV and private Sheets API import. `routes/source.py` exposes the admin-only source actions.
- `app/web/src/pages/admin/DataSource.jsx` is the connection and mapping screen.
- API URLs and file exports now use the same origin. The Python server serves the bundled UI and all API routes.
- `app/web/src/router.jsx` provides navigation for the web interface.

To edit the React UI, install Node.js 22.12+ and run `python run.py --rebuild`. This installs the locked frontend dependencies and rebuilds the UI. The packaged UI was built with available local build dependencies; a fresh registry install was blocked in the reconstruction environment.

## Verification and limits

See `RECOVERY_NOTES.md` for the recovered revision, tests, and remaining checks. No live Google Sheet or final service credentials were supplied for testing. Live Sheets, Gemini and Brevo calls were not performed. The automated tests use isolated temporary data and mock external source responses. The browser connection failed during visual validation, so a full browser walkthrough remains to be checked on your computer.

This package is intended for local testing. It binds to loopback, uses local test accounts, and does not deploy or modify the original hosted application. The older files in `security_documents` describe the original project; they are historical documents, not a security certification of this reconstructed version.
