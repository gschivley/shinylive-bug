import altair as alt
import pandas as pd
from altair.utils import Undefined
from shiny.express import module, render, ui
from shinywidgets import render_altair


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
    opacity="None",
    cap_types=None,
    avg_by=None,
):
    x_var = var_to_none(x_var)
    col_var = var_to_none(col_var)
    row_var = var_to_none(row_var)
    shape = var_to_none(shape)
    dash = var_to_none(dash)
    color = var_to_none(color)
    opacity = var_to_none(opacity)

    if "capacity_type" in df.columns and cap_types is not None:
        df = df.loc[df["capacity_type"].isin(cap_types), :]

    group_by = [
        var
        for var in [x_var, col_var, row_var, color, shape, dash, opacity]
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
    points=True,
    interactive_zoom=False,
    interpolate="linear",
    tension=0.75,
    legend_selection_fields=None,
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

    # selection_fields = [f for f in legend_selection_fields if f is not None]
    # selection = alt.selection_point(fields=selection_fields or [], bind="legend")

    chart = (
        alt.Chart(data)
        .mark_line(
            point=dash is None and points, interpolate=interpolate, tension=tension
        )
        .encode(
            x=alt.X(x_var),
            y=alt.Y("sum(value)"),
            color=color,
            tooltip=_tooltips,
            # opacity=alt.condition(selection, alt.value(0.8), alt.value(0.2)),
        )
        # .add_params(selection)
        .properties(width=width, height=height)
        # .interactive()
    )
    if dash is not None:
        chart = chart.encode(strokeDash=dash)
        if points:
            points_chart = (
                alt.Chart(data)
                .mark_point(filled=True)
                .encode(
                    x=alt.X(x_var),
                    y=alt.Y("sum(value)"),
                    color=alt.Color(color),
                    tooltip=_tooltips,
                    # opacity=alt.condition(selection, alt.value(0.8), alt.value(0.2)),
                )
                # .add_params(selection)
                .properties(width=width, height=height)
                # .interactive()
            )
            chart = chart + points_chart  # .resolve_scale(strokeDash="independent")
    if interactive_zoom:
        chart = chart.interactive(bind_y=False)
    chart = config_chart_row_col(chart, row_var, col_var)
    return chart


def chart_error_line(
    data: pd.DataFrame,
    x_var="planning_year",
    col_var="tech_type",
    row_var="case",
    color="model",
    shape=None,
    dash=None,
    errorband="stderr",
    legend_selection_fields=None,
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

    # selection_fields = [f for f in legend_selection_fields if f is not None]
    # selection = alt.selection_point(fields=selection_fields or [], bind="legend")

    lines = (
        alt.Chart(data)
        .mark_line(point=dash is None)
        .encode(
            x=alt.X(x_var),
            y=alt.Y("value"),
            color=color,
            tooltip=_tooltips,
            # opacity=alt.condition(selection, alt.value(0.8), alt.value(0.2)),
        )
        # .add_params(selection)
        .properties(width=width, height=height)
        # .interactive()
    )
    _tooltips.extend(
        [
            alt.Tooltip("high_value"),
            alt.Tooltip("low_value"),
        ]
    )
    band = (
        alt.Chart(data)
        .mark_errorband(borders=True)
        .encode(
            x=alt.X(x_var),
            # y=alt.Y("value"),
            y=alt.Y("high_value"),
            y2=alt.Y2("low_value"),
            color=alt.Color(color),
            tooltip=_tooltips,
        )
    )
    # if dash is not None:
    #     band.encode(strokeDash=dash)
    chart = lines + band

    chart = config_chart_row_col(chart, row_var, col_var)
    return chart


def chart_total_stacked_area(
    data: pd.DataFrame,
    x_var="planning_year",
    col_var="tech_type",
    row_var="case",
    color="model",
    interactive_zoom=False,
    legend_selection_fields=None,
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
    color = var_to_none(color)

    # group_by = []
    _tooltips = [alt.Tooltip("value")]  # , title="Capacity (GW)", format=",.0f"),

    for var in [x_var, col_var, row_var, color]:
        if var is not None:
            _tooltips.append(alt.Tooltip(var))

    # selection_fields = [f for f in legend_selection_fields if f is not None]
    # selection = alt.selection_point(fields=selection_fields or [], bind="legend")

    chart = (
        alt.Chart(data)
        .mark_area()
        .encode(
            x=alt.X(x_var),
            y=alt.Y("sum(value)"),
            color=color,
            tooltip=_tooltips,
            # opacity=alt.condition(selection, alt.value(0.8), alt.value(0.2)),
        )
        # .add_params(selection)
        .properties(width=width, height=height)
        # .interactive()
    )
    if interactive_zoom:
        chart = chart.interactive(bind_y=False)
    chart = config_chart_row_col(chart, row_var, col_var)
    return chart


def chart_total_bar(
    data: pd.DataFrame,
    x_var="planning_year",
    col_var="tech_type",
    row_var="case",
    color="model",
    opacity=None,
    legend_selection_fields=None,
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
    opacity = var_to_none(opacity)
    color = var_to_none(color)

    # group_by = []
    _tooltips = [alt.Tooltip("value")]  # , title="Capacity (GW)", format=",.0f"),

    for var in [x_var, col_var, row_var, color, opacity]:
        if var is not None:
            _tooltips.append(alt.Tooltip(var))

    # selection_fields = [f for f in legend_selection_fields if f is not None]
    # selection = alt.selection_point(fields=selection_fields or [], bind="legend")

    chart = (
        alt.Chart(data)
        .mark_bar()
        .encode(
            x=alt.X(x_var),
            y=alt.Y("sum(value)"),
            color=color,
            tooltip=_tooltips,
            # opacity=alt.condition(selection, alt.value(0.8), alt.value(0.2)),
        )
        # .add_params(selection)
        .properties(width=width, height=height)
        # .interactive()
    )
    if opacity:
        chart.encode(opacity=opacity)

    chart = config_chart_row_col(chart, row_var, col_var)
    return chart
