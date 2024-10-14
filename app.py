from pathlib import Path

import altair as alt
import anywidget
import pandas as pd
from shiny import reactive
from shiny.express import input, render, ui
from shiny.types import FileInfo
from shiny.ui import page_navbar
from shinyswatch import theme
from shinywidgets import render_altair, render_widget

from icons import gear_fill
from plots import (
    chart_total_bar,
    chart_total_line,
    prep_chart_data,
    title_case,
    var_to_none,
)


def add_hour_of_day_and_month(df: pd.DataFrame) -> pd.DataFrame:
    "Assume all rows have a valid time value from 1-8760"
    # Add 'hour_of_day': hours go from 0 to 23, so we use (time-1) % 24
    df["hour_of_day"] = ((df["time"] - 1) % 24).astype(int)

    # Calculate the day of the year (1-365)
    day_of_year = (df["time"] - 1) // 24 + 1

    # Define month boundaries (non-leap year)
    month_boundaries = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334, 365]

    # Map 'day_of_year' to 'month' (1-12)
    df["month"] = day_of_year.apply(
        lambda day: next(
            month
            for month, boundary in enumerate(month_boundaries[1:], start=1)
            if day <= boundary
        )
    )

    return df


def add_cap_type(df: pd.DataFrame) -> pd.DataFrame:
    df["capacity_type"] = "Total"
    df.loc[df["variable"].str.contains("new"), "capacity_type"] = "New"
    df.loc[df["variable"].str.contains("ret"), "capacity_type"] = "Retired"
    return df


def read_file(fn) -> pd.DataFrame:
    if Path(fn).suffix in [".parquet", ".pq"]:
        return pd.read_parquet(fn).dropna(how="all")
    else:
        return pd.read_csv(fn).dropna(how="all")


@reactive.calc
def parsed_file():
    cat_cols = ["model", "scenario", "region", "variable", "type"]
    file: list[FileInfo] | None = input.results_files()

    if file is None or not file:
        return pd.DataFrame()
    df = pd.concat([read_file(f["datapath"]) for f in file])
    for col in cat_cols:
        df[col] = df[col].astype("category")
    df["time"] = df["time"].astype("float32")
    df["year"] = df["year"].astype(str)
    return df


ui.page_opts(title="Explore model results", fillable=True, theme=theme.yeti)
with ui.sidebar(id="user_data_sidebar_left"):
    ui.p("This space could contain descriptions of how to use the dashboard.")

    ui.p(
        "Select your data files. Within each page of the dashboard you can filter the inputs."
    )

    ui.p("A top-level set of filters could also be included in this sidebar.")

    ui.p(
        "All of this could also go on a separate page rather than being a collapsible sidebar."
    )
    with ui.tooltip(id="upload_tooltip"):
        ui.input_file(
            "results_files",
            "Choose Data File(s)",
            accept=[".csv", ".gz", ".parquet"],
            multiple=True,
        )
        "Select one or more data files. All files must be selected at the same time."


@reactive.calc
def filter_data():
    if parsed_file().empty:
        return parsed_file()
    elif input.data_type() == "Capacity":
        return parsed_file().query("time.isna()")
    else:
        return parsed_file().query("time.notna()")


@reactive.calc
def tx_cap_data():
    if parsed_file().empty:
        return parsed_file()
    else:
        return (
            parsed_file()
            .query("time.isna() and type == 'PowerLine'")
            .pipe(add_cap_type)
        )


@reactive.calc
def tx_time_data():
    if parsed_file().empty:
        return parsed_file()
    else:
        return (
            parsed_file()
            .query("time.notna() and type == 'PowerLine'")
            .pipe(add_hour_of_day_and_month)
        )


@reactive.calc
def resource_cap_data():
    if parsed_file().empty:
        return parsed_file()
    else:
        return (
            parsed_file()
            .query("time.isna() and type != 'PowerLine'")
            .pipe(add_cap_type)
        )


@reactive.calc
def resource_time_data():
    if parsed_file().empty:
        return parsed_file()
    else:
        return (
            parsed_file()
            .query(
                "time.notna() and type != 'PowerLine' and unit == 'MWh' and variable.str.contains('flow')"
            )
            .pipe(add_hour_of_day_and_month)
        )


