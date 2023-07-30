## Textile App Prototype for ERPNext

The Textile App for is manufacturing workspace for [ERPNext](https://github.com/frappe/erpnext) that adds customizations for the textile manufacturing process.

The app workflow and design principle puts the user first, where only minimal user input is is required to ensure that production process and stock levels stay in sync in real-time. The app is in active development, and not ready for use in production environments.

## Features 🎁

### 1. Digital printing on textiles 🖨️ (developed, in optimization phase)
Adds a new **Print Order** Doctype for roll-to-roll printing.
- Create print orders for both repeats (seamless or rapport designs) and panels (with gaps between each panel).
- Automatically calculate print length based on design file dimensions, gaps, and required quantity.
- Automatically calculate fabric required based on above considerations and definable process wastage.
- Allows for choosing primary quantity based on fabric length or design length.
- Directly see production quantity on item level: printed quantity, packed quantity and delivered quantity.
- Accomodates for unprinted areas in printing head and tail.

Unique BOM concept for highly accurate stock consumptions.
- Flexible BOM's for reactive/disperse/pigment (based on linear-meters, area and weight), and sublimation (based on linear-meters and area).
- BOM's with drop-down on Print Order level to allow recipe selections at each step, e.g. coating and finishing.
- Smart BOM's for sublimation to ensure right papers are pre-selected based on fabric width.

### 2. Greige fabric pre-treatment ☀️  (in early development phase) 
Process steps for pre-treatment of greige fabrics: singeing, desizing, scouring, bleaching and washing.
- Independent BOM's for each process step.
- Accruate WIP stock for each process step.

## Roadmap & Wishlist ✨
- Extensive testing
- Piece goods manufacturing 👚 (planned for 2023)
-- Drag-and-drop production re-scheduling tool
- Yarn manufacturing 🧵 (planned for 2024)

## Support 🤗
Please contact us for any support or other inquiries via our website https://paralogic.io.

## Contributing 🤝
You can fork this repository and create a pull request to contribute code. By contributing to Textile App for ERPNext, you agree that your contributions will be licensed under its GNU General Public License (v3). 

## GNU/General Public License 
The ERPNext Pakistan Workspace code is licensed as GNU General Public License (v3) and the copyright is owned by ParaLogic and Contributors (see [license.txt](license.txt)).
