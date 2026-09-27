"""Sound (semantics-preserving) circuit rewrite passes."""
from .cancel import cancel, cancel_pass
from .commutation import commute
from .fuse import fuse_1q
from .hadamard import hadamard_reduce, hadamard_reduce_pass
from .phasefold import phase_fold

__all__ = ["cancel", "cancel_pass", "commute", "fuse_1q", "hadamard_reduce", "hadamard_reduce_pass",
           "phase_fold"]
