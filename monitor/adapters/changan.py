from .base import Adapter


class ChanganAdapter(Adapter):
    brand_id = 'changan'

    def parse(self, document, verified_at):
        return self.discover(document, 'Changan', 'CS75', 'прайс')
