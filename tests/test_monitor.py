import copy
import hashlib
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
import httpx
import pytest
import jsonschema
from monitor.adapters import ADAPTERS
from monitor.adapters.base import NeedsReview
from monitor.adapters.haval import HavalAdapter
from monitor.adapters.tenet import TenetAdapter
from monitor.collect import collect
from monitor.common import ROOT, active_status, comparison_key, extract_conditions, parse_amount, read_json, timestamp, write_json
from monitor.import_prices import import_prices
from monitor.pdf import pdf_text
from monitor.publish import publish
from monitor.state import current_view, empty_state, merge_brand
from monitor.transport import Document, Fetcher
from monitor.validation import validate_offer

FIXTURES = Path(__file__).parent / 'fixtures'
SOURCES = read_json(ROOT / 'data/sources.json')


def document(name, bid):
    url = next(s['source_url'] for s in SOURCES if s['brand_id'] == bid)
    return Document(url, (FIXTURES / name).read_bytes(), 'text/html')


@pytest.fixture
def offer():
    source = next(s for s in SOURCES if s['brand_id'] == 'haval')
    return HavalAdapter(source).parse(document('haval-h3.html', 'haval'), timestamp())[0]


@pytest.fixture
def temp_project(tmp_path):
    shutil.copytree(ROOT / 'data', tmp_path / 'data')
    write_json(tmp_path / 'data/state.json', empty_state())
    return tmp_path


@pytest.mark.parametrize('raw, expected', [('2 549 000 ₽',2549000),('от 2\u00a0549\u00a0000 ₽*',2549000),('2\u202f625\u202f000',2625000),('2 805 000,00 руб.',2805000),('2549000',2549000)])
def test_whole_rub_amount(raw, expected):
    assert parse_amount(raw) == expected


@pytest.mark.parametrize('raw', ['18 500,02 руб.', '200 000 ₽', '0', '2 599 000 — 3 000 000 ₽', 'от 0,01%', 'кредит 2 549 000 ₽', '2549000 ₽ скидка'])
def test_reject_payment_discount_and_ambiguous_amount(raw):
    with pytest.raises(ValueError):
        parse_amount(raw)


def test_haval_fixture_identity_price_conditions(offer):
    assert offer['model_id'] == 'haval-h3'
    assert offer['model_year'] == offer['production_year'] == 2026
    assert offer['price_rub'] == 2549000
    assert 'HAVAL или Great Wall' in offer['conditions']
    assert '3 (три)' in offer['conditions']
    assert '置换 / Trade-in' in offer['condition_labels']
    assert offer['price_basis'] == 'starting_at'
    validate_offer(offer)


def test_conditions_labels_never_claim_unconditional():
    assert extract_conditions('Трейд-ин и кредит. Не является офертой.') == ['置换 / Trade-in','贷款','非合同报价']


@pytest.mark.parametrize('mutation', ['delete_price','wrong_model','missing_conditions','conflicting_duplicates'])
def test_haval_structure_changes_fail_closed(mutation):
    doc = document('haval-h3.html','haval')
    html = doc.text
    if mutation == 'delete_price': html = html.replace('web_block_models__item-price','unknown-price')
    if mutation == 'wrong_model': html = html.replace('>H3<','>H9<')
    if mutation == 'missing_conditions': html = html.replace('3 (три)','несколько')
    if mutation == 'conflicting_duplicates': html += html.replace('2 549 000','2 599 000')
    doc.content = html.encode()
    with pytest.raises(NeedsReview): HavalAdapter(SOURCES[1]).parse(doc,timestamp())


class FixtureFetcher:
    def __init__(self, *args): pass
    def get(self, url):
        if url.startswith('https://tenet.ru'):
            return document('tenet-t7.html','tenet')
        return Document(url,(FIXTURES/'tenet-t7.pdf').read_bytes(),'application/pdf')
    def close(self): pass


def test_tenet_official_pdf_and_html_agree():
    adapter = TenetAdapter(next(s for s in SOURCES if s['brand_id']=='tenet'))
    offers, documents = adapter.collect(FixtureFetcher(),timestamp())
    assert len(offers) == 8
    assert [o['price_rub'] for o in offers if o['price_kind']=='official_promotional_reference'] == [2625000,2805000,2880000,3060000]
    assert [o['price_rub'] for o in offers if o['price_kind']=='msrp'] == [2805000,3005000,3010000,3210000]
    assert all(o['production_year']==2026 and o['model_year'] is None for o in offers)
    for o in offers: validate_offer(o)


def test_tenet_html_pdf_conflict_rejected():
    class ConflictFetcher(FixtureFetcher):
        def get(self,url):
            doc=super().get(url)
            if url.startswith('https://tenet.ru'): doc.content=doc.content.replace(b'2 625 000',b'2 605 000')
            return doc
    with pytest.raises(NeedsReview,match='conflict'):
        TenetAdapter(next(s for s in SOURCES if s['brand_id']=='tenet')).collect(ConflictFetcher(),timestamp())


