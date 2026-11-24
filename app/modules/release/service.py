CONCLUSIONS = {'full': '整组随行', 'partial': '部分放行', 'held': '整组留后'}


def receiver_for(leg, legs):
    followups = sorted(
        (other for other in legs
         if other['leg'] != leg['leg'] and other['flight'] == leg['flight'] and other['start'] >= leg['end']),
        key=lambda other: (other['start'], other['leg']),
    )
    if followups:
        return dict(kind='leg', ref=followups[0]['leg'], label=f"{followups[0]['leg']} 接班航段")
    return dict(kind='station', ref=leg['destination'], label=f"{leg['destination']} 到达中转席")


def conclude(decisions, legs):
    groups, orders = [], []
    for leg in sorted(legs, key=lambda item: item['leg']):
        rows = [row for row in decisions['rows'] if row['planned'] == leg['leg']]
        if not rows:
            continue
        aboard = sorted(row['tag'] for row in rows if row['status'] == 'loaded')
        left = [dict(tag=row['tag'], status=row['status'], reason=row['reason'])
                for row in sorted(rows, key=lambda row: row['tag'])
                if row['status'] in ('pending', 'not_loaded')]
        conclusion = 'full' if not left else 'held' if not aboard else 'partial'
        receiver = receiver_for(leg, legs)
        groups.append(dict(leg=leg['leg'], flight=leg['flight'], destination=leg['destination'],
                           members=len(rows), aboard=aboard, left=left, conclusion=conclusion,
                           receiver=receiver, handover=len(left)))
        if left:
            orders.append(dict(leg=leg['leg'], receiver=receiver['label'], receiver_kind=receiver['kind'],
                               tags=[row['tag'] for row in left], count=len(left)))
    counts = dict(groups=len(groups),
                  full=sum(group['conclusion'] == 'full' for group in groups),
                  partial=sum(group['conclusion'] == 'partial' for group in groups),
                  held=sum(group['conclusion'] == 'held' for group in groups),
                  handover=sum(group['handover'] for group in groups))
    return dict(groups=groups, orders=orders, counts=counts)
