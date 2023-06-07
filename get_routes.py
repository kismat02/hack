import numpy as np
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp


def create_data_for_solver(distance_matrix: np.ndarray, num_vehicles: int = 1, depot: int = 0):
    """Return the data for the problem solver."""
    return {
        "distance_matrix": distance_matrix,
        "num_vehicles": num_vehicles,
        "depot": depot,
    }


def get_routes(solution, routing, manager, data) -> list[list[int]]:
    """Get vehicles routes from a solution and store them in an array."""
    routes = []  # List to store routes for each vehicle
    for vehicle_id in range(data['num_vehicles']):
        route = []
        index = routing.Start(vehicle_id)
        while not routing.IsEnd(index):
            node_index = manager.IndexToNode(index)
            route.append(node_index)
            index = solution.Value(routing.NextVar(index))
        # We store point zero only for 1 vehicle because other vehicles starts from another points
        routes.append(route) if vehicle_id == 0 else routes.append(route[1:])
    return routes


def print_solution(data, manager, routing, solution):
    """Prints solution on console."""
    print(f'Objective: {solution.ObjectiveValue()}')
    max_route_distance = 0
    for vehicle_id in range(data['num_vehicles']):
        index = routing.Start(vehicle_id)
        plan_output = 'Route for vehicle {}:\n'.format(vehicle_id)
        route_distance = 0
        while not routing.IsEnd(index):
            plan_output += ' {} -> '.format(manager.IndexToNode(index))
            previous_index = index
            index = solution.Value(routing.NextVar(index))
            route_distance += routing.GetArcCostForVehicle(previous_index, index, vehicle_id)
        plan_output += '{}\n'.format(manager.IndexToNode(index))
        plan_output += 'Distance of the route: {}m\n'.format(route_distance)
        print(plan_output)
        max_route_distance = max(route_distance, max_route_distance)
    print('Maximum of the route distances: {}m'.format(max_route_distance))


def return_optimal_route(
        distance_matrix: np.ndarray,
        terminals_to_cash_out: list[int],
        tid_2_idx: dict[int, int],
        idx_2_tid: dict[int, int],
        num_vehicles: int = 1,
    ) -> list[list[int]]:
    """Returns optimal routes."""
    selected_indices = [tid_2_idx[i] for i in terminals_to_cash_out]
    num_terminals = len(selected_indices)
    distance_matrix_selected = distance_matrix[selected_indices][:, selected_indices]

    # To let the solver choose start and end points of the routes instead of depo every time
    distance_matrix_selected = np.insert(distance_matrix_selected, num_terminals, 0, axis=0)
    distance_matrix_selected = np.insert(distance_matrix_selected, num_terminals, 0, axis=1)

    data = create_data_for_solver(distance_matrix_selected, num_vehicles)

    # Create the routing index manager.
    manager = pywrapcp.RoutingIndexManager(
        len(data['distance_matrix']),
        data['num_vehicles'],
        data['depot'],
    )
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index, to_index):
        """Returns the distance between the two nodes."""
        # Convert from routing variable Index to distance matrix NodeIndex.
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return data['distance_matrix'][from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)

    # Define cost of each arc.
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    dimension_name = 'Time'
    routing.AddDimension(
        transit_callback_index,
        slack_max=0,  # no slack
        capacity=12 * 60 - 20,  # vehicle maximum travel time, minus 10 minutes because first point takes 10 minutes
        fix_start_cumul_to_zero=False,  # start cumul to zero
        name=dimension_name,
    )
    time_dimension = routing.GetDimensionOrDie(dimension_name)
    time_dimension.SetGlobalSpanCostCoefficient(5)

    # Setting first solution heuristic.
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.AUTOMATIC
    search_parameters.time_limit.seconds = 60

    solution = routing.SolveWithParameters(search_parameters)
    if solution:
        # print_solution(data, manager, routing, solution)
        routes = get_routes(solution, routing, manager, data)

        # Last terminal in every route is pseudo depo created on lines 65-66
        routes_tids = [
            [idx_2_tid[selected_indices[i]] for i in route if i < num_terminals]
            for route in routes
        ]
        return routes_tids


def find_optimal_routes_with_iterating_num_vehicles(
        distance_matrix: np.ndarray,
        terminals_to_cash_out: list[int],
        tid_2_idx: dict[int, int],
        idx_2_tid: dict[int, int],
        min_num_vehicles: int = 1,
        max_num_vehicles: int = 5,
    ) -> tuple[list[list[int]], int]:
    """Find an optimal number of vehicles to solve the problem and returns optimal routes with num_vehicles."""
    for num_vehicles in range(min_num_vehicles, max_num_vehicles + 1):
        routes = return_optimal_route(distance_matrix, terminals_to_cash_out, tid_2_idx, idx_2_tid, num_vehicles)
        if routes:
            return routes, num_vehicles
    return None, None
