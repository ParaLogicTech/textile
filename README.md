## Textile ERP App for ERPNext

The Textile App is a manufacturing workspace for [ERPNext](https://github.com/frappe/erpnext) that adds workflows and
customizations for the textile manufacturing process. It is built and maintained by [ParaLogic](https://paralogic.io)
and is in production use at textile manufacturers.

The app workflow and design principle puts the user first, where only minimal user input is required to ensure that
production process and stock levels stay in sync in real-time.

> [!NOTE]
> This app only works on ParaLogic's forks of [Frappe](https://github.com/ParaLogicTech/frappe) and
> [ERPNext](https://github.com/ParaLogicTech/erpnext). It will not work on the official versions of Frappe or ERPNext.

## Features 🎁

### 1. Digital printing on textiles 🖨️
Adds a new **Print Order** DocType for roll-to-roll printing.
- Create print orders for both repeats (seamless or rapport designs) and panels (with gaps between each panel).
- Automatically calculate print length based on design file dimensions, gaps, and required quantity.
- Automatically calculate fabric required based on above considerations and definable process wastage.
- Allows for choosing primary quantity based on fabric length, design length or number of panels.
- Directly see production quantity on item level: printed quantity, packed quantity and delivered quantity.
- Maintains fabric traceability by batch numbers and packing labels.
- Generates fabric ledger for tracking every step of the production, packing and delivery process.
- Accommodates unprinted areas in printing head and tail, fabric shrinkage and scrapped fabrics.
- **Coating Order** for coating fabric as a separate process.
- **Fabric Printers** with the processes each printer can run.

Unique BOM concept for highly accurate stock consumptions.
- Flexible BOMs for reactive/disperse/pigment (based on linear-meters, area and weight), and sublimation (based on
  linear-meters and area).
- BOMs with drop-down on Print Order level to allow recipe selections at each step, e.g. coating and finishing.
- Smart BOMs for sublimation to ensure right papers are pre-selected based on fabric width.
- **Print Process Rules** pick the process, coating and softener items from the fabric's material and type.

### 2. Greige fabric pre-treatment ☀️
Adds a **Pretreatment Order** DocType with process steps for pre-treatment of greige fabrics: singeing, desizing,
scouring, bleaching and washing.
- Independent BOMs and operation tracking for each process step.
- Accurate WIP stock for each process step.
- **Pretreatment Process Rules** pick the item for each step from the fabric's material and type.

### 3. Pricing 💰
- **Print** and **Pretreatment Pricing Rules** price a fabric by its material, type, GSM and width, per price list
  and customer group. A base rate is adjusted by the rules that add, subtract or multiply.
- A customer can have its own base rate, and can be set to a fixed rate that the other rules don't adjust.

### 4. Textile items and customers 👕
- Textile item types (Greige Fabric, Ready Fabric, Printed Design, Print Process, Process Component) with their own
  properties: design size, gap and wastage; fabric material, type, width, GSM and construction; paper width and GSM.
- Customer defaults for print orders: unit of measure, gap, quantity type and length unit.
- Work Orders and Stock Entries for printing and pre-treatment are visible only to users with the matching print or
  pretreatment roles.

### 5. Reports and notifications 📊
- Fabric Ledger, Fabric Stock Balance, Fabric Packing List and Fabric Delivery Register.
- Print, Coating and Pretreatment Production Registers, and Fabric Printing Summary.
- Textile Email Digest: a daily email, built from an Email Template, sent at a chosen hour.

## How it extends ERPNext

textile changes ERPNext's own documents rather than replacing them. It subclasses the controllers of Item, Quotation,
Sales Order, Delivery Note, Sales Invoice, Packing Slip, Work Order and Stock Entry, adds form scripts and dashboard
links to them, and fills textile fields when documents are mapped from one another (e.g. Sales Order to Delivery
Note). Its Custom Fields on ERPNext DocTypes ship as fixtures.

## Installation

Create a bench from ParaLogic's frappe fork as described in [its README](https://github.com/ParaLogicTech/frappe),
then:

```bash
bench get-app https://github.com/frappe/payments --branch version-15
bench get-app https://github.com/ParaLogicTech/crm --branch version-15
bench get-app https://github.com/ParaLogicTech/erpnext --branch version-15
bench get-app https://github.com/ParaLogicTech/textile --branch version-15
bench --site <site> install-app textile
```

textile requires ParaLogic's ERPNext fork, which requires Payments and ParaLogic CRM. `version-15` is the only
maintained branch.

## Roadmap & Wishlist ✨
- Extensive testing
- Piece goods manufacturing (stitching) 👚
- Drag-and-drop production re-scheduling tool
- Yarn manufacturing 🧵

## Support 🤗
Please contact us for any support or other inquiries via our website https://paralogic.io.

Bugs can be reported as [issues](https://github.com/ParaLogicTech/textile/issues). Security issues: don't open a
public issue, report them privately as described in [SECURITY.md](SECURITY.md).

## Contributing 🤝
Branch from `version-15` and open a pull request against `version-15`. Commit messages follow
[Conventional Commits](https://www.conventionalcommits.org) (`fix: …`, `feat: …`). By contributing to the Textile
App, you agree that your contributions will be licensed under its GNU General Public License (v3).

## GNU/General Public License
The Textile App is licensed under the GNU General Public License (v3) and the copyright is owned by ParaLogic and
Contributors (see [license.txt](license.txt)).

## Screenshots

### Dashboard / Workspace

<img src="docs/screenshots/printing-workspace.png" alt="Printing Workspace" width="800">

### Print Order
<img src="docs/screenshots/print-order.png" alt="Print Order" width="800">

### Work Order List
<img src="docs/screenshots/work-order-list.png" alt="Work Order List" width="800">

### Simplified Production Entry
<img src="docs/screenshots/print-production-dialog.png" alt="Print Production Dialog" width="500">
