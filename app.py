from functools import partial
from pathlib import Path

import altair as alt
import anywidget
import pandas as pd
from pivottablejs import pivot_ui
from shiny import reactive
from shiny.express import input, render, ui
from shiny.types import FileInfo
from shiny.ui import page_navbar
from shinywidgets import render_altair, render_widget


def var_to_none(var):
    if var == "None":
        return None
    return var


def title_case(s: str) -> str:
    if isinstance(s, str):
        return s.replace("_", " ").title()


def config_chart_row_col(
    chart: alt.Chart,
    row_var: str,
    col_var: str,
    strokeDash: str = None,
    shape: str = None,
) -> alt.Chart:
    if strokeDash is not None:
        chart = chart.encode(strokeDash=strokeDash)
    if shape is not None:
        chart = chart.encode(shape=shape)
    if col_var is not None and row_var is not None:
        chart = chart.facet(
            column=alt.Column(col_var)
            # .sort(order_dict().get(col_var))
            # .title(title_case(col_var))
            .header(titleFontSize=20, labelFontSize=15),
            row=alt.Row(row_var)
            # .sort(order_dict().get(row_var))
            # .title(title_case(row_var))
            .header(titleFontSize=20, labelFontSize=15),
        )
    elif col_var is not None:
        chart = chart.facet(
            column=alt.Column(col_var)
            # .sort(order_dict().get(col_var))
            # .title(title_case(col_var))
            .header(titleFontSize=20, labelFontSize=15)
        )
    elif row_var is not None:
        chart = chart.facet(
            row=alt.Row(row_var)
            # .sort(order_dict().get(row_var))
            # .title(title_case(row_var))
            .header(titleFontSize=20, labelFontSize=15)
        )
    chart = chart.configure_axis(labelFontSize=15, titleFontSize=15).configure_legend(
        titleFontSize=20, labelFontSize=16
    )
    if "case" in [row_var, col_var]:
        chart = (
            chart.configure(lineBreak="\n")
            .configure_axis(labelFontSize=15, titleFontSize=15)
            .configure_legend(titleFontSize=20, labelFontSize=16)
        )
    return chart


def fill_idx(df: pd.DataFrame, cols) -> pd.DataFrame:
    midx = pd.MultiIndex.from_product([df[c].unique() for c in cols], names=cols)
    df = df.set_index(cols)
    df = df.reindex(midx, fill_value=0)
    return df.reset_index()


def prep_chart_data(
    df: pd.DataFrame,
    x_var="planning_year",
    col_var="tech_type",
    row_var="case",
    color="model",
    dash="None",
    shape="None",
    cap_types=None,
    avg_by=None,
):
    x_var = var_to_none(x_var)
    col_var = var_to_none(col_var)
    row_var = var_to_none(row_var)
    shape = var_to_none(shape)
    dash = var_to_none(dash)
    color = var_to_none(color)

    if "capacity_type" in df.columns and cap_types is not None:
        df = df.loc[df["capacity_type"].isin(cap_types), :]

    group_by = [
        var
        for var in [x_var, col_var, row_var, color, shape, dash]
        if var is not None and var in df.columns
    ]

    if avg_by is None:
        data = df.groupby(list(set(group_by)), as_index=False, observed=True)[
            "value"
        ].sum()
    else:
        group_by.append(avg_by)
        data = df.groupby(list(set(group_by)), as_index=False, observed=True)[
            "value"
        ].mean()
    data = fill_idx(data, list(set(group_by)))
    return data