@pytest.mark.parametrize('bid,title,token', [('geely','Geely official','Monjaro'),('changan','Changan official','CS75'),('hongqi','Hongqi official','HS3')])
def test_unreviewed_brand_adapters_never_extract_ad_prices(bid,title,token):
    doc=Document(next(s['source_url'] for s in SOURCES if s['brand_id']==bid),f'<title>{title}</title><h1>{token}</h1><p>от 2 000 000 ₽</p>'.encode(),'text/html')
    with pytest.raises(NeedsReview): ADAPTERS[bid](next(s for s in SOURCES if s['brand_id']==bid)).parse(doc,timestamp())


def test_pdf_invalid_type_rejected():
    with pytest.raises(ValueError): pdf_text(b'<html>challenge</html>')


def test_comparable_price_delta(offer):
    first=merge_brand(empty_state(),'haval',[offer],timestamp())
    changed=copy.deepcopy(offer);changed['price_rub']+=50000;changed['raw_price']='2 599 000 ₽'
    second=merge_brand(first,'haval',[changed],timestamp())
    event=second['changes'][-1]
    assert event['kind']=='price_change' and event['delta_rub']==50000
    assert event['delta_percent']==round(50000/2549000*100,4)


@pytest.mark.parametrize('field,value',[('trim','Changed configuration'),('production_year',2025),('model_year',2025),('conditions','Другие условия трейд-ин'),('region','Москва'),('effective_date','2026-01-01'),('valid_until','2026-12-31'),('price_basis','exact_trim')])
def test_scope_change_never_computes_delta(offer,field,value):
    first=merge_brand(empty_state(),'haval',[offer],timestamp())
    changed=copy.deepcopy(offer);changed[field]=value;changed['price_rub']+=10000
    event=merge_brand(first,'haval',[changed],timestamp())['changes'][-1]
    assert event['kind']=='scope_change'
    assert event['delta_rub'] is event['delta_percent'] is None


def test_failed_collection_preserves_original_amount_and_time(temp_project,offer):
    state=merge_brand(empty_state(),'haval',[offer],timestamp())
    write_json(temp_project/'data/state.json',state)
    class Blocked:
        def __init__(self,*args):pass
        def get(self,url):raise httpx.HTTPStatusError('HTTP 403',request=httpx.Request('GET',url),response=httpx.Response(403))
        def close(self):pass
    result=collect(temp_project,brands=['haval'],fetcher_factory=Blocked)
    retained=result['offers'][0]
    assert retained['price_rub']==offer['price_rub']
    assert retained['verified_at']==offer['verified_at']
    assert retained['last_success_at']==offer['verified_at']
    assert retained['status']=='stale' and '403' in retained['failure_reason']
    assert len(result['observations'])==len(state['observations'])
    view=read_json(temp_project/'public/data/current.json')
    assert next(m for m in view['models'] if m['model_id']=='haval-h3')['promo']['min_rub'] is None


def test_partial_brand_missing_trim_preserved_stale(offer):
    second=copy.deepcopy(offer);second['trim']='Other reviewed trim'
    state=merge_brand(empty_state(),'haval',[offer,second],timestamp())
    state=merge_brand(state,'haval',[offer],timestamp())
    assert len(state['offers'])==2
    assert next(o for o in state['offers'] if o['trim']==second['trim'])['status']=='stale'


def test_no_fabricated_upper_bound_for_starting_price(offer):
    state=merge_brand(empty_state(),'haval',[offer],timestamp())
    model=next(m for m in current_view(state,read_json(ROOT/'data/catalog.json')) if m['model_id']=='haval-h3')
    assert model['promo']['min_rub']==2549000 and model['promo']['max_rub'] is None
    assert model['msrp']['min_rub'] is None


def test_unchanged_observation_same_day_deduplicated(offer):
    state=merge_brand(empty_state(),'haval',[offer],timestamp())
    twice=merge_brand(state,'haval',[offer],timestamp())
    assert len(twice['observations'])==1 and len(twice['changes'])==1


def test_different_days_accumulate_flat_history(offer):
    yesterday=(datetime.now(timezone.utc)-timedelta(days=1)).isoformat()
    state=merge_brand(empty_state(),'haval',[offer],yesterday)
    state=merge_brand(state,'haval',[offer],timestamp())
    assert len(state['observations'])==2 and len(state['changes'])==1


@pytest.mark.parametrize('field,value',[('price_rub',0),('price_rub',2549001),('source_url','https://dealer.example.com/price'),('source_url','http://haval.ru/price'),('model_id','haval-poer'),('brand_id','geely'),('price_kind','verified_transaction'),('production_year',None)])
def test_validation_rejects_bad_or_mismatched_evidence(offer,field,value):
    offer[field]=value
    if field=='production_year':offer['model_year']=None
    with pytest.raises((ValueError,jsonschema.ValidationError)):
        validate_offer(offer)


