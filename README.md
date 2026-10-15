# Factory Simulation Model - Original

## Objective

Understand whether a production plan is feasible with the factory's available machines, people, materials, and working calendar. This basic discrete-event simulation helps investigate bottlenecks, staffing requirements, and the completion dates that emerge when products compete for limited resources.

Instead of assuming that every order can be completed on schedule, the model simulates the work required for each product and its components. Change the Excel inputs to compare scenarios such as additional parallel machines, different shift patterns, workforce availability, or starting inventory.

![Model overview: Excel inputs feed a production-event log that supports capacity and planning analysis.](docs/images/model-overview.png)

*Source: slide 3 of [Factory simulation model - basic version](factory%20simulation%20model%20basic.pptx). Some analyses shown in the presentation require downstream processing or extensions; they are not built-in reports.*

## What Is Included

| File | Purpose |
| --- | --- |
| [sim_factory.py](sim_factory.py) | Original Python simulation, implemented with SimPy and pandas. |
| [sim_factory_inputs.xlsx](sim_factory_inputs.xlsx) | Example scenario and Excel input tables. |
| [factory simulation model basic.pptx](factory%20simulation%20model%20basic.pptx) | Restyled presentation with the worked example, process diagrams, and historical installation instructions. |
| [docs/images](docs/images) | Five slide images exported from the presentation for this README. |

This repository preserves the original simulator and example workbook. The presentation has a refreshed palette, with the original cover, closing slide, and unused branded layouts removed. It is a command-line model, not a graphical factory application or an automatic scheduling optimizer.

## How It Works

1. **Create the factory.** Read the workbook and create a SimPy environment, work cells, input queues, product codes, initial inventories, and a shared pool of production workers.
2. **Release production orders.** At each order's requested start time, create one `ProductionBox` for every requested finished unit. Each box carries its original order and finished-product references.
3. **Resolve component requirements recursively.** Check stock for the requested code first. If stock exists, consume one unit and signal readiness. Otherwise, create boxes for the components listed in the bill of materials and wait for all of them to become ready.
4. **Queue and process the code.** Send the box to its assigned work cell. Each parallel cell processes its queue, performs setup when the code changes, and carries out production subject to its shift calendar and the required workers being available.
5. **Wait for external lead time.** Where configured, complete procurement or another external delay before signalling that the code is ready. The cell can move to another box while this delay runs.
6. **Unblock parent assemblies and record events.** Completed components release waiting parent boxes. The observer records warehouse withdrawals, setup, production, and external lead-time events, then exports the history after the run.

`ProductionBox` objects act like software kanban cards: they express a requirement and expose a readiness event. Components are requested down the product tree, but fabrication proceeds from ready subcomponents back toward the finished product.

![Recursive production boxes follow the bill of materials from a finished product to its subcomponents.](docs/images/recursive-production.png)

*Source: slide 23. The component cascade creates the dependencies that must be satisfied before assembly can proceed.*

![A work cell takes a queued production box, acquires workers, and performs the required work.](docs/images/work-cell-process.png)

*Source: slide 25. Setup and production consume working time; external procurement can add a separate lead time.*

### Main Objects

| Class | Responsibility |
| --- | --- |
| `SimFactory` | Loads inputs, creates resources, releases orders, and advances the simulation. |
| `ProductCode` | Holds component requirements, work-cell assignment, processing parameters, and stock. |
| `ProductionBox` | Resolves one unit's material requirements and signals when that unit is ready. |
| `WorkCell` | Controls opening hours, setup, production, worker allocation, and external delays. |
| `FactoryObserver` | Collects timestamped events and writes the output files. |

## Excel Inputs

Keep the workbook beside the script and run from that directory. `INPUT_FILE` is a relative filename in the source. The simulator reads these seven worksheets; the workbook also contains supporting example sheets that the script does not load.

| Worksheet | Key columns | Role |
| --- | --- | --- |
| `production_start` | `order_line_number`, `product_code`, `number_of_products`, `request_time` | Finished-product order releases. `request_time` is an offset in days, converted to simulation hours. Descriptive columns such as `client` and `request_date` are not used to schedule orders. |
| `bom` | `code_produced`, `code_used`, `quantity` | Parent/component relationships and the number of component units required. |
| `bol` | `code_produced`, `work_cell_used`, `setup_time`, `setup_crew`, `production_time`, `production_crew`, `lead_time_days` | Bill of labour: cell assignment, setup and production hours per unit, crew sizes, and external lead time in days. |
| `codes_descriptions` | `code_name`, `description`, `classification` | Product and component catalogue. |
| `work_cells` | `work_cell`, `description`, `department`, `number_of_equal_cells`, `shift_pool` | Work-cell definitions, parallel capacity, and calendar assignment. |
| `initial_warehouse` | `code`, `quantity` | Units already available at the beginning of the simulation. |
| `shifts` | `day`, `date`, `blue_collars_per_shift`, `shift_hours`, `shifts_A` | Daily workforce and opening calendar. A cell's `shift_pool` selects a `shifts_<pool>` column; the example uses pool `A`. |

The bill of materials is tabular rather than hard-coded: a component may itself have components, and a finished product may also be used in another product.

![The example bill of materials shows product trees and their equivalent Excel relationships.](docs/images/bill-of-materials.png)

*Source: slide 7. Quantities on each relationship determine how many child boxes the model creates.*

### Scenario Constraints

