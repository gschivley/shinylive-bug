from functools import partial

import altair as alt
import anywidget
import pandas as pd
from shiny import reactive
from shiny.express import input, render, ui
from shiny.types import FileInfo
from shiny.ui import page_navbar
from shinywidgets import render_altair


def var_to_none(var):
    if var == "None":
        return None
    return var


def parsed_file():
    file: list[FileInfo] | None = input.file1()
    if file is None:
        return pd.DataFrame()
    return pd.read_csv(file[0]["datapath"])  # pyright: ignore[reportUnknownMemberType]


ui.page_opts(
    title="Example app",
    # page_fn=partial(page_navbar, id="page"),
)
with ui.sidebar(id="user_data_sidebar_left"):

    ui.input_selectize(
        "x_var",
        "X Variable",
        choices=["A", "B", "C", "D", "E"],
        selected="A",
        width="150px",
    )
    ui.input_selectize(
        "y_var",
        "Y Variable",
        choices=["A", "B", "C", "D", "E"],
        selected="D",
        width="150px",
    )
    ui.input_selectize(
        "col_var",
        "Column",
        choices=["A", "B", "C", "D", "E", "None"],
        selected="",
        width="150px",
    )
    ui.input_selectize(
        "row_var",
        "Row",
        choices=["A", "B", "C", "D", "E", "None"],
        selected="B",
        width="150px",
    )
    ui.input_selectize(
        "color",
        "Color",
        choices=["A", "B", "C", "D", "E"],
        selected="C",
        width="150px",
    )

with ui.nav_panel("Plot user data"):
    ui.input_file("file1", "Choose CSV File", accept=[".csv"], multiple=False)

    @render_altair
    def user_bars():
        if parsed_file().empty:
            return None
        col_var = var_to_none(input.col_var())
        row_var = var_to_none(input.row_var())
        tooltips = [
            alt.Tooltip(input.x_var()),
            alt.Tooltip(input.y_var()),
            alt.Tooltip(input.color()),
        ]
        for var in [col_var, row_var]:
            if var is not None:
                tooltips.append(alt.Tooltip(var))
        chart = (
            alt.Chart(parsed_file())
            .mark_bar()
            .encode(
                x=input.x_var(), y=input.y_var(), color=input.color(), tooltip=tooltips
            )
        )

        if col_var is not None and row_var is not None:
            chart = chart.facet(column=input.col_var(), row=input.row_var())
        elif col_var is not None:
            chart = chart.facet(
                column=input.col_var(),
            )
        elif row_var is not None:
            chart = chart.facet(row=input.row_var())
        return chart


with ui.nav_panel("Plot penguins"):
    ui.input_selectize(
        "var", "Select variable", choices=["bill_length_mm", "body_mass_g"]
    )

    @render_altair
    def hist():
        import altair as alt
        from palmerpenguins import load_penguins

        df = load_penguins()
        return (
            alt.Chart(df)
            .mark_bar()
            .encode(x=alt.X(f"{input.var()}:Q", bin=True), y="count()")
            .properties(height=200, width=300)
        )
