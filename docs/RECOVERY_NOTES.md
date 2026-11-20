# Recovery record

Upstream repository: https://github.com/Gokulrohit45/Buildsmart_estimator

Recovered commit: 2d727f5edab3b4e7ab7121544cfe870e801aaf73

## Findings

The repository contained the React pages, Flask routes, calculation engine and export code. It did not contain the Supabase schema, database seed data, complete environment setup or a portable launcher. Its backend stopped at import time without Supabase credentials. Its admin utility referenced a developer-specific drive path. Several frontend exports hard-coded localhost:5000. The legacy estimator test also supplied totalSqft while the engine expected a floor list, yielding zero construction area.

## Reconstructed behavior

The original route contracts now use a local SQLite adapter, hashed passwords and expiring opaque sessions. Source masters can be loaded from Google Sheets using editable tab and header mappings. Source changes are published transactionally. Account approval, project ownership checks, project deletion cascades, saved estimate versions and original exports remain functional. First-run account setup is idempotent. The UI and API are served together by the single Python launcher.

The source engine and page workflows are preserved. The decorative PNG background could not be retrieved through the available repository connector and was replaced with a CSS gradient. Unused PNG assets are not included. Navigation uses a small first-party History API router for the existing flat routes. Reopening a saved estimate now uses its persisted calculation output instead of reconstructing incomplete cost fields.

## Validation

The backend integration suite covers authentication, registration, permissions, blocked sessions, arithmetic, zero contingency, geometry validation, legacy area input, persistence, versioning, ownership, cascading deletion, PDF and Excel output, source preview, activation, import failure retention, custom CSV header mapping, invalid source data, first-run account idempotency and session revocation after password reset. Tests use temporary data and no real secrets. Production frontend bundling succeeded.

Result: 16 integration tests passed. The built frontend, direct page refresh, and bundled assets were also served successfully by Flask. The test runtime used Python 3.13.14, Flask 3.1.3, ReportLab 4.4.9 and openpyxl 3.1.5. Backend package pins match the tested Flask/ReportLab/openpyxl versions.

The supplied run.py prerequisite check succeeded. Full first-run package installation could not be tested because this environment could not resolve package registry hosts. The production UI was built with existing installed React/Vite dependencies. Browser interaction could not be verified because the connected browser session returned an error. No production deployment, original database migration, live email, Gemini call, or live user spreadsheet read was performed.

## Before your test

Run python run.py, use the generated local test credentials, import the four CSV templates into Google Sheets, activate the connection in Admin, and generate an estimate as Builder. Change CONSTRUCTION_STANDARD in the sheet and refresh: a new estimate should change, while saved estimates should retain their earlier values.

Use new private credentials for optional services. No .env, API key, service-account JSON, local database, or first-run password file is included in the ZIP. The requested local Builder login is included as a salted password hash and an idempotent startup migration.
