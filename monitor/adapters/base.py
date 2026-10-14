import hashlib
from bs4 import BeautifulSoup
from ..common import extract_conditions, parse_amount


class NeedsReview(ValueError):
    pass


class Adapter:
    brand_id = ''

    def __init__(self, source):
        self.source = source

    def parse(self, document, verified_at):
        raise NotImplementedError

    def collect(self, fetcher, verified_at):
        document = fetcher.get(self.source['source_url'])
        return self.parse(document, verified_at), [document]

    def offer(self, document, verified_at, *, model_id, raw_price, trim, conditions,
              model_year=None, production_year=None, effective_date=None, valid_until=None,
              price_kind='official_promotional_reference', price_basis='starting_at', excerpt=None):
        evidence = excerpt or conditions
        return dict(brand_id=self.brand_id, model_id=model_id, model_year=model_year,
                    production_year=production_year, trim=trim, price_kind=price_kind,
                    price_rub=parse_amount(raw_price), raw_price=raw_price, conditions=conditions,
                    condition_labels=extract_conditions(conditions), region='俄罗斯；以官方经销商确认为准',
                    effective_date=effective_date, valid_until=valid_until, source_url=document.url,
                    source_type='official_pdf' if document.content.startswith(b'%PDF') else 'official_html',
                    verified_at=verified_at, status='verified', confidence=0.98,
                    evidence_excerpt=evidence, evidence_sha256=document.sha256, price_basis=price_basis)

    def discover(self, document, brand, heading_token, link_label):
        soup = BeautifulSoup(document.text, 'html.parser')
        title = soup.title.get_text(' ', strip=True) if soup.title else ''
        if brand.casefold() not in title.casefold() or heading_token.casefold() not in soup.get_text(' ', strip=True).casefold():
            raise NeedsReview('Official document identity/heading changed')
        links = [a.get('href') for a in soup.select('a[href]') if link_label.casefold() in a.get_text(' ', strip=True).casefold()]
        raise NeedsReview(f'Official page reachable; {len(set(links))} candidate price documents; year/trim/conditions parser pending review')
