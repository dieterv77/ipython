# -*- coding: utf-8 -*-
"""Pylab (matplotlib) support utilities.

Authors
-------

* Fernando Perez.
* Brian Granger
"""

#-----------------------------------------------------------------------------
#  Copyright (C) 2009  The IPython Development Team
#
#  Distributed under the terms of the BSD License.  The full license is in
#  the file COPYING, distributed as part of this software.
#-----------------------------------------------------------------------------

#-----------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------

from io import BytesIO

from IPython.utils.decorators import flag_calls

# If user specifies a GUI, that dictates the backend, otherwise we read the
# user's mpl default from the mpl rc structure
backends = {'tk': 'TkAgg',
            'gtk': 'GTKAgg',
            'wx': 'WXAgg',
            'qt': 'Qt4Agg', # qt3 not supported
            'qt4': 'Qt4Agg',
            'osx': 'MacOSX',
            'inline' : 'module://IPython.zmq.pylab.backend_inline'}

# We also need a reverse backends2guis mapping that will properly choose which
# GUI support to activate based on the desired matplotlib backend.  For the
# most part it's just a reverse of the above dict, but we also need to add a
# few others that map to the same GUI manually:
backend2gui = dict(zip(backends.values(), backends.keys()))
# In the reverse mapping, there are a few extra valid matplotlib backends that
# map to the same GUI support
backend2gui['GTK'] = backend2gui['GTKCairo'] = 'gtk'
backend2gui['WX'] = 'wx'
backend2gui['CocoaAgg'] = 'osx'

#-----------------------------------------------------------------------------
# Matplotlib utilities
#-----------------------------------------------------------------------------


def getfigs(*fig_nums):
    """Get a list of matplotlib figures by figure numbers.

    If no arguments are given, all available figures are returned.  If the
    argument list contains references to invalid figures, a warning is printed
    but the function continues pasting further figures.

    Parameters
    ----------
    figs : tuple
        A tuple of ints giving the figure numbers of the figures to return.
    """
    from matplotlib._pylab_helpers import Gcf
    if not fig_nums:
        fig_managers = Gcf.get_all_fig_managers()
        return [fm.canvas.figure for fm in fig_managers]
    else:
        figs = []
        for num in fig_nums:
            f = Gcf.figs.get(num)
            if f is None:
                print('Warning: figure %s not available.' % num)
            else:
                figs.append(f.canvas.figure)
        return figs


def figsize(sizex, sizey):
    """Set the default figure size to be [sizex, sizey].

    This is just an easy to remember, convenience wrapper that sets::

      matplotlib.rcParams['figure.figsize'] = [sizex, sizey]
    """
    import matplotlib
    matplotlib.rcParams['figure.figsize'] = [sizex, sizey]


def print_figure(fig, fmt='png'):
    """Convert a figure to svg or png for inline display."""
    # When there's an empty figure, we shouldn't return anything, otherwise we
    # get big blank areas in the qt console.
    if not fig.axes:
        return

    fc = fig.get_facecolor()
    ec = fig.get_edgecolor()
    fig.set_facecolor('white')
    fig.set_edgecolor('white')
    try:
        bytes_io = BytesIO()
        fig.canvas.print_figure(bytes_io, format=fmt, bbox_inches='tight')
        data = bytes_io.getvalue()
    finally:
        fig.set_facecolor(fc)
        fig.set_edgecolor(ec)
    return data


# We need a little factory function here to create the closure where
# safe_execfile can live.
def mpl_runner(safe_execfile):
    """Factory to return a matplotlib-enabled runner for %run.

    Parameters
    ----------
    safe_execfile : function
      This must be a function with the same interface as the
      :meth:`safe_execfile` method of IPython.

    Returns
    -------
    A function suitable for use as the ``runner`` argument of the %run magic
    function.
    """
    
    def mpl_execfile(fname,*where,**kw):
        """matplotlib-aware wrapper around safe_execfile.

        Its interface is identical to that of the :func:`execfile` builtin.

        This is ultimately a call to execfile(), but wrapped in safeties to
        properly handle interactive rendering."""

        import matplotlib
        import matplotlib.pylab as pylab

        #print '*** Matplotlib runner ***' # dbg
        # turn off rendering until end of script
        is_interactive = matplotlib.rcParams['interactive']
        matplotlib.interactive(False)
        safe_execfile(fname,*where,**kw)
        matplotlib.interactive(is_interactive)
        # make rendering call now, if the user tried to do it
        if pylab.draw_if_interactive.called:
            pylab.draw()
            pylab.draw_if_interactive.called = False

    return mpl_execfile


def select_figure_format(shell, fmt):
    """Select figure format for inline backend, either 'png' or 'svg'.

    Using this method ensures only one figure format is active at a time.
    """
    from matplotlib.figure import Figure
    from IPython.zmq.pylab import backend_inline

    svg_formatter = shell.display_formatter.formatters['image/svg+xml']
    png_formatter = shell.display_formatter.formatters['image/png']

    if fmt=='png':
        svg_formatter.type_printers.pop(Figure, None)
        png_formatter.for_type(Figure, lambda fig: print_figure(fig, 'png'))
    elif fmt=='svg':
        png_formatter.type_printers.pop(Figure, None)
        svg_formatter.for_type(Figure, lambda fig: print_figure(fig, 'svg'))
    else:
        raise ValueError("supported formats are: 'png', 'svg', not %r"%fmt)

    # set the format to be used in the backend()
    backend_inline._figure_format = fmt

