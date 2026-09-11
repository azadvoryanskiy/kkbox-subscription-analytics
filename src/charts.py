"""Chart style for the case study.

The reference palette from the dataviz method: blue and orange as the two
categorical slots, gray for context. Hairline, recessive axes; 2px lines; bars
no thicker than 24px with a 4px rounded data end and a square baseline. Text
always uses ink colours, never a series colour. Charts go to docs/img/.
"""

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import PathPatch
from matplotlib.path import Path as MPath

IMG_DIR = Path(__file__).resolve().parents[1] / "docs" / "img"

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
BLUE = "#2a78d6"        # categorical slot 1
BLUE_LIGHT = "#86b6ef"  # blue ramp step 250, the lighter shade of the same hue
ORANGE = "#eb6834"      # categorical slot 2
GRAY = "#c3c2b7"        # context series

PX = 1 / 96  # one screen pixel in inches


def use_style() -> None:
    mpl.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
        "font.size": 9.5,
        "text.color": INK,
        "axes.labelcolor": INK_2,
        "axes.labelsize": 9,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "xtick.labelsize": 8.5,
        "ytick.labelsize": 8.5,
        "axes.edgecolor": AXIS,
        "axes.linewidth": 0.75,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": False,
        "axes.grid": True,
        "axes.grid.axis": "y",
        "grid.color": GRID,
        "grid.linewidth": 0.75,
        "grid.linestyle": "-",
        "axes.axisbelow": True,
        "xtick.major.size": 0,
        "ytick.major.size": 0,
        "xtick.major.pad": 6,
        "ytick.major.pad": 6,
        "lines.linewidth": 1.5,
        "lines.solid_capstyle": "round",
        "lines.solid_joinstyle": "round",
        "legend.frameon": False,
        "legend.fontsize": 8.5,
        "legend.handlelength": 1.2,
        "figure.dpi": 110,
        "savefig.dpi": 200,
    })


def figure(width=7.2, height=3.8, left=0.08, right=0.97, bottom=0.13, top=0.74):
    """A figure with one axes at a fixed position, so bar geometry is exact."""
    fig = plt.figure(figsize=(width, height))
    ax = fig.add_axes([left, bottom, right - left, top - bottom])
    return fig, ax


def titles(fig, ax, title, subtitle=None):
    """Left-aligned title and subtitle above the plot."""
    x = ax.get_position().x0
    top = ax.get_position().y1
    fig.text(x, top + 0.16, title, fontsize=12, fontweight="bold", color=INK, va="bottom")
    if subtitle:
        fig.text(x, top + 0.10, subtitle, fontsize=9, color=INK_2, va="bottom")


def legend(ax, handles_labels, y=1.02):
    """A one-row legend just above the plot area."""
    handles, labels = zip(*handles_labels)
    ax.legend(handles, labels, loc="lower left", bbox_to_anchor=(0, y), ncol=len(labels),
              borderaxespad=0, columnspacing=1.6)


def _units_per_inch(ax):
    fig = ax.figure
    pos = ax.get_position()
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    return (x1 - x0) / (pos.width * fig.get_figwidth()), (y1 - y0) / (pos.height * fig.get_figheight())


def bars(ax, positions, values, colors, horizontal=False, slot=1.0, max_px=24, radius_px=4, starts=None):
    """Bars with a 4px rounded data end and a square baseline.

    Set the axis limits before calling: the rounding and the 24px thickness cap
    are converted from pixels to data units with the final axes size. `starts`
    lets a bar begin somewhere other than zero (for stacked segments).
    """
    ux, uy = _units_per_inch(ax)
    across, along = (uy, ux) if horizontal else (ux, uy)
    width = min(0.6 * slot, max_px * PX * across)
    if isinstance(colors, str):
        colors = [colors] * len(values)
    starts = starts if starts is not None else [0] * len(values)
    for p, v, c, s0 in zip(positions, values, colors, starts):
        _bar(ax, p, s0, s0 + v, width, min(radius_px * PX * across, width / 2),
             min(radius_px * PX * along, abs(v)), horizontal, c, round_end=True)
    return width


def _bar(ax, p, start, end, width, r_across, r_along, horizontal, color, round_end):
    a0, a1 = p - width / 2, p + width / 2
    s = 1 if end >= start else -1
    if round_end and r_along > 0:
        verts = [(a0, start), (a0, end - s * r_along), (a0, end), (a0 + r_across, end),
                 (a1 - r_across, end), (a1, end), (a1, end - s * r_along), (a1, start), (a0, start)]
        codes = [MPath.MOVETO, MPath.LINETO, MPath.CURVE3, MPath.CURVE3, MPath.LINETO,
                 MPath.CURVE3, MPath.CURVE3, MPath.LINETO, MPath.CLOSEPOLY]
    else:
        verts = [(a0, start), (a0, end), (a1, end), (a1, start), (a0, start)]
        codes = [MPath.MOVETO, MPath.LINETO, MPath.LINETO, MPath.LINETO, MPath.CLOSEPOLY]
    if horizontal:
        verts = [(b, a) for a, b in verts]
    ax.add_patch(PathPatch(MPath(verts, codes), facecolor=color, edgecolor="none", zorder=2))


def stacked_hbar(ax, y, parts, colors, gap_px=2, max_px=24, radius_px=4):
    """One horizontal stacked bar; segments separated by a 2px surface gap."""
    ux, uy = _units_per_inch(ax)
    width = max_px * PX * uy
    gap = gap_px * PX * ux
    start = 0.0
    for i, (v, c) in enumerate(zip(parts, colors)):
        last = i == len(parts) - 1
        end = start + v - (0 if last else gap)
        _bar(ax, y, start, end, width, min(radius_px * PX * uy, width / 2),
             min(radius_px * PX * ux, v), True, c, round_end=last)
        start += v
    return width


def line(ax, x, y, color, label=None, end_dot=True, **kw):
    """A 2px line with an end dot ringed in the surface colour."""
    (h,) = ax.plot(x, y, color=color, label=label, zorder=3, **kw)
    if end_dot:
        ax.plot([list(x)[-1]], [list(y)[-1]], marker="o", markersize=6.5, color=color,
                markeredgecolor=SURFACE, markeredgewidth=1.5, zorder=4)
    return h


def note(ax, x, y, text, ha="left", va="center", color=INK_2, **kw):
    """A direct label in ink, never in the series colour."""
    ax.text(x, y, text, ha=ha, va=va, color=color, fontsize=8.5, zorder=5, **kw)


def save(fig, name):
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(IMG_DIR / name, bbox_inches="tight", pad_inches=0.12)
    return IMG_DIR / name
