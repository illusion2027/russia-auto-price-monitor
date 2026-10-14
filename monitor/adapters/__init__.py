from .haval import HavalAdapter
from .geely import GeelyAdapter
from .tenet import TenetAdapter
from .changan import ChanganAdapter
from .hongqi import HongqiAdapter

ADAPTERS = {cls.brand_id: cls for cls in [GeelyAdapter, HavalAdapter, TenetAdapter, ChanganAdapter, HongqiAdapter]}