def chart_total_line(
    data: pd.DataFrame,
    x_var="planning_year",
    col_var="tech_type",
    row_var="case",
    color="model",
    shape=None,
    dash=None,
    order=None,
    scale="linear",
    width=alt.Step(40),
    height=200,
) -> alt.Chart:
    alt.data_transformers.disable_max_rows()
    alt.renderers.enable("svg")
    x_var = var_to_none(x_var)
    col_var = var_to_none(col_var)
    row_var = var_to_none(row_var)
    shape = var_to_none(shape)
    dash = var_to_none(dash)
    color = var_to_none(color)

    # group_by = []
    _tooltips = [alt.Tooltip("value")]  # , title="Capacity (GW)", format=",.0f"),

    for var in [x_var, col_var, row_var, color, shape, dash]:
        if var is not None:
            _tooltips.append(alt.Tooltip(var))

    lines = (
        alt.Chart(data)
        .mark_line(point=dash is None)
        .encode(
            x=alt.X(x_var),
            y=alt.Y("sum(value)"),
            color=color,
            tooltip=_tooltips,
        )
        .properties(width=width, height=height)
        # .interactive()
    )
    if dash is not None:
        lines = lines.encode(strokeDash=dash)
        points = (
            alt.Chart(data)
            .mark_point(filled=True)
            .encode(
                x=alt.X(x_var),
                y=alt.Y("sum(value)"),
                color=alt.Color(color),
                tooltip=_tooltips,
            )
            .properties(width=width, height=height)
            # .interactive()
        )
        chart = lines + points  # .resolve_scale(strokeDash="independent")
    else:
        chart = lines

    chart = config_chart_row_col(chart, row_var, col_var)
    return chart


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
    return df


ui.page_opts(
    title="Example app",
    fillable=True,
)
with ui.sidebar(id="user_data_sidebar_left"):
    ui.input_file(
        "results_files",
        "Choose Data File(s)",
        accept=[".csv", ".gz", ".parquet"],
        multiple=True,
    )


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


with ui.nav_panel("Plot resource cap data"):
    with ui.layout_sidebar():
        with ui.sidebar():
            ui.input_selectize(
                "r_cap_type",
                "Capacity type",
                multiple=True,
                choices=["Total", "New", "Retired"],
                selected=["Total", "New", "Retired"],
                width="125px",
            )
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
                width="125px",
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
                width="125px",
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
                width="125px",
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
                selected="None",
                width="125px",
            )

        # with ui.accordion_panel("Outputs"):
        with ui.navset_card_pill(id="r_cap"):
            with ui.nav_panel("Plot"):

                @render.download(
                    label="Download plot data", filename="resource_capacity_data.csv"
                )
                def download_data():
                    yield prep_chart_data(
                        resource_cap_data(),
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
                        resource_cap_data(),
                        x_var=input.r_cap_x_var(),
                        col_var=input.r_cap_col_var(),
                        row_var=input.r_cap_row_var(),
                        color=input.r_cap_color(),
                        dash=input.r_cap_dash(),
                        cap_types=input.r_cap_type(),
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
                    )
                    return chart

            with ui.nav_panel("Table"):

                @render.data_frame
                def show_r_cap_df():
                    data = prep_chart_data(
                        resource_cap_data(),
                        x_var=input.r_cap_x_var(),
                        col_var=input.r_cap_col_var(),
                        row_var=input.r_cap_row_var(),
                        color=input.r_cap_color(),
                        dash=input.r_cap_dash(),
                        cap_types=input.r_cap_type(),
                    )
                    return render.DataTable(data, filters=True)


with ui.nav_panel("Plot resource time series data"):
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

        with ui.navset_card_pill(id="r_time"):
            with ui.nav_panel("Plot"):

                @render.download(
                    label="Download plot data", filename="resource_time_data.csv"
                )
                def download_r_time_data():
                    yield prep_chart_data(
                        resource_time_data(),
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
                        resource_time_data(),
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
                        resource_time_data(),
                        x_var=None,
                        col_var=input.r_time_col_var(),
                        row_var=input.r_time_row_var(),
                        color=input.r_time_color(),
                        dash=input.r_time_dash(),
                        avg_by=input.r_time_avg(),
                    )
                    return render.DataTable(data, filters=True)
