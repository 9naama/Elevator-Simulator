"""CSC148 Assignment 1 - Simulation

=== CSC148 Fall 2023 ===
Department of Computer Science,
University of Toronto

=== Module description ===
This contains the main Simulation class that is actually responsible for
creating and running the simulation. You'll also find the function run_example_simulation
here at the bottom of the file, which you can use as a starting point to run
your simulation on a small configuration.

Note that we have provided a fairly comprehensive list of attributes for
Simulation already. You may add your own *private* attributes, but should not
modify/remove any of the existing attributes.
"""
# You MAY import more things from these modules (e.g., additional types from
# typing), but you may not import from any other modules.
from typing import Any
from python_ta.contracts import check_contracts

import a1_algorithms
from a1_entities import Person, Elevator
from a1_visualizer import Direction, Visualizer


@check_contracts
class Simulation:
    """The main simulation class.

    Instance Attributes:
    - arrival_generator: the algorithm used to generate new arrivals.
    - elevators: a list of the elevators in the simulation
    - moving_algorithm: the algorithm used to decide how to move elevators
    - num_floors: the number of floors
    - visualizer: the Pygame visualizer used to visualize this simulation
    - waiting: a dictionary of people waiting for an elevator, where:
        - The keys are floor numbers from 1 to num_floors, inclusive
        - Each corresponding value is the list of people waiting at that floor
          (could be an empty list)

    Representation Invariants:
    - len(self.elevators) >= 1
    - self.num_floors >= 2
    - list(self.waiting.keys()) == list(range(1, self.num_floors + 1))
    """
    arrival_generator: a1_algorithms.ArrivalGenerator
    elevators: list[Elevator]
    moving_algorithm: a1_algorithms.MovingAlgorithm
    num_floors: int
    visualizer: Visualizer
    waiting: dict[int, list[Person]]

    def __init__(self,
                 config: dict[str, Any]) -> None:
        """Initialize a new simulation using the given configuration.

        Preconditions:
        - config is a dictionary in the format found on the assignment handout
        - config['num_floors'] >= 2
        - config['elevator_capacity'] >= 1
        - config['num_elevators'] >= 1

        A partial implementation has been provided to you; you'll need to finish it!
        """

        # Initialize the algorithm attributes (this is done for you)
        self.arrival_generator = config['arrival_generator']
        self.moving_algorithm = config['moving_algorithm']

        self.num_floors = config['num_floors']
        self.elevators = []
        count = 0
        while count < config['num_elevators']:
            self.elevators.append(Elevator(config['elevator_capacity']))
            count += 1

        self.waiting = {}
        for i in list(range(1, self.num_floors + 1)):
            self.waiting[i] = []

        # Initialize the visualizer (this is done for you).
        # Note that this should be executed *after* the other attributes
        # have been initialized, particularly self.elevators and self.num_floors.
        self.visualizer = Visualizer(self.elevators, self.num_floors,
                                     config['visualize'])

    ############################################################################
    # Handle rounds of simulation.
    ############################################################################
    def run(self, num_rounds: int) -> dict[str, int]:

        """Run the simulation for the given number of rounds.

        Return a set of statistics for this simulation run, as specified in the
        assignment handout.

        Preconditions:
        - num_rounds >= 1
        - This method is only called once for each Simulation instance
            (since we have not asked you to "reset" back to the initial simulation state
            for this assignment)
        """
        people = []
        disembarked = []

        for i in range(num_rounds):
            self.visualizer.render_header(i)

            # Stage 1: elevator disembarking
            disembarked.extend(self.handle_disembarking())

            # Stage 2: new arrivals
            people.extend(self.generate_arrivals(i))

            # Stage 3: elevator boarding
            self.handle_boarding()

            # Stage 4: move the elevators
            self.move_elevators()

            # Stage 5: update wait times
            self.update_wait_times()

            # Pause for 1 second
            self.visualizer.wait(1)

        # The following line waits until the user closes the Pygame window
        self.visualizer.wait_for_exit()

        return self._calculate_stats(num_rounds, disembarked, people)

    def handle_disembarking(self) -> list[Person]:
        """Handle people leaving elevators.

        Hints:
        - You shouldn't loop over a list (e.g. elevator.passengers) and mutate it within the
          loop body. This will cause unexpected behaviour due to how Python implements looping!
        - It's fine to reassign elevator.passengers to a new list. If you do so,
          make sure to call elevator.update() so that the new "fullness" of the elevator
          gets visualized properly.
        """
        disembarked = []
        for ele in self.elevators:
            i = 0
            while i < len(ele.passengers):
                if ele.passengers[i].target == ele.current_floor:
                    self.visualizer.show_disembarking(ele.passengers[i], ele)
                    disembarked.append(ele.passengers[i])
                    ele.passengers.pop(i)
                    ele.update()
                else:
                    i += 1
        return disembarked

    def generate_arrivals(self, round_num: int) -> list[Person]:
        """Generate and visualize new arrivals."""
        people = []
        arrivals = self.arrival_generator.generate(round_num)
        if arrivals:
            for key in arrivals:
                self.waiting[key].extend(arrivals[key])
                people.extend(arrivals[key])
            self.visualizer.show_arrivals(self.waiting)
        return people

    def handle_boarding(self) -> None:
        """Handle boarding of people and visualize."""

        for ele in self.elevators:
            i = 0
            while i < len(self.waiting[ele.current_floor]):
                person = self.waiting[ele.current_floor][i]
                if ele.fullness() < 1:
                    floor = ele.current_floor
                    if ele.target_floor == floor \
                            or (ele.target_floor > floor and person.target > floor) \
                            or (ele.target_floor < floor and person.target < floor):
                        ele.passengers.append(person)
                        self.visualizer.show_boarding(person, ele)
                        self.waiting[floor].remove(self.waiting[ele.current_floor][i])
                    else:
                        i += 1
                else:
                    i += (ele.capacity + 1)

    def move_elevators(self) -> None:
        """Update elevator target floors and then move them."""
        directions = []
        self.moving_algorithm.update_target_floors(self.elevators, self.waiting, self.num_floors)
        for elevator in self.elevators:
            if elevator.target_floor > elevator.current_floor:
                elevator.current_floor += 1
                directions.append(Direction.UP)
            elif elevator.target_floor < elevator.current_floor:
                elevator.current_floor -= 1
                directions.append(Direction.DOWN)
            else:
                directions.append(Direction.STAY)
        self.visualizer.show_elevator_moves(self.elevators, directions)

    def update_wait_times(self) -> None:
        """Update the waiting time for every person waiting in this simulation.

        Note that this includes both people waiting for an elevator AND people
        who are passengers on an elevator. It does not include people who have
        reached their target floor.
        """
        for key in self.waiting:
            for person in self.waiting[key]:
                if person.target != key:
                    person.wait_time += 1

        for elevator in self.elevators:
            for person in elevator.passengers:
                person.wait_time += 1

    ############################################################################
    # Statistics calculations
    ############################################################################
    def _calculate_stats(self, num_rounds: int, disembarked: list[Person], people: list[Person])\
            -> dict[str, int]:
        """Report the statistics for the current run of this simulation.

        Preconditions:
        - This method is only called after the simulation rounds have finished

        You MAY change the interface for this method (e.g., by adding new parameters).
        We won't call it directly in our testing.
        """
        total_people = len(people)
        people_completed = len(disembarked)
        total_wait_time = 0
        max_wait_time = -1
        avg_wait_time = -1

        if people_completed:
            for person in disembarked:
                total_wait_time += person.wait_time
                max_wait_time = max(person.wait_time, max_wait_time)

            avg_wait_time = total_wait_time // people_completed

        return {
            'num_rounds': num_rounds,
            'total_people': total_people,
            'people_completed': people_completed,
            'max_time': max_wait_time,
            'avg_time': avg_wait_time
        }


