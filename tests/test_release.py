import pytest
from app.pipeline import compute


def late_files(arrived):
    rows = ['event,tag,flight,leg_hint,action,effective,received',
            'S1,000201,NX518,,SORT,2026-11-20T23:50:00+08:00,2026-11-20T23:50:00+08:00']
    if arrived:
        rows.append('S2,000201,NX518,,LOAD,2026-11-20T23:45:00+08:00,2026-11-21T00:12:00+08:00')
    return {
        'scans.csv': '\n'.join(rows) + '\n',
        'legs.csv': ('leg,flight,start,end,destination\n'
                     'NX-01,NX518,2026-11-20T23:00:00+08:00,2026-11-21T00:20:00+08:00,宁波\n'
                     'NX-02,NX518,2026-11-21T00:20:00+08:00,2026-11-21T02:00:00+08:00,宁波\n'),
        'manifest.csv': 'tag,planned\n000201,NX-01\n',
    }


@pytest.fixture
def released(dirty):
    return dirty['release']


def test_groups_cover_whole_manifest(released):
    assert sum(group['members'] for group in released['groups']) == 12


def test_dirty_conclusions(released):
    by_leg = {group['leg']: group for group in released['groups']}
    assert by_leg['NX-01']['conclusion'] == 'partial'
    assert by_leg['NX-01']['aboard'] == ['000101']
    assert [row['tag'] for row in by_leg['NX-01']['left']] == ['000109']
    assert by_leg['HX-41']['conclusion'] == 'held'
    assert by_leg['HX-42']['aboard'] == ['000110']
    assert [row['tag'] for row in by_leg['HX-42']['left']] == ['000104']


def test_receiver_prefers_following_leg(released):
    by_leg = {group['leg']: group for group in released['groups']}
    assert by_leg['NX-01']['receiver'] == dict(kind='leg', ref='NX-02', label='NX-02 接班航段')
    assert by_leg['NX-02']['receiver'] == dict(kind='station', ref='宁波', label='宁波 到达中转席')
    assert by_leg['HX-41']['receiver']['kind'] == 'station'


def test_orders_only_for_groups_with_leftovers(released):
    assert {order['leg'] for order in released['orders']} == {'NX-01', 'NX-02', 'HX-41', 'HX-42', 'JL-08'}
    assert all(order['count'] == len(order['tags']) for order in released['orders'])


def test_handover_count_matches_ledger(dirty):
    assert dirty['release']['counts']['handover'] == dirty['ledger']['counts']['handover'] == 9
    assert sum(row['handover'] for row in dirty['ledger']['rows']) == 9


def test_late_scan_rewrites_conclusion_and_handover():
    before = compute(late_files(arrived=False))
    group, = before['release']['groups']
    assert (group['conclusion'], group['handover']) == ('held', 1)
    assert before['ledger']['counts']['handover'] == 1

    after = compute(late_files(arrived=True))
    assert after['replay']['counts']['late'] == 1
    group, = after['release']['groups']
    assert (group['conclusion'], group['handover']) == ('full', 0)
    assert after['ledger']['counts']['handover'] == 0
    assert after['release']['orders'] == []


def test_orders_issued_once_per_run(desk, saved):
    first = desk.get(f"/api/release/{saved['id']}").json['rows']
    assert len(first) == saved['handovers'] > 0
    desk.post(f"/api/archive/{saved['id']}/rerun")
    again = desk.get(f"/api/release/{saved['id']}").json['rows']
    assert first == again


def test_recall_is_idempotent(desk, saved):
    recalled = desk.post(f"/api/release/{saved['id']}/recall").json
    assert recalled['recalled'] == saved['handovers']
    assert {row['status'] for row in recalled['rows']} == {'recalled'}
    assert desk.post(f"/api/release/{saved['id']}/recall").json['recalled'] == 0


def test_stale_orders_stay_recoverable_after_new_run(desk):
    stale = desk.post('/api/archive', json={'files': late_files(False)}).json
    assert desk.get(f"/api/release/{stale['id']}").json['rows'][0]['count'] == 1
    fresh = desk.post('/api/archive', json={'files': late_files(True)}).json
    assert desk.get(f"/api/release/{fresh['id']}").json['rows'] == []
    recalled = desk.post(f"/api/release/{stale['id']}/recall").json
    assert recalled['recalled'] == 1 and recalled['rows'][0]['status'] == 'recalled'


def test_unknown_run(desk):
    assert desk.get('/api/release/unknown').status_code == 404
    assert desk.post('/api/release/unknown/recall').json['code'] == 'NO_RUN'
