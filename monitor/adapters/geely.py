from .base import Adapter


class GeelyAdapter(Adapter):
    brand_id = 'geely'

    def parse(self, document, verified_at):
        return self.discover(document, 'Geely', 'Monjaro', 'прайс')
