# -*- coding: utf-8 -*-
from django.utils import timezone
from django.utils.translation import gettext as _

import plotly.graph_objs as go
import plotly.offline as plotly

from reports import utils


def stash_balance(events):
    """
    Step line of the milk stash balance over time.
    :param events: the list returned by core.stash.stash_events().
    :returns: a tuple of the graph's html and javascript.
    """
    times, balances, running = [], [], 0.0
    for event in events:
        running += event.amount
        times.append(timezone.localtime(event.time))
        balances.append(round(running, 2))
    trace = go.Scatter(
        name=_("Stash"),
        x=times,
        y=balances,
        mode="lines+markers",
        line={"shape": "hv"},
        fill="tozeroy",
    )
    layout_args = utils.default_graph_layout_options()
    layout_args["title"] = "<b>" + _("Milk Stash") + "</b>"
    layout_args["xaxis"]["title"] = _("Date")
    layout_args["xaxis"]["rangeselector"] = utils.rangeselector_date()
    layout_args["yaxis"]["title"] = _("Amount in stash")
    fig = go.Figure({"data": [trace], "layout": go.Layout(**layout_args)})
    fig.add_hline(y=0, line_dash="dot")
    output = plotly.plot(fig, output_type="div", include_plotlyjs=False)
    return utils.split_graph_output(output)