###############################################################################
# Simulation runner
###############################################################################
def run_example_simulation() -> dict[str, int]:
    """Run a sample simulation, and return the simulation statistics.

    This function is provided to help you test your work. You MAY change it
    (e.g., by changing the configuration values) for further testing.
    """
    num_floors = 6
    num_elevators = 2
    elevator_capacity = 2

    config = {
        'num_floors': num_floors,
        'num_elevators': num_elevators,
        'elevator_capacity': elevator_capacity,
        'arrival_generator': a1_algorithms.FileArrivals(num_floors, 'data/sample_arrivals_ten.csv'),
        'moving_algorithm': a1_algorithms.FurthestFloor(),
        'visualize': True
    }

    sim = Simulation(config)
    stats1 = sim.run(15)
    return stats1


if __name__ == '__main__':
    # We haven't provided any doctests for you, but if you add your own the following
    # code will run them!

    import doctest
    doctest.testmod()

    # Uncomment this line to run our sample simulation (and print the
    # statistics generated by the simulation).
    sample_run_stats = run_example_simulation()
    print(sample_run_stats)

    # Uncomment the python_ta lines below and run this module.
    # This is different that just running doctests! To run this file in PyCharm,
    # right-click in the file and select "Run a1_simulation" or "Run File in Python Console".
    #
    # python_ta will check your work and open up your web browser to display
    # its report. For full marks, you must fix all issues reported, so that
    # you see "None!" under both "Code Errors" and "Style and Convention Errors".
    # TIP: To quickly uncomment lines in PyCharm, select the lines below and press
    # "Ctrl + /" or "⌘ + /".
    # import python_ta
    # python_ta.check_all(config={
    #     'extra-imports': ['a1_entities', 'a1_visualizer', 'a1_algorithms'],
    #     'max-nested-blocks': 4,
    #     'max-attributes': 10,
    #     'max-line-length': 100
    # })
