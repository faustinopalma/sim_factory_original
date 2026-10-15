# Technical Note: Using a Forward Simulator to Work Backward in Time

Backward planning starts from a delivery target and determines when the required work must take place. The design idea is to use an ordinary discrete-event simulator for that calculation by reversing the relationship between its clock and the factory calendar.

SimPy continues to process events in increasing simulation time. Each additional simulated hour represents an hour earlier in the factory calendar. Durations remain positive, and the simulator retains its event queue, resource allocation, and waiting mechanisms.

## Two Clocks

Choose a reference time $T$ at the end of the planning horizon. Let $s$ be the elapsed simulation time, measured in hours. The corresponding factory-calendar time is:

$$
t = T - s
$$

At $s=0$, the calendar is at $T$. As $s$ increases, the calendar moves backward. For a reference time of Friday at 18:00:

| Simulation Time $s$ | Factory-Calendar Time $t$ |
| --- | --- |
| 0 hours | Friday, 18:00 |
| 2 hours | Friday, 16:00 |
| 5 hours | Friday, 13:00 |
| 24 hours | Thursday, 18:00 |

A delivery target $D$ is expressed on the same clock as $s_D = T - D$. Using one reference horizon gives all orders and resources a common time coordinate.

## Work Intervals and Resource Constraints

Suppose a three-hour operation occupies a machine from simulation hour 2 to hour 5. On the factory calendar, that reservation covers Friday from 13:00 to 16:00. The interval's endpoints exchange roles, while its duration remains three hours.

More generally, a simulated reservation from $s_a$ to $s_b$ corresponds to the calendar interval:

$$
[T-s_b,\ T-s_a]
$$

This transformation preserves overlap. Two operations that compete for the same machine in simulation also overlap on the factory calendar. A machine with one processing slot therefore remains a finite-capacity machine after the transformation. The same reasoning applies to a shared pool of workers.

The benefit is that the simulator can calculate resource conflicts and waits while exploring earlier calendar slots. Backward planning can then account for competing work and opening hours, rather than merely subtracting operation durations from a deadline.

## Reading the Calendar Backward

Resource availability must use the factory-calendar coordinate. If a machine is closed on a particular date, it must also be unavailable when the reversed clock reaches that date.

The [staffing process](../sim_factory.py#L69) and the work-cell calendar use this calculation:

```python
time = self.end_time - self.env.now
day = math.floor(time / 24)
```

`env.now` is SimPy's increasing clock; `end_time - env.now` selects decreasing calendar-day indices. This is the part of the implementation that expresses the reverse-time idea. The library itself needs no decreasing clock or negative timeout.

## Time Direction and Operation Order

A production plan must satisfy both resource constraints and technological precedence. If assembly requires a component, the component must be ready before assembly starts on the factory calendar.

For example, suppose a component takes one hour and assembly takes two hours, with delivery at Friday 18:00 and all required resources available. A backward allocation first reserves assembly from 16:00 to 18:00, then component production from 15:00 to 16:00. In simulation coordinates, assembly occupies hours 0 to 2 and component production hours 2 to 3.

Thus the order in which operations are allocated also reverses. Expanding a bill of materials identifies the required work; a backward scheduling process must connect that work in the direction implied by the reversed calendar. The clock transformation preserves resource overlap, but precedence must be represented explicitly.

## Interpreting This Implementation

The source combines a reverse calendar lookup with two other conventions:

- [Component synchronization](../sim_factory.py#L164) waits for component events before placing their parent in its processing queue. That expresses component-before-parent precedence in increasing SimPy time.
- The [observer](../sim_factory.py#L122) exports timestamps as `start_date + Hour(env.now)`, which increases with SimPy time.

Consequently, the reverse calendar calculation establishes the design idea, while interpreting a complete output as a backward production schedule also requires consistent order dates, operation precedence, and exported timestamps. For a simulated work interval, a backward report would use $T-s_b$ as its calendar start and $T-s_a$ as its calendar finish.

The [worked examples](worked-examples.md) use the existing observer's forward timestamps and compile their operating calendar accordingly. Their completion dates and lateness measures follow that convention; they demonstrate the current engine's resource-constrained execution rather than validate a fully reversed schedule.

The original insight is the separation of simulation time from calendar time: an increasing event clock can represent a search backward through the production calendar. A complete backward planner applies that relationship consistently to dates, resources, and dependencies.