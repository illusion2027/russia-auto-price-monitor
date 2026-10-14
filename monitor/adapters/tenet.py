import re
from urllib.parse import urljoin, urlparse
import fitz
from bs4 import BeautifulSoup
from .base import Adapter, NeedsReview
from ..common import parse_amount
from ..pdf import pdf_text


class TenetAdapter(Adapter):
    brand_id = 'tenet'

    def parse(self, document, verified_at):
        return self.discover(document, 'TENET', 'T7', 'Прайс-лист')

    def collect(self, fetcher, verified_at):
        page = fetcher.get(self.source['source_url'])
        soup = BeautifulSoup(page.text, 'html.parser')
        if not soup.title or 'TENET T7' not in soup.title.get_text() or not soup.h1 or re.sub(r'\s', '', soup.h1.get_text()).upper() != 'TENETT7':
            raise NeedsReview('TENET T7 official model identity changed')
        links = {urljoin(page.url, a['href']) for a in soup.select('a[href]') if 'прайс-лист' in a.get_text(' ', strip=True).casefold()}
        if len(links) != 1:
            raise NeedsReview('T7 price document link ambiguous/missing')
        pdf = fetcher.get(links.pop())
        offers = self.parse_pdf(pdf, verified_at)
        cards = soup.select('.web_block_grades__card-content')
        html_prices = {}
        for card in cards:
            title, price = card.select_one('.web_block_grades__card-title'), card.select_one('.main-caps')
            if title is None or price is None:
                continue
            match = re.fullmatch(r'(Актив/Active|Прайм/Prime) (2WD|4WD), (20\d{2}) г\.в\.', title.get_text(' ', strip=True))
            if match:
                name = ('Active' if match[1].startswith('Актив') else 'Prime') + ' ' + match[2]
                html_prices[name] = (int(match[3]), parse_amount(price.get_text(' ', strip=True)))
        promo = [o for o in offers if o['price_kind'] == 'official_promotional_reference']
        if len(html_prices) != 4 or any(html_prices.get(o['trim']) != (o['production_year'], o['price_rub']) for o in promo):
            raise NeedsReview('T7 website/PDF year or price conflict; human review required')
        return offers, [page, pdf]

    def parse_pdf(self, document, verified_at):
        text = pdf_text(document.content)
        foot = re.search(r'\*Максимальная цена перепродажи с учетом маркетинговых акций\.(.*?)\*\*\*', text, re.S)
        dates = set(re.findall(r'Цена актуальна на (\d{2})\.(\d{2})\.(20\d{2})', text))
        if not foot or len(dates) != 1 or 'трейд-ин автомобилей с пробегом популярных марок' not in foot[0] or 'www.tenet.ru' not in foot[0]:
            raise NeedsReview('T7 price validity/marketing/trade-in footnotes changed')
        d, m, y = dates.pop()
        effective = f'{y}-{m}-{d}'
        with fitz.open(stream=document.content, filetype='pdf') as pdf:
            page = pdf[0]
            if abs(page.rect.width - 595.276) > 1 or pdf.page_count != 3:
                raise NeedsReview('T7 reviewed three-page A4 layout changed')
            words = page.get_text('words')
            def anchor(label):
                matches = [w for w in words if w[4] == label and w[0] < 180 and 170 < w[1] < 240]
                if len(matches) != 1:
                    raise NeedsReview(f'T7 row heading missing/ambiguous: {label}')
                return matches[0][1]
            top = anchor('Максимальная')
            rrp_y = anchor('Рекомендуемая')
            trade_y = anchor('Выгода')
            year_tokens = [w[4] for w in words if w[0] < 180 and top - 20 < w[1] < top - 5]
            if len(year_tokens) != 3 or year_tokens[1:] != ['ГОД', 'ВЫПУСКА'] or not re.fullmatch(r'20\d{2}', year_tokens[0]):
                raise NeedsReview('T7 production year heading changed')
            year = int(year_tokens[0])
            values = []
            for left, right, trim, drive in [(200, 285, 'Active', 'передний'), (285, 380, 'Prime', 'передний'), (380, 475, 'Active', 'полный'), (475, 570, 'Prime', 'полный')]:
                header = ' '.join(w[4] for w in sorted(words, key=lambda w: (round(w[1]), w[0])) if left < w[0] < right and top - 20 < w[1] < top - 4)
                if trim not in header or drive not in header:
                    raise NeedsReview('T7 column/drive header changed')
                def cell(row_y, minimum=300_000):
                    tokens = sorted([w for w in words if left < w[0] < right and abs(w[1] - row_y) < 5], key=lambda w: w[0])
                    raw = ' '.join(w[4] for w in tokens)
                    if not re.fullmatch(r'\d{1,3} \d{3}(?: \d{3})?', raw):
                        raise NeedsReview('T7 price cell structure changed')
                    amount = int(raw.replace(' ', ''))
                    if amount < minimum:
                        raise NeedsReview('T7 invalid amount')
                    return raw, amount
                promo_raw, promo = cell(top)
                rrp_raw, rrp = cell(rrp_y)
                discount_raw, discount = cell(trade_y, 1)
                if rrp - discount != promo:
                    raise NeedsReview('T7 RRP minus stated trade-in benefit does not equal promotion')
                values.append((trim + (' 2WD' if drive == 'передний' else ' 4WD'), promo_raw, rrp_raw, discount_raw))
        offers = []
        for trim, promo_raw, rrp_raw, discount_raw in values:
            conditions = f'Выгода по трейд-ин: {discount_raw} руб. ' + re.sub(r'\s+', ' ', foot[0]).strip()
            excerpt = f'TENET T7 | {year} ГОД ВЫПУСКА | {trim} | Максимальная цена перепродажи с учетом всех выгод: {promo_raw} | Рекомендуемая цена перепродажи: {rrp_raw} | {conditions}'
            for kind, raw, detail in [('official_promotional_reference', promo_raw, conditions), ('msrp', rrp_raw, f'Рекомендуемая цена перепродажи; цена актуальна на {d}.{m}.{y}. Не является публичной офертой. Подробности у официальных дилеров TENET.')]:
                offers.append(self.offer(document, verified_at, model_id='tenet-t7', raw_price=raw,
                                        trim=trim, production_year=year, effective_date=effective,
                                        price_kind=kind, price_basis='exact_trim', conditions=detail, excerpt=excerpt))
        return offers
