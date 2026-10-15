import pandas as pd
import simpy
import timeit
import math
import collections
import os
import shutil
import datetime

INPUT_FILE = 'sim_factory_inputs.xlsx'


class SimFactory:
    def __init__(self):
        # read input file
        self.production_start = pd.read_excel(INPUT_FILE, sheetname='production_start')
        self.production_start.loc[:, 'request_time'] *= 24  # converts from days to hours
        self.bom = pd.read_excel(INPUT_FILE, sheetname='bom', index_col='code_produced')
        self.bol = pd.read_excel(INPUT_FILE, sheetname='bol', index_col='code_produced')
        self.codes_descriptions = pd.read_excel(INPUT_FILE, sheetname='codes_descriptions')
        self.work_cells_table = pd.read_excel(INPUT_FILE, sheetname='work_cells', index_col='work_cell')
        self.initial_warehouse = pd.read_excel(INPUT_FILE, sheetname='initial_warehouse', index_col='code')
        self.shifts = pd.read_excel(INPUT_FILE, sheetname='shifts', index_col='day')

        # sets key working objects and variables
        self.env = simpy.Environment()
        self.start_date = self.shifts.ix[0, 'date']  # it is the first date in the shifts sheet
        self.end_time = self.shifts.index.max() * 24

        # set blue collars
        self.number_of_blue_collars = 0
        self.blue_collars = simpy.Container(self.env, init=0)
        self.blue_collars_token = simpy.PreemptiveResource(self.env, capacity=1)

        # set wip-locations and work-cells
        self.input_wip_locations = {}
        """:type : dict[str, simpy.FilterStore]"""
        self.work_cells = {}
        """:type : dict[str, WorkCell] """
        for cell_name, cell_data in self.work_cells_table.iterrows():
            input_wip_location = simpy.FilterStore(self.env)
            self.input_wip_locations[cell_name] = input_wip_location
            work_cell = WorkCell(name=cell_name,
                                 description=cell_data['description'],
                                 department=cell_data['department'],
                                 number_of_equal_cells=cell_data['number_of_equal_cells'],
                                 shift_pool=cell_data['shift_pool'],
                                 input_wip_location=input_wip_location,  # specifies where the wip is stored
                                 factory=self)
            self.work_cells[cell_name] = work_cell

        # set codes and bom connections
        self.codes = {}
        for index, code_data in self.codes_descriptions.iterrows():
            code_name = code_data['code_name']
            code_description = code_data['description']
            code_classification = code_data['classification']
            new_code = ProductCode(factory=self, code_name=code_name,
                                   description=code_description, classification=code_classification)
            new_code.set_warehouse()
            self.codes[code_name] = new_code

        for code in self.codes.values():
            code.connect_components()

        # set factory observer, which will record events and write output files
        self.observer = FactoryObserver(self)

    def blue_collar_availability_process(self):
        while True:
            time = (self.end_time - self.env.now)
            day = math.floor(time/24)
            blue_collars_today = self.shifts.loc[day, 'blue_collars_per_shift']
            if blue_collars_today > self.number_of_blue_collars:
                with self.blue_collars_token.request(priority=1000, preempt=False) as token:
                    yield token
                    yield self.blue_collars.put(blue_collars_today - self.number_of_blue_collars)
                    self.number_of_blue_collars = blue_collars_today
            elif blue_collars_today < self.number_of_blue_collars:
                with self.blue_collars_token.request(priority=1000, preempt=False) as token:
                    yield token
                    yield self.blue_collars.get(self.number_of_blue_collars - blue_collars_today)
                    self.number_of_blue_collars = blue_collars_today
            yield self.env.timeout(24)

    def schedule_production_start(self, product, number_of_cables, delta_time, originating_order):
        yield self.env.timeout(delta_time)
        code = self.codes[product]
        """:type : ProductCode"""

        for i in range(number_of_cables):
            production_box = ProductionBox(requester='none', code_to_be_kitted=code,
                                           originating_order=originating_order, product=product)

    def start(self, step):
        # activates  processes that keep the factory working
        for work_cell in self.work_cells.values():
            for i in range(work_cell.number_of_equal_cells):
                self.env.process(work_cell.door_keeper_process())
                self.env.process(work_cell.produce_or_purchase())
        self.env.process(self.blue_collar_availability_process())

        # inserts demanded orders in the simulation
        for index, production_start in self.production_start.iterrows():
            self.env.process(
                self.schedule_production_start(product=production_start['product_code'],
                                               number_of_cables=production_start['number_of_products'],
                                               delta_time=production_start['request_time'],
                                               originating_order=production_start['order_line_number']))

        # starts the simulation advancing the time backward in steps while writing the progress to the console
        for advance_to_time in range(step, self.end_time, step*24*7):
            print(self.start_date + pd.offsets.Hour(advance_to_time))
            self.env.run(advance_to_time)