#-----------------------------------------------------------------------------
# Code for initializing matplotlib and importing pylab
#-----------------------------------------------------------------------------


def find_gui_and_backend(gui=None):
    """Given a gui string return the gui and mpl backend.

    Parameters
    ----------
    gui : str
        Can be one of ('tk','gtk','wx','qt','qt4','inline').

    Returns
    -------
    A tuple of (gui, backend) where backend is one of ('TkAgg','GTKAgg',
    'WXAgg','Qt4Agg','module://IPython.zmq.pylab.backend_inline').
    """

    import matplotlib

    if gui and gui != 'auto':
        # select backend based on requested gui
        backend = backends[gui]
    else:
        backend = matplotlib.rcParams['backend']
        # In this case, we need to find what the appropriate gui selection call
        # should be for IPython, so we can activate inputhook accordingly
        gui = backend2gui.get(backend, None)
    return gui, backend


def activate_matplotlib(backend):
    """Activate the given backend and set interactive to True."""

    import matplotlib
    if backend.startswith('module://'):
        # Work around bug in matplotlib: matplotlib.use converts the
        # backend_id to lowercase even if a module name is specified!
        matplotlib.rcParams['backend'] = backend
    else:
        matplotlib.use(backend)
    matplotlib.interactive(True)

    # This must be imported last in the matplotlib series, after
    # backend/interactivity choices have been made
    import matplotlib.pylab as pylab

    # XXX For now leave this commented out, but depending on discussions with
    # mpl-dev, we may be able to allow interactive switching...
    #import matplotlib.pyplot
    #matplotlib.pyplot.switch_backend(backend)

    pylab.show._needmain = False
    # We need to detect at runtime whether show() is called by the user.
    # For this, we wrap it into a decorator which adds a 'called' flag.
    pylab.draw_if_interactive = flag_calls(pylab.draw_if_interactive)

def import_pylab(user_ns, backend, import_all=True, shell=None):
    """Import the standard pylab symbols into user_ns."""

    # Import numpy as np/pyplot as plt are conventions we're trying to
    # somewhat standardize on.  Making them available to users by default
    # will greatly help this.
    s = ("import numpy\n"
          "import matplotlib\n"
          "from matplotlib import pylab, mlab, pyplot\n"
          "np = numpy\n"
          "plt = pyplot\n"
          )
    exec s in user_ns

    if shell is not None:
        exec s in shell.user_ns_hidden
        # If using our svg payload backend, register the post-execution
        # function that will pick up the results for display.  This can only be
        # done with access to the real shell object.
        #
        from IPython.zmq.pylab.backend_inline import InlineBackend

        cfg = InlineBackend.instance(config=shell.config)
        cfg.shell = shell
        if cfg not in shell.configurables:
            shell.configurables.append(cfg)

        if backend == backends['inline']:
            from IPython.zmq.pylab.backend_inline import flush_figures
            from matplotlib import pyplot
            shell.register_post_execute(flush_figures)
            # load inline_rc
            pyplot.rcParams.update(cfg.rc)
            
            # Add 'figsize' to pyplot and to the user's namespace
            user_ns['figsize'] = pyplot.figsize = figsize
            shell.user_ns_hidden['figsize'] = figsize
        
        # Setup the default figure format
        fmt = cfg.figure_format
        select_figure_format(shell, fmt)

        # The old pastefig function has been replaced by display
        from IPython.core.display import display
        # Add display and display_png to the user's namespace
        user_ns['display'] = display
        shell.user_ns_hidden['display'] = display
        user_ns['getfigs'] = getfigs
        shell.user_ns_hidden['getfigs'] = getfigs

    if import_all:
        s = ("from matplotlib.pylab import *\n"
             "from numpy import *\n")
        exec s in user_ns
        if shell is not None:
            exec s in shell.user_ns_hidden


def pylab_activate(user_ns, gui=None, import_all=True, shell=None):
    """Activate pylab mode in the user's namespace.

    Loads and initializes numpy, matplotlib and friends for interactive use.

    Parameters
    ----------
    user_ns : dict
      Namespace where the imports will occur.

    gui : optional, string
      A valid gui name following the conventions of the %gui magic.

    import_all : optional, boolean
      If true, an 'import *' is done from numpy and pylab.

    Returns
    -------
    The actual gui used (if not given as input, it was obtained from matplotlib
    itself, and will be needed next to configure IPython's gui integration.
    """
    gui, backend = find_gui_and_backend(gui)
    activate_matplotlib(backend)
    import_pylab(user_ns, backend, import_all, shell)

    print """
Welcome to pylab, a matplotlib-based Python environment [backend: %s].
For more information, type 'help(pylab)'.""" % backend
    
    return gui

