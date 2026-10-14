from .base import Adapter


class HongqiAdapter(Adapter):
    brand_id = 'hongqi'

    def parse(self, document, verified_at):
        return self.discover(document, 'Hongqi', 'HS3', 'Прайс-лист')