class FactoryObserver:
    def __init__(self, factory: SimFactory):
        self.production_history = collections.deque()
        self.factory = factory

    def time_now(self):
        return self.factory.start_date + pd.offsets.Hour(self.factory.env.now)

    def record(self, record_data):
        time = self.time_now()
        week = time - pd.offsets.Day(time.weekday())
        week = week.replace(hour=0, minute=0, second=0, microsecond=0)
        month = time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        data = {'time': time, 'week': week, 'month': month}
        data.update(record_data)
        self.production_history.append(data)

    def write_output(self):
        outputs_folder = 'outputs'
        if not os.path.exists(outputs_folder):
            os.makedirs(outputs_folder)
        output_folder_name = 'output_{date:%Y-%m-%d_%H%M%S}'.format(date=datetime.datetime.now())
        output_folder_name = os.path.join(outputs_folder, output_folder_name)
        if not os.path.exists(output_folder_name):
            os.makedirs(output_folder_name)
        shutil.copyfile(INPUT_FILE, os.path.join(output_folder_name, INPUT_FILE))

        production_history = pd.DataFrame(list(self.production_history))
        file_path = os.path.join(output_folder_name, 'production_history.csv')
        production_history.to_csv(file_path)


class ProductionBox:
    def __init__(self, requester, code_to_be_kitted, originating_order, product):
        """
        :type requester: ProductionBox
        :type code_to_be_kitted: ProductCode
        """
        # set input parameters
        self.code_to_be_kitted = code_to_be_kitted
        self.env = self.code_to_be_kitted.factory.env
        self.requester = requester
        self.originating_order = originating_order
        self.product = product
        self.product_ready = simpy.Event(self.env)
        self.env.process(self.kit_code())

    def kit_code(self):
        yield self.env.timeout(0)
        with self.code_to_be_kitted.warehouse_access_token.request() as request:
            if len(self.code_to_be_kitted.warehouse) > 0:
                self.code_to_be_kitted.warehouse.pop()
                self.product_ready.succeed()
                data_to_record = {
                    'product': self.product,
                    'originating_order': self.originating_order,
                    'code': self.code_to_be_kitted.code_name,
                    'activity': 'take_from_warehouse'
                }
                self.code_to_be_kitted.factory.observer.record(data_to_record)
            else:
                all_components_stoplight = []
                for row in self.code_to_be_kitted.components:
                    component = row['component']
                    """:type : ProductCode"""
                    quantity = row['quantity']
                    for i in range(quantity):
                        production_box = ProductionBox(requester=self, code_to_be_kitted=component,
                                                       originating_order=self.originating_order,
                                                       product=self.product)
                        all_components_stoplight.append(production_box.product_ready)
                yield simpy.AllOf(self.env, all_components_stoplight)
                self.code_to_be_kitted.input_wip_location.put(self)