@reactive.calc
def storage_time_data():
    if parsed_file().empty:
        return parsed_file()
    else:
        return (
            parsed_file()
            .query(
                "time.notna() and type != 'PowerLine' and variable.str.contains('storage_level')"
            )
            .pipe(add_hour_of_day_and_month)
        )


@reactive.calc
def co2_time_data():
    if parsed_file().empty:
        return parsed_file()
    else:
        return parsed_file().query(
            "time.notna() and type != 'PowerLine' and unit == 't'"
        )


@reactive.calc
def r_cap_values():
    values = {}
    for col in ["year", "scenario", "region", "type", "capacity_type"]:
        if parsed_file().empty:
            options = ["all"]
        else:
            options = list(resource_cap_data()[col].unique())
        values[col] = options
    return values


@reactive.calc
def r_time_values():
    values = {}
    for col in ["year", "scenario", "region", "type"]:
        if parsed_file().empty:
            options = ["all"]
        else:
            options = list(resource_time_data()[col].unique())
        values[col] = options
    return values


with ui.nav_panel("Resource capacity"):
    with ui.layout_sidebar():
        with ui.sidebar():
            "Filter data"

            @render.ui
            def r_calc_filters():
                if not parsed_file().empty:
                    filters = []
                    for k, v in r_cap_values().items():
                        filters.append(
                            ui.input_selectize(
                                f"r_cap_{k}",
                                k,
                                choices=v,
                                selected=v,
                                multiple=True,
                            )
                        )
                    return filters

            @reactive.calc
            def filtered_r_cap_data():
                df = resource_cap_data()
                df = df.loc[
                    (df["year"].isin(input.r_cap_year()))
                    & (df["scenario"].isin(input.r_cap_scenario()))
                    & (df["region"].isin(input.r_cap_region()))
                    & (df["capacity_type"].isin(input.r_cap_capacity_type()))
                    & (df["type"].isin(input.r_cap_type())),
                    :,
                ]
                return df

        with ui.navset_card_pill(id="r_cap"):
            with ui.nav_panel("Line plot"):
                with ui.popover(placement="right", id="cap_line_vars"):
                    ui.input_action_button(
                        "btn", "Select chart variables", width="200px", class_="mt-3"
                    )

                    # "Change plot variables"
                    ui.input_selectize(
                        "r_cap_x_var",
                        "X variable",
                        choices=[
                            "year",
                            "model",
                            "scenario",
                            "region",
                            "variable",
                            "type",
                            "capacity_type",
                            "None",
                        ],
                        selected="year",
                        width="150px",
                    )

                    ui.input_selectize(
                        "r_cap_col_var",
                        "Column",
                        choices=[
                            "year",
                            "model",
                            "scenario",
                            "region",
                            "variable",
                            "type",
                            "capacity_type",
                            "None",
                        ],
                        selected="scenario",
                        width="150px",
                    )
                    ui.input_selectize(
                        "r_cap_row_var",
                        "Row",
                        choices=[
                            "year",
                            "model",
                            "scenario",
                            "region",
                            "variable",
                            "type",
                            "capacity_type",
                            "None",
                        ],
                        selected="region",
                        width="150px",
                    )
                    ui.input_selectize(
                        "r_cap_color",
                        "Color",
                        choices=[
                            "year",
                            "model",
                            "scenario",
                            "region",
                            "variable",
                            "type",
                            "capacity_type",
                            "None",
                        ],
                        selected="type",
                        width="150px",
                    )
                    ui.input_selectize(
                        "r_cap_dash",
                        "Line dash",
                        choices=[
                            "year",
                            "model",
                            "scenario",
                            "region",
                            "variable",
                            "type",
                            "capacity_type",
                            "None",
                        ],
                        selected="capacity_type",
                        width="150px",
                    )

                    @render.download(
                        label="Download plot data",
                        filename="resource_capacity_line_data.csv",
                    )
                    def download_r_cap_line_data():
                        yield prep_chart_data(
                            filtered_r_cap_data(),
                            x_var=input.r_cap_x_var(),  # input.cap_line_x_var(),
                            col_var=input.r_cap_col_var(),
                            row_var=input.r_cap_row_var(),
                            color=input.r_cap_color(),
                            dash=input.r_cap_dash(),
                            cap_types=input.r_cap_type(),
                        ).to_csv()

                @render_altair
                def alt_cap_lines():
                    if parsed_file().empty:
                        return None
                    data = prep_chart_data(
                        filtered_r_cap_data(),
                        x_var=input.r_cap_x_var(),
                        col_var=input.r_cap_col_var(),
                        row_var=input.r_cap_row_var(),
                        color=input.r_cap_color(),
                        dash=input.r_cap_dash(),
                        # cap_types=input.r_cap_type(),
                    )
                    chart = chart_total_line(
                        data,
                        x_var=input.r_cap_x_var(),
                        col_var=input.r_cap_col_var(),
                        row_var=input.r_cap_row_var(),
                        color=input.r_cap_color(),
                        dash=input.r_cap_dash(),
                        height=200,  # * (input.cap_line_height() / 100),
                        width=200,  # * (input.cap_line_width() / 100),
                        legend_selection_fields=[
                            input.r_cap_color(),
                            input.r_cap_dash(),
                        ],
                    )
                    return chart

            with ui.nav_panel("Bar plot"):
                "Select chart variables"
                with ui.popover(placement="right", id="cap_bar_vars"):
                    ui.p(
                        gear_fill,
                        style="position:absolute; top: 73px; left: 185px;",
                    )

                    # "Change plot variables"
                    ui.input_selectize(
                        "r_cap_bar_x_var",
                        "X variable",
                        choices=[
                            "year",
                            "model",
                            "scenario",
                            "region",
                            "variable",
                            "type",
                            "capacity_type",
                            "None",
                        ],
                        selected="scenario",
                        width="150px",
                    )

                    ui.input_selectize(
                        "r_cap_bar_col_var",
                        "Column",
                        choices=[
                            "year",
                            "model",
                            "scenario",
                            "region",
                            "variable",
                            "type",
                            "capacity_type",
                            "None",
                        ],
                        selected="year",
                        width="150px",
                    )
                    ui.input_selectize(
                        "r_cap_bar_row_var",
                        "Row",
                        choices=[
                            "year",
                            "model",
                            "scenario",
                            "region",
                            "variable",
                            "type",
                            "capacity_type",
                            "None",
                        ],
                        selected="region",
                        width="150px",
                    )
                    ui.input_selectize(
                        "r_cap_bar_color",
                        "Color",
                        choices=[
                            "year",
                            "model",
                            "scenario",
                            "region",
                            "variable",
                            "type",
                            "capacity_type",
                            "None",
                        ],
                        selected="type",
                        width="150px",
                    )

                    @render.download(
                        label="Download plot data",
                        filename="resource_capacity_bar_data.csv",
                    )
                    def download_r_cap_bar_data():
                        yield prep_chart_data(
                            filtered_r_cap_data(),
                            x_var=input.r_cap_bar_x_var(),  # input.cap_line_x_var(),
                            col_var=input.r_cap_bar_col_var(),
                            row_var=input.r_cap_bar_row_var(),
                            color=input.r_cap_bar_color(),
                            cap_types=input.r_cap_type(),
                            # opacity=input.r_cap_bar_opacity(),
                        ).to_csv()

                @render_altair
                def alt_cap_bars():
                    if parsed_file().empty:
                        return None
                    data = prep_chart_data(
                        filtered_r_cap_data(),
                        x_var=input.r_cap_bar_x_var(),
                        col_var=input.r_cap_bar_col_var(),
                        row_var=input.r_cap_bar_row_var(),
                        color=input.r_cap_bar_color(),
                        # opacity=input.r_cap_bar_opacity(),
                    )
                    chart = chart_total_bar(
                        data,
                        x_var=input.r_cap_bar_x_var(),
                        col_var=input.r_cap_bar_col_var(),
                        row_var=input.r_cap_bar_row_var(),
                        color=input.r_cap_bar_color(),
                        # opacity=input.r_cap_bar_opacity(),
                        height=200,  # * (input.cap_line_height() / 100),
                        width=200,  # * (input.cap_line_width() / 100),
                        legend_selection_fields=[
                            input.r_cap_bar_color(),
                        ],
                    )
                    return chart

            with ui.nav_panel("Table"):

                @render.data_frame
                def show_r_cap_df():
                    if parsed_file().empty:
                        return None
                    # data = prep_chart_data(
                    #     filtered_r_cap_data(),
                    #     x_var=input.r_cap_x_var(),
                    #     col_var=input.r_cap_col_var(),
                    #     row_var=input.r_cap_row_var(),
                    #     color=input.r_cap_color(),
                    #     dash=input.r_cap_dash(),
                    #     # cap_types=input.r_cap_type(),
                    # )
                    return render.DataTable(filtered_r_cap_data(), filters=True)


