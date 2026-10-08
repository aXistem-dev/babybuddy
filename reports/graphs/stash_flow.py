# -*- coding: utf-8 -*-
from collections import OrderedDict

from django.utils import timezone
from django.utils.translation import gettext as _

import plotly.graph_objs as go
import plotly.offline as plotly

from reports import utils


def _series():
    return (
        ("pumping", _("Stored from pumping")),
        ("added", _("Added")),
        ("feeding", _("Drunk")),
        ("discarded", _("Discarded")),
    )


def stash_flow(events):
    """
    Stacked bars per day: milk into the stash (positive) and out of it (negative).
    :param events: the list returned by core.stash.stash_events().
    :returns: a tuple of the graph's html and javascript.
    """
    series = _series()
    days = OrderedDict()
    for event in events:
        day = str(timezone.localtime(event.time).date())
        days.setdefault(day, {kind: 0.0 for kind, _label in series})
        days[day][event.kind] += event.amount
    traces = [
        go.Bar(name=label, x=list(days), y=[round(d[kind], 2) for d in days.values()])
        for kind, label in series
    ]
    layout_args = utils.default_graph_layout_options()
    layout_args["title"] = "<b>" + _("Milk Stash In and Out") + "</b>"
    layout_args["xaxis"]["title"] = _("Date")
    layout_args["xaxis"]["rangeselector"] = utils.rangeselector_date()
    layout_args["yaxis"]["title"] = _("Amount")
    fig = go.Figure({"data": traces, "layout": go.Layout(**layout_args)})
    fig.update_layout(barmode="relative")
    output = plotly.plot(fig, output_type="div", include_plotlyjs=False)
    return utils.split_graph_output(output)
