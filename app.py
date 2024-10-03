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


def title_case(s: str) -> str:
    if isinstance(s, str):
        return s.replace("_", " ").title()


_COLOR_MAP = {
    "Battery": "#4379AB",
    "CCS": "#96CCEB",
    "Coal": "#FF8900",
    "Distributed Solar": "#FFBC71",
    "Geothermal": "#3DA443",
    "Hydro": "#76D472",
    "Hydrogen": "#BA9900",
    "Natural Gas CC": "#F7CD4B",
    "Natural Gas CT": "#249A95",
    "Nuclear": "#77BEB6",
    "Solar": "#F14A54",
    "Wind": "#FF9797",
}

TECH_ORDER = [
    "Nuclear",
    "CCS",
    "Natural Gas CC",
    "Natural Gas CT",
    "Coal",
    "Geothermal",
    "Hydro",
    "Distributed Solar",
    "Solar",
    "Wind",
    "Hydrogen",
    "Battery",
]

COLOR_MAP = {k: _COLOR_MAP[k] for k in TECH_ORDER[::-1]}


def config_chart_row_col(chart: alt.Chart, row_var: str, col_var: str) -> alt.Chart:
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


def chart_total_cap_line(
    cap: pd.DataFrame,
    x_var="planning_year",
    col_var="tech_type",
    row_var="case",
    color="model",
    order=None,
    scale="linear",
    width=alt.Step(40),
    height=200,
) -> alt.Chart:
    x_var = var_to_none(x_var)
    col_var = var_to_none(col_var)
    row_var = var_to_none(row_var)

    group_by = []
    _tooltips = [
        alt.Tooltip("end_value", title="Capacity (GW)", format=",.0f"),
    ]

    for var in [x_var, col_var, row_var, color]:
        if var is not None:
            group_by.append(var)
            _tooltips.append(alt.Tooltip(var))

    group_by = [c for c in set(group_by) if c in cap.columns]
    cap_data = cap.groupby(list(set(group_by)), as_index=False)["end_value"].sum()
    cap_data["end_value"] /= 1000
    # cap_data["case"] = cap_data["case"].map(WRAPPED_CASE_NAME_MAP)
    cap_data = fill_idx(cap_data, list(set(group_by)))

    if color == "tech_type":
        _color = (
            alt.Color(color).scale(
                domain=list(COLOR_MAP.keys()), range=list(COLOR_MAP.values())
            )
            # .title(title_case(color))
        )
    else:
        _color = (
            alt.Color(color)
            # .title(title_case(color))
            # .sort(order_dict().get(color))
        )
    chart = (
        alt.Chart(cap_data)
        .mark_line(point=True)
        .encode(
            x=alt.X(x_var).axis(format="04d"),  # .title(title_case(x_var)),
            # x=alt.X("y")
            # .sort(order_dict().get("planning_year"))
            # .title(title_case("planning_year")),
            y=alt.Y("sum(end_value)").title("Capacity (GW)").scale(type=scale.lower()),
            color=_color,
            tooltip=_tooltips,
            # column="tt",
            # row="c",
        )
        .properties(width=width, height=height)
    )
    chart = config_chart_row_col(chart, row_var, col_var)
    return chart


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
        "cap_line_col_var",
        "Column",
        choices={
            c: title_case(c)
            for c in [
                "model",
                "case",
                "planning_year",
                "tech_type",
                "zone",
                "agg_zone",
                "None",
            ]
        },
        selected="tech_type",
        width="125px",
    )
    ui.input_selectize(
        "cap_line_row_var",
        "Row",
        choices={
            c: title_case(c)
            for c in [
                "model",
                "case",
                "planning_year",
                "tech_type",
                "zone",
                "agg_zone",
                "None",
            ]
        },
        selected="case",
        width="150px",
    )
    ui.input_selectize(
        "cap_line_color",
        "Color",
        choices={
            c: title_case(c)
            for c in ["model", "case", "planning_year", "tech_type", "agg_zone", "None"]
        },
        selected="model",
        width="125px",
    )

with ui.nav_panel("Plot user data"):
    ui.input_file("file1", "Choose CSV File", accept=[".csv", ".gz"], multiple=False)

    @render_altair
    def alt_cap_lines():
        if parsed_file().empty:
            return None
        chart = chart_total_cap_line(
            parsed_file(),
            x_var="planning_year",  # input.cap_line_x_var(),
            col_var=input.cap_line_col_var(),
            row_var=input.cap_line_row_var(),
            color=input.cap_line_color(),
            height=200,  # * (input.cap_line_height() / 100),
            width=200,  # * (input.cap_line_width() / 100),
        )
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
