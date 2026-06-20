"""digimon_data — read the Digimon asset package with a small typed API.

Quickstart:

    from digimon_data import DigimonDB

    db = DigimonDB("assets")              # path to the package (holds index.json)
    for cat in db.categories():
        print(cat.id, cat.label, len(cat.dims))

    dim = db.load_dim("v", "gamma")       # one self-contained evolution chart
    for stage, mons in dim.by_stage().items():
        print(stage, [m.name for m in mons])

    gamma = dim.get("gamma")
    print(gamma.frame1_path)              # absolute path to the sprite
    print([m.name for m in dim.next("gamma")])   # what it evolves into
"""
from .db import DigimonDB
from .models import Category, DimRef, Dim, Digimon, Evolution, STAGE_ORDER, stage_rank

__all__ = [
    "DigimonDB",
    "Category",
    "DimRef",
    "Dim",
    "Digimon",
    "Evolution",
    "STAGE_ORDER",
    "stage_rank",
]

__version__ = "1.0.0"