def test_expiry_and_age_hide_default_price(offer):
    state=merge_brand(empty_state(),'haval',[offer],timestamp())
    view=current_view(state,read_json(ROOT/'data/catalog.json'),datetime.now(timezone.utc)+timedelta(days=4))
    model=next(m for m in view if m['model_id']=='haval-h3')
    assert model['status']=='stale' and model['promo']['min_rub'] is None
    offer['valid_until']=(datetime.now(timezone.utc)-timedelta(days=1)).date().isoformat()
    with pytest.raises(ValueError,match='Expired'):validate_offer(offer)


def test_official_validity_uses_moscow_midnight(offer):
    offer['verified_at']='2026-10-14T12:00:00Z'
    offer['valid_until']='2026-10-14'
    assert active_status(offer,datetime.fromisoformat('2026-10-14T20:59:00+00:00'))=='verified'
    assert active_status(offer,datetime.fromisoformat('2026-10-14T21:00:00+00:00'))=='expired'


def test_brand_failure_does_not_stop_others(temp_project):
    class MixedFetcher(FixtureFetcher):
        def get(self,url):
            if 'haval.ru' in url:raise httpx.ReadTimeout('timeout')
            return super().get(url)
    state=collect(temp_project,brands=['haval','tenet'],fetcher_factory=MixedFetcher)
    assert any(o['brand_id']=='tenet' for o in state['offers'])
    assert [r['status'] for r in state['runs']]==['failed','partial_success']


def test_manual_import_requires_attestation_and_audits_source(temp_project,offer):
    file=temp_project/'manual.json';evidence=FIXTURES/'haval-h3.html'
    write_json(file,[offer])
    with pytest.raises(ValueError,match='reviewer'):import_prices(file,evidence,'',False,temp_project)
    import_prices(file,evidence,'Offline test reviewer',True,temp_project)
    state=read_json(temp_project/'data/state.json')
    assert state['offers'][0]['source_type']=='manual_verified'
    assert state['offers'][0]['verified_at']==offer['verified_at']
    assert state['runs'][-1]['reviewer']=='Offline test reviewer'


def test_invalid_manual_import_is_transactional(temp_project,offer):
    file=temp_project/'manual.json';bad=copy.deepcopy(offer);bad['price_rub']=0
    write_json(file,[offer,bad]);before=(temp_project/'data/state.json').read_bytes()
    with pytest.raises(jsonschema.ValidationError):import_prices(file,FIXTURES/'haval-h3.html','Test reviewer',True,temp_project)
    assert (temp_project/'data/state.json').read_bytes()==before


def test_http_403_not_retried_and_robots_blocked(monkeypatch):
    monkeypatch.setattr('monitor.transport.time.sleep',lambda _:None)
    calls=[]
    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200,text='User-agent: *\nAllow: /') if request.url.path=='/robots.txt' else httpx.Response(403,text='Forbidden')
    fetcher=Fetcher(['haval.ru'],httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(httpx.HTTPStatusError):fetcher.get('https://haval.ru/purchase/catalogues/')
    assert len(calls)==2
    blocked=Fetcher(['haval.ru'],httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,text='User-agent: *\nDisallow: /'))))
    with pytest.raises(ValueError,match='disallows'):blocked.get('https://haval.ru/purchase/catalogues/')


def test_redirect_outside_allowlist_rejected(monkeypatch):
    monkeypatch.setattr('monitor.transport.time.sleep',lambda _:None)
    def handler(request):
        return httpx.Response(200,text='User-agent: *\nAllow: /') if request.url.path=='/robots.txt' else httpx.Response(302,headers={'Location':'https://evil.example/price'})
    fetcher=Fetcher(['haval.ru'],httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(ValueError,match='unsafe'):fetcher.get('https://haval.ru/price')


def test_timeout_retries_are_bounded(monkeypatch):
    monkeypatch.setattr('monitor.transport.time.sleep',lambda _:None)
    calls=[]
    def handler(request):calls.append(request.url);raise httpx.ReadTimeout('timeout')
    f=Fetcher(['haval.ru'],httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(httpx.ReadTimeout):f.get('https://haval.ru/price')
    assert len(calls)==3


def test_catalog_scope_and_public_schema(temp_project):
    publish(temp_project)
    current=read_json(temp_project/'public/data/current.json')
    assert len(current['brands'])==5 and len(current['models'])==39
    assert all(m['promo']['min_rub'] is None and m['msrp']['min_rub'] is None for m in current['models'])
    assert all(m['body_type'] not in ['pickup','commercial'] for m in current['models'])
    assert not any(m['brand_id'] in ['chery','avatr','deepal','uni'] for m in current['models'])