- Use consistent code and work-cell identifiers across worksheets. Every code needs a bill-of-labour row and a valid cell assignment.
- Keep the bill of materials acyclic. The original code does not detect circular dependencies or validate the workbook schema.
- Use nonnegative durations and whole-number unit counts, component quantities, parallel-cell counts, and crew sizes. The code uses several workbook values directly in `range()` calls.
- Ensure requested crews can be supplied by the workforce calendar. Impossible resource requirements can leave production waiting indefinitely within the simulated horizon.
- The calendar logic assumes up to three eight-hour shift slots per day. `shift_hours` is the working portion of each slot; the remainder is closed time.
- Preserve the example's calendar structure when experimenting. The implementation reads `date` at day index `0`, but selects daily staffing and opening rows using `floor((end_time - env.now) / 24)`. Calendar lookup therefore runs through day indices in descending order even though simulation time advances forward.

## Running the Original Version

### Compatibility First

**This is legacy source, not a verified modern-Python release.** It calls `pd.read_excel(..., sheetname=...)` and uses pandas `.ix`, both absent from current pandas versions. Installing current pandas and SimPy is not sufficient to run it unchanged.

The dependencies are Python, pandas, SimPy, and an Excel reader compatible with that pandas version. The other imports are Python standard-library modules. The original presentation recommends Anaconda, SimPy, and optionally PyCharm; an IDE is not required.

For historical reproduction, the following is a **candidate isolated environment**, not a tested dependency lock or a guaranteed installation recipe:

```shell
conda create -n sim-factory-original python=3.6 pandas=0.24.2 xlrd=1.2.0 pip
conda activate sim-factory-original
python -m pip install simpy==3.0.11
```

These versions are obsolete and may be unavailable for your platform, especially Windows ARM64. Use a suitable isolated legacy environment or VM, not a production Python installation. No end-to-end execution of this historical environment has been verified for this repository. A supported modern runtime would require a separate compatibility update and regression checks.

### Execute

Once a compatible environment is available:

```shell
git clone https://github.com/faustinopalma/sim_factory_original.git
cd sim_factory_original
python sim_factory.py
```

The script constructs `SimFactory`, calls `start(step=1)`, writes the output, and prints elapsed wall-clock time. It also executes immediately when imported because it has no `if __name__ == '__main__'` guard.

The run prints progress dates. Its maximum calendar horizon is `max(shifts.day) * 24` hours, but the current loop advances only to the points generated by `range(step, end_time, step * 24 * 7)`. With the default `step=1`, those points are one hour after the start and then one week apart; the script does **not** perform a final run to the exact calendar horizon. Interpret incomplete orders accordingly.

## Outputs and Interpretation

Each execution creates a timestamped directory:

```text
outputs/
  output_YYYY-MM-DD_HHMMSS/
    sim_factory_inputs.xlsx
    production_history.csv
```

The copied workbook preserves the scenario used for that run. The CSV contains the recorded events, with an additional pandas index column because the original exporter uses the default `to_csv()` options.

| Field | Meaning |
| --- | --- |
| `time`, `week`, `month` | Event timestamp and calendar buckets; weeks start on Monday. |
| `product`, `originating_order` | Finished product and original order responsible for the activity. |
| `code` | Product or component involved in the event. |
| `activity` | `take_from_warehouse`, `setup`, `production`, or `external_lead_time`. |
| `work_cell` | Cell responsible for processing, when applicable. |
| `worked_time`, `crew` | Hours in that recorded setup/production segment and workers assigned. |
| `lead_time` | External delay in hours, when applicable. |
| `work_completion` | `work_complete` on the last production segment of a finished-product box. |

Fields are populated only when applicable, so some columns contain blanks. Setup and production may span multiple events when interrupted by closed shifts.

![The event history can be pivoted into machine-utilization and completion-date analyses.](docs/images/simulation-output.png)

*Source: slide 15. The script writes CSV, even though the presentation refers more generally to a spreadsheet.*

Typical downstream analyses in Excel or pandas include:

- **Cell workload:** sum `worked_time` for setup and production by `work_cell` and `week`, then compare with the configured opening hours and parallel capacity.
- **Labour demand:** sum `worked_time * crew` by week to obtain worker-hours, rather than machine-hours.
- **Finished production:** filter `work_completion == 'work_complete'` and group by product and order to count units completing production over time.
- **What-if comparisons:** compare event logs from runs with different demand, staffing, calendars, stock, or cell counts.

The completion marker is recorded **before** any subsequent external lead time. It is not automatically a delivery-ready timestamp for a finished product with a nonzero lead time. Finished units satisfied directly from starting inventory generate a warehouse event instead of this marker. The log has no unique per-unit box identifier, so reconstructing individual delivery dates can require additional instrumentation.

## Scope and Limitations

The basic version uses fixed processing and lead times, one assigned work cell per code, FIFO input queues, a shared worker pool, and setup whenever a parallel cell switches product code. Initial stock is consumed before new work is requested; completed boxes signal their requester rather than replenishing a general finished-goods warehouse.

It does not implement demand optimization, random breakdowns, learning curves, purchase costing, or automatic charts and pivots. The presentation discusses these as possible analyses or extensions, not features already implemented in the Python file. Results depend on the input scenario and the original scheduling assumptions; validate them before using them for operational decisions.

## Presentation Reference

This README follows the [Factory simulation model - basic version presentation](factory%20simulation%20model%20basic.pptx): objectives and model overview (slides 2-3), input example (6-13), output interpretation (15-19), implementation logic (21-26), and extensions and historical setup (28-34). Slide references use the updated 34-slide presentation. The five images above are direct exports from the restyled slides, not screenshots of a newly executed simulation.