with ui.nav_panel("Resource time series"):
    with ui.layout_sidebar():
        with ui.sidebar():
            ui.input_selectize(
                "r_time_col_var",
                "Column",
                choices=[
                    "year",
                    "model",
                    "scenario",
                    "region",
                    "variable",
                    "type",
                    "capacity_type",
                    "None",
                ],
                selected="scenario",
                width="125px",
            )
            ui.input_selectize(
                "r_time_row_var",
                "Row",
                choices=[
                    "year",
                    "model",
                    "scenario",
                    "region",
                    "variable",
                    "type",
                    "capacity_type",
                    "None",
                ],
                selected="region",
                width="150px",
            )
            ui.input_selectize(
                "r_time_color",
                "Color",
                choices=[
                    "year",
                    "model",
                    "scenario",
                    "region",
                    "variable",
                    "type",
                    "capacity_type",
                    "None",
                ],
                selected="type",
                width="125px",
            )
            ui.input_selectize(
                "r_time_dash",
                "Line dash",
                choices=[
                    "year",
                    "model",
                    "scenario",
                    "region",
                    "variable",
                    "type",
                    "capacity_type",
                    "None",
                ],
                selected="year",
                width="125px",
            )
            ui.input_selectize(
                "r_time_avg",
                "Average by time",
                choices=["hour_of_day", "month"],
                selected="hour_of_day",
                width="125px",
            )

            @render.ui
            def r_time_filters():
                if not parsed_file().empty:
                    filters = []
                    for k, v in r_time_values().items():
                        filters.append(
                            ui.input_selectize(
                                f"r_time_{k}",
                                k,
                                choices=v,
                                selected=v,
                                multiple=True,
                            )
                        )
                    return filters

        with ui.navset_card_pill(id="r_time"):
            with ui.nav_panel("Plot"):

                @reactive.calc
                def filtered_r_time_data():
                    df = resource_time_data()
                    df = df.loc[
                        (df["year"].isin(input.r_time_year()))
                        & (df["scenario"].isin(input.r_time_scenario()))
                        & (df["region"].isin(input.r_time_region()))
                        & (df["type"].isin(input.r_time_type())),
                        :,
                    ]
                    return df

                @render.download(
                    label="Download plot data", filename="resource_time_data.csv"
                )
                def download_r_time_data():
                    yield prep_chart_data(
                        filtered_r_time_data(),
                        x_var=None,  # input.cap_line_x_var(),
                        col_var=input.r_time_col_var(),
                        row_var=input.r_time_row_var(),
                        color=input.r_time_color(),
                        dash=input.r_time_dash(),
                        cap_types=input.r_time_type(),
                        avg_by=input.r_time_avg(),
                    ).to_csv()

                @render_altair
                def alt_r_time_lines():
                    if parsed_file().empty:
                        return None
                    data = prep_chart_data(
                        filtered_r_time_data(),
                        x_var=None,
                        col_var=input.r_time_col_var(),
                        row_var=input.r_time_row_var(),
                        color=input.r_time_color(),
                        dash=input.r_time_dash(),
                        avg_by=input.r_time_avg(),
                    )
                    chart = chart_total_line(
                        data,
                        x_var=input.r_time_avg(),
                        col_var=input.r_time_col_var(),
                        row_var=input.r_time_row_var(),
                        color=input.r_time_color(),
                        dash=input.r_time_dash(),
                        height=200,  # * (input.cap_line_height() / 100),
                        width=200,  # * (input.cap_line_width() / 100),
                    )
                    return chart

            with ui.nav_panel("Table"):

                @render.data_frame
                def show_r_time_df():
                    data = prep_chart_data(
                        filtered_r_time_data(),
                        x_var=None,
                        col_var=input.r_time_col_var(),
                        row_var=input.r_time_row_var(),
                        color=input.r_time_color(),
                        dash=input.r_time_dash(),
                        avg_by=input.r_time_avg(),
                    )
                    return render.DataTable(data, filters=True)
