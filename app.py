from datetime import datetime
from contextlib import asynccontextmanager
from io import StringIO
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from find_terminals_to_cash_out import PoiStats, BEST_CASH_WEIGHT, BEST_NUM_OF_TERMINALS_TO_CASH_OUT
from get_routes import return_optimal_route
from prepare_data import create_distance_matrix, get_mappings, prepare_data
from schedule_report import create_report_for_schedules, get_schedules_of_vehicles, postprocess_schedules


OPTIMAL_NUM_OF_VEHICLES = 8
app_data = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    incomes, times_from_terminal_to_terminal = prepare_data()

    # Just to immitate how it should work: initial terminals balance from yesterday and income today
    terminals_account_balance = {
        terminal: balance
        for _, (terminal, balance) in incomes.query("timestamp == '2022-08-31'")[["TID", "cash"]].iterrows()
    }
    terminals_income = {
        terminal: balance
        for _, (terminal, balance) in incomes.query("timestamp == '2022-09-01'")[["TID", "cash"]].iterrows()
    }
    terminal_id_to_idx, idx_to_terminal_id = get_mappings()
    times_from_terminal_to_terminal["Destination_tid_idx"] = (
        times_from_terminal_to_terminal["Destination_tid"].map(terminal_id_to_idx)
    )

    distance_matrix = create_distance_matrix()

    # Load the data into app_data
    app_data["terminals_account_balance"] = terminals_account_balance
    app_data["terminals_income"] = terminals_income
    app_data["distance_matrix"] = distance_matrix
    app_data["terminal_id_to_idx"] = terminal_id_to_idx
    app_data["idx_to_terminal_id"] = idx_to_terminal_id

    app_data["stat_obj"] = PoiStats(
        terminals_account_balance,
        BEST_NUM_OF_TERMINALS_TO_CASH_OUT,
        start_date='2022-08-31 00:00:00',  # some random date
        weights=(BEST_CASH_WEIGHT, 1 - BEST_CASH_WEIGHT)
    )
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/find_optimal_routes", response_class=StreamingResponse)
async def find_optimal_routes(): # terminals_income: dict[int, float]
    app_data["stat_obj"].update_day(app_data["terminals_income"])
    termials_to_cash_out = app_data["stat_obj"]._daily_list

    routes = return_optimal_route(
        distance_matrix=app_data["distance_matrix"],
        terminals_to_cash_out=termials_to_cash_out,
        tid_2_idx=app_data["terminal_id_to_idx"],
        idx_2_tid=app_data["idx_to_terminal_id"],
        num_vehicles=OPTIMAL_NUM_OF_VEHICLES,
    )

    today = str(datetime.now().replace(microsecond=0, second=0, minute=0, hour=0))
    result = {today: {"route": routes, "num_vehicles": OPTIMAL_NUM_OF_VEHICLES}}

    schedules = get_schedules_of_vehicles(result)
    report = create_report_for_schedules(schedules)
    final_report = postprocess_schedules(report).drop("день", axis=1)
    final_report[["дата-время прибытия", "дата-время отъезда"]] = (
        final_report[["дата-время прибытия", "дата-время отъезда"]].astype(str)
    )

    stream = StringIO()
    final_report.to_csv(stream, index=False)
    response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=export.csv"
    return response
