"""qcpso -- quantum circuit optimisation with particle swarm optimisation.

The main entry point is :func:`qcpso.framework.optimize` (the HyPSO-QCO
framework).  See ``docs/FRAMEWORK.md`` for the method description.
"""
from .circuit import Circuit, Gate

__version__ = "0.1.0"
__all__ = ["Circuit", "Gate", "__version__"]
