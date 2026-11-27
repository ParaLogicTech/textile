# Agent instructions

This repository is **textile**, ParaLogic's textile manufacturing app (fabric printing, coating and pre-treatment). It
runs on ParaLogic's forks of [Frappe](https://github.com/ParaLogicTech/frappe) and
[ERPNext](https://github.com/ParaLogicTech/erpnext), not stock Frappe or ERPNext. Those forks differ from upstream
(frappe's FORK.md lists how), and ERPNext's in particular has diverged a lot. Documentation for stock ERPNext, and your
own knowledge of it, often doesn't match: read the code of the apps on this bench.

## Where it sits

frappe fork → crm → ERPNext fork → **textile** → apps that build on textile. Dependencies point downward: textile may
use erpnext, crm and frappe, never an app above it.

## How textile changes ERPNext

- **Controllers**: `override_doctype_class` in `hooks.py` replaces the controllers of Item, Quotation, Sales Order,
  Delivery Note, Sales Invoice, Packing Slip, Work Order and Stock Entry with subclasses named `<DocType>DP`
  (`SalesOrderDP`). They subclass erpnext's class and call `super()`; don't re-implement erpnext's methods.
- **Apps above textile subclass the `*DP` classes** in turn. Before renaming or changing a method of one, check the
  apps that extend it.
- **Hooks**: code that hooks into another app lives in `textile/overrides/`, one `<doctype>_hooks.py` and
  `<doctype>_hooks.js` per DocType (flat layout). erpnext's fork provides `update_*` hooks (mappers, item details,
  defaults) that textile registers in `hooks.py`; prefer those over overriding a whole method.
- **Custom Fields** on other apps' DocTypes are listed by name in the `fixtures` filter in `hooks.py`. Add new ones to
  that list and export with `bench --site <site> export-fixtures --app textile`. Keep the filter by name so it doesn't
  capture other apps' customisations.

## Rules for changes

- **Branch** from `version-15` and target `version-15` in pull requests.
- **Style**: tabs and double quotes in new code. Name functions for what they do, and comment only what the code
  doesn't make clear.
- **Tests**: the test suite is outdated and not run in CI. Don't rely on it to verify a change: check it on a site
  with textile installed, with console scripts that roll back and in the Desk.
- **Patches** go in `textile/patches.txt` and must be idempotent. Keep old patches.
- **DocType changes**: save through the Desk or `bench console` in developer mode, which exports the JSON. Don't
  hand-edit DocType JSON.
- **Commit messages** follow Conventional Commits (`fix: …`, `feat: …`, `docs: …`), one subject line.
- **No customer details**: don't name clients or quote client data in code, comments, commits or pull requests.
  Describe cases generically.
