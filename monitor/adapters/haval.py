import re
from bs4 import BeautifulSoup
from .base import Adapter, NeedsReview


class HavalAdapter(Adapter):
    brand_id = 'haval'

    def parse(self, document, verified_at):
        soup = BeautifulSoup(document.text, 'html.parser')
        if not soup.title or 'HAVAL' not in soup.title.get_text().upper():
            raise NeedsReview('HAVAL page identity changed')
        matches = []
        for card in soup.select('.web_block_models__item-info'):
            title = card.select_one('.web_block_models__item-title')
            if not title or title.get_text(strip=True) != 'H3':
                continue
            price_node = card.select_one('.web_block_models__item-price')
            disclaimer = card.select_one('.card-disclaimer-popup__info-text')
            if price_node is None or disclaimer is None:
                raise NeedsReview('H3 price/disclaimer card missing')
            raw = ' '.join(str(t).strip() for t in price_node.find_all(string=True, recursive=False)).strip()
            conditions = disclaimer.get_text(' ', strip=True)
            header = re.search(r'Цена автомобиля HAVAL H3 (20\d{2}) модельного года в комплектации ([^,]+), (20\d{2}) года производства с учетом выгоды', conditions)
            starts = re.findall(r'предусмотрена с (\d{2})\.(\d{2})\.(20\d{2})', conditions)
            if not header or len(set(starts)) != 1 or not all(token in conditions.casefold() for token in ['лояльный трейд-ин', 'haval или great wall', '3 (три)']):
                raise NeedsReview('H3 model/year/trim/loyal trade-in conditions changed')
            d, m, y = starts[0]
            offer = self.offer(document, verified_at, model_id='haval-h3', raw_price=raw,
                               trim=header[2], model_year=int(header[1]), production_year=int(header[3]),
                               conditions=conditions, effective_date=f'{y}-{m}-{d}',
                               excerpt=f'HAVAL H3 | {raw} | {conditions}')
            offer['condition_labels'] = ['HAVAL / Great Wall 置换', '持有至少 3 个月', '置换 / Trade-in']
            matches.append(offer)
        if not matches:
            raise NeedsReview('No reviewed H3 card found; not guessing from unrelated RUB amounts')
        if any(o != matches[0] for o in matches[1:]):
            raise NeedsReview('Duplicate H3 cards disagree')
        return matches[:1]
