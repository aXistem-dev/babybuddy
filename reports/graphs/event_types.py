# -*- coding: utf-8 -*-
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils.translation import gettext as _
from django.utils.translation import get_language

import plotly.offline as plotly
import plotly.graph_objs as go

from reports import utils


def event_types(instances):
    """
    Create a graph showing the number of events per day, stacked by event type.
    :param instances: a QuerySet of Event instances.
    :returns: a tuple of the graph's html and javascript.
    """
    totals = (
        instances.annotate(date=TruncDate("time"))
        .values("date", "type__name")
        .annotate(count=Count("id"))
        .order_by("type__name", "date")
    )

    if not totals:
        return None, None

    per_type = {}
    for row in totals:
        dates, counts = per_type.setdefault(row["type__name"], ([], []))
        dates.append(row["date"])
        counts.append(row["count"])

    traces = []
    for name, (dates, counts) in per_type.items():
        traces.append(go.Bar(name=name, x=dates, y=counts, hovertemplate="%{y}"))

    layout_args = utils.default_graph_layout_options()
    layout_args["barmode"] = "stack"
    layout_args["title"] = "<b>" + _("Events per Day") + "</b>"
    layout_args["xaxis"]["title"] = _("Date")
    layout_args["xaxis"]["type"] = "date"
    layout_args["xaxis"]["autorange"] = True
    all_dates = sorted(
        {date for dates, counts in per_type.values() for date in dates}, reverse=True
    )
    layout_args["xaxis"]["autorangeoptions"] = utils.autorangeoptions(all_dates)
    layout_args["xaxis"]["rangeselector"] = utils.rangeselector_date()
    layout_args["yaxis"]["title"] = _("Number of events")

    fig = go.Figure({"data": traces, "layout": go.Layout(**layout_args)})
    output = plotly.plot(
        fig,
        output_type="div",
        include_plotlyjs=False,
        config={"locale": get_language()},
    )
    return utils.split_graph_output(output)
