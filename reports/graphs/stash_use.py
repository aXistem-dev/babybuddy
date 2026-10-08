# -*- coding: utf-8 -*-
from collections import OrderedDict

from django.utils import timezone
from django.utils.translation import gettext as _

import plotly.graph_objs as go
import plotly.offline as plotly

from reports import utils


def stash_use(feedings):
    """
    Stacked bars per day: milk taken from the stash, one series per baby.
    :param feedings: a queryset/iterable of Feeding instances with
        `stash_amount` set (`select_related("child")` avoids N+1 lookups).
    :returns: a tuple of the graph's html and javascript.
    """
    days = OrderedDict()
    children = OrderedDict()
    for feeding in feedings:
        children.setdefault(feeding.child_id, str(feeding.child))
        day = str(timezone.localtime(feeding.start).date())
        days.setdefault(day, {})
        days[day][feeding.child_id] = (
            days[day].get(feeding.child_id, 0.0) + feeding.stash_amount
        )
    traces = [
        go.Bar(
            name=name,
            x=list(days),
            y=[round(day.get(child_id, 0.0), 2) for day in days.values()],
        )
        for child_id, name in children.items()
    ]
    layout_args = utils.default_graph_layout_options()
    layout_args["title"] = "<b>" + _("Milk From the Stash per Baby") + "</b>"
    layout_args["xaxis"]["title"] = _("Date")
    layout_args["xaxis"]["rangeselector"] = utils.rangeselector_date()
    layout_args["yaxis"]["title"] = _("Amount")
    fig = go.Figure({"data": traces, "layout": go.Layout(**layout_args)})
    fig.update_layout(barmode="stack")
    output = plotly.plot(fig, output_type="div", include_plotlyjs=False)
    return utils.split_graph_output(output)