class WorkCell:
    def __init__(self, name, description, department, number_of_equal_cells, shift_pool,
                 input_wip_location: simpy.FilterStore, factory: SimFactory):
        self.name = name
        self.description = description
        self.department = department
        self.number_of_equal_cells = number_of_equal_cells
        self.number_of_shifts_head = 'shifts_' + shift_pool
        self.shift_hours_head = 'shift_hours'
        self.input_wip_location = input_wip_location
        self.factory = factory
        self.door_is_open = False
        self.door_opened = simpy.Event(self.factory.env)
        self.time_when_door_will_shift = 0

    def time_to_door_shift(self):
        return self.time_when_door_will_shift - self.factory.env.now

    def door_keeper_process(self):
        while True:
            time = (self.factory.end_time - self.factory.env.now)
            day = math.floor(time/24)
            shift_hours = self.factory.shifts.loc[day, self.shift_hours_head]
            number_of_shifts = self.factory.shifts.loc[day, self.number_of_shifts_head]

            for i in range(number_of_shifts):
                self.door_is_open = True
                self.door_opened.succeed()
                self.door_opened = simpy.Event(self.factory.env)
                self.time_when_door_will_shift = self.factory.env.now + shift_hours
                yield self.factory.env.timeout(shift_hours)
                self.door_is_open = False
                self.time_when_door_will_shift = self.factory.env.now + 8 - shift_hours
                yield self.factory.env.timeout(8 - shift_hours)
            for i in range(3 - number_of_shifts):
                self.door_is_open = False
                self.time_when_door_will_shift = self.factory.env.now + 8
                yield self.factory.env.timeout(8)

    def produce_or_purchase(self):
        previously_produced_code = ""
        while True:
            production_box = yield self.input_wip_location.get()
            """:type : ProductionBox"""
            code_produced = production_box.code_to_be_kitted

            base_data_to_record = {
                'product': production_box.product,
                'originating_order': production_box.originating_order,
                'code': code_produced.code_name,
                'work_cell': self.name
            }

            priority_on_blue_collars = 10

            if previously_produced_code != code_produced.code_name:
                # set previously_produced_code variable to decide whether to execute the setup at the next cycle
                previously_produced_code = code_produced.code_name
                # setup cycle
                setup_time = code_produced.setup_time
                working_time_performed = 0
                while working_time_performed < setup_time:
                    if self.door_is_open:
                        # adjust workers to setup crew
                        setup_crew = code_produced.setup_crew
                        if setup_crew > 0:
                            with self.factory.blue_collars_token.request(priority=priority_on_blue_collars,
                                                                         preempt=False) as token:
                                yield token
                                priority_on_blue_collars = 100
                                yield self.factory.blue_collars.get(setup_crew)

                        # perform the setup
                        if self.door_is_open:
                            worked_time = min(setup_time - working_time_performed,
                                              self.time_to_door_shift())
                            yield self.factory.env.timeout(worked_time)
                            working_time_performed += worked_time
                            data_to_record = base_data_to_record.copy()
                            data_to_record['worked_time'] = worked_time
                            data_to_record['crew'] = setup_crew
                            data_to_record['activity'] = 'setup'
                            self.factory.observer.record(record_data=data_to_record)

                        # release workers after the job is complete
                        if setup_crew > 0:
                            yield self.factory.blue_collars.put(setup_crew)
                    else:
                        yield self.door_opened

            # production cycle
            working_time_performed = 0
            production_working_time = code_produced.production_time
            while working_time_performed < production_working_time:
                if self.door_is_open:
                    # adjust workers to production crew
                    production_crew = code_produced.production_crew
                    if production_crew > 0:
                        with self.factory.blue_collars_token.request(priority=priority_on_blue_collars,
                                                                     preempt=False) as token:
                            yield token
                            yield self.factory.blue_collars.get(production_crew)

                    # perform the production taking a fixed time plus a variable time
                    if self.door_is_open:
                        worked_time = min(production_working_time - working_time_performed, self.time_to_door_shift())
                        yield self.factory.env.timeout(worked_time)
                        working_time_performed += worked_time
                        data_to_record = base_data_to_record.copy()
                        data_to_record['worked_time'] = worked_time
                        data_to_record['crew'] = production_crew
                        data_to_record['activity'] = 'production'
                        is_final_code = production_box.product == code_produced.code_name
                        work_is_completed = working_time_performed >= production_working_time
                        if is_final_code and work_is_completed:
                            data_to_record['work_completion'] = 'work_complete'
                        self.factory.observer.record(record_data=data_to_record)

                    # release workers after the job is completed
                    if production_crew > 0:
                        yield self.factory.blue_collars.put(production_crew)

                else:
                    yield self.door_opened

            # wait the lead time
            lead_time = code_produced.lead_time
            if lead_time > 0:
                self.factory.env.process(self.wait_for_lead_time(lead_time, base_data_to_record, production_box))
            else:
                production_box.product_ready.succeed()

    def wait_for_lead_time(self, lead_time, base_data_to_record, production_box):
        yield self.factory.env.timeout(lead_time)
        data_to_record = base_data_to_record.copy()
        data_to_record['lead_time'] = lead_time
        data_to_record['activity'] = 'external_lead_time'
        self.factory.observer.record(record_data=data_to_record)
        production_box.product_ready.succeed()


class ProductCode:
    def __init__(self, factory: SimFactory, code_name, description, classification):
        self.code_name = code_name
        self.code_description = description
        self.code_classification = classification
        self.factory = factory

        # data from the BOM, it will be set with the connect_components method, after each code is instantiated
        self.components = []

        # data from the BOL
        self.bol = self.factory.bol.loc[self.code_name]
        self.work_cell_used_name = self.bol.ix['work_cell_used']
        self.setup_time = self.bol.ix['setup_time']
        self.setup_crew = self.bol.ix['setup_crew']
        self.production_time = self.bol.ix['production_time']
        self.production_crew = self.bol.ix['production_crew']
        self.lead_time = self.bol.ix['lead_time_days'] * 24

        # setup work cell and queue for production
        self.work_cell = self.factory.work_cells[self.work_cell_used_name]
        self.input_wip_location = self.work_cell.input_wip_location

        # setup of warehouse storing ready items
        self.warehouse = []
        self.warehouse_access_token = simpy.Resource(factory.env)

    def connect_components(self):
        if self.code_name in self.factory.bom.index:
            sub_bom = self.factory.bom.loc[self.code_name]
            if isinstance(sub_bom, pd.Series):
                sub_bom = pd.DataFrame(sub_bom).T
            for index, row in sub_bom.iterrows():
                self.components.append({'component': self.factory.codes[row['code_used']],
                                        'quantity': row['quantity']})

    def set_warehouse(self):
        if self.code_name in self.factory.initial_warehouse.index:
            sub_warehouse = self.factory.initial_warehouse.loc[self.code_name]
            if isinstance(sub_warehouse, pd.Series):
                sub_warehouse = pd.DataFrame(sub_warehouse).T
            for index, row in sub_warehouse.iterrows():
                for i in range(row['quantity']):
                    self.warehouse.append(self.code_name)


time_start = timeit.default_timer()
sim_factory = SimFactory()
sim_factory.start(step=1)
sim_factory.observer.write_output()
time_end = timeit.default_timer()
print('elapsed time:', time_end-time_start)