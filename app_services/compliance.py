"""Deterministic long-only equity-and-cash compliance calculations for the demo UI.

All policy limits here are invented client mandates; none are universal regulations.
Unreliable input always produces DATA_ISSUE rather than a clean PASS.
"""
from datetime import date
from collections import defaultdict

TOL = 1e-9


def evaluate(snapshot, rules, approved_exclusions=None):
    errors = []
    today = date.fromisoformat(snapshot['as_of'])
    totals = defaultdict(float)
    sectors = defaultdict(float)
    activities, issued, issuer_sectors = {}, {}, {}
    total = 0.0
    for p in snapshot['positions']:
        ticker = p.get('ticker')
        issuer = p.get('issuer') or ticker
        for required in ('ticker', 'issuer', 'sector', 'quantity', 'price', 'price_date'):
            if p.get(required) is None or p.get(required) == '':
                errors.append(f'{ticker or "?"}: missing {required}')
        q, price = p.get('quantity'), p.get('price')
        if q is None or price is None:
            continue
        if (isinstance(q, bool) or isinstance(price, bool) or
                not isinstance(q, (int, float)) or not isinstance(price, (int, float)) or
                q < 0 or price < 0):
            errors.append(f'{ticker}: invalid long-only quantity or price')
            continue
        try:
            age = (today - date.fromisoformat(p['price_date'])).days
            if age < 0 or age > 3:
                errors.append(f'{ticker}: price date not within 3 days of snapshot')
        except (KeyError, TypeError, ValueError):
            errors.append(f'{ticker}: missing/invalid price date')
        mv = q * price
        total += mv
        totals[issuer] += mv
        sectors[p.get('sector') or 'UNKNOWN'] += mv
        issued[ticker] = issuer
        if issuer in issuer_sectors and issuer_sectors[issuer] != p.get('sector'):
            errors.append(f'{issuer}: inconsistent sector across securities')
        issuer_sectors[issuer] = p.get('sector')
        activities[issuer] = p.get('business_activities')
    cash = snapshot.get('cash')
    if cash is None or isinstance(cash, bool) or not isinstance(cash, (int, float)) or cash < 0:
        errors.append('Missing or invalid cash amount')
        cash = 0
    nav = total + cash
    if nav <= 0:
        errors.append('Non-positive net asset value')
    exposures = {k: v / nav for k, v in totals.items()} if nav > 0 else {}
    sector_weights = {k: v / nav for k, v in sectors.items()} if nav > 0 else {}
    results = []
    for r in rules:
        bad = {}
        type_, threshold = r['type'], r['value']
        observed = ''
        description = ''
        if type_ == 'max_issuer_weight':
            bad = {k: w for k, w in exposures.items() if w > threshold + TOL}
            top = sorted(exposures.items(), key=lambda x: x[1], reverse=True)[:3]
            observed = ', '.join(f'{name}: {weight:.2%}' for name, weight in top)
            description = f'Every issuer must stay at or below {threshold:.1%} of NAV; securities of the same issuer are combined.'
        elif type_ == 'max_sector_weight':
            bad = {k: w for k, w in sector_weights.items() if w > threshold + TOL}
            top = sorted(sector_weights.items(), key=lambda x: x[1], reverse=True)[:3]
            observed = ', '.join(f'{name}: {weight:.2%}' for name, weight in top)
            description = f'Every sector must stay at or below {threshold:.1%} of NAV.'
        elif type_ == 'min_cash':
            cash_w = cash / nav if nav > 0 else 0.0
            if nav > 0 and cash_w < threshold - TOL:
                bad = {'cash': cash_w}
            observed = f'Cash: {cash_w:.2%}'
            description = f'Cash must be at least {threshold:.1%} of NAV.'
        elif type_ == 'prohibited_issuers':
            blocked = {str(x).upper() for x in threshold}
            bad = {t: exposures.get(issued[t], 0) for t in issued
                   if t.upper() in blocked or issued[t].upper() in blocked}
            observed = f'{len(bad)} prohibited holdings found'
            description = f'No positions in the blocked ticker/issuer list: {", ".join(threshold)}.'
        elif type_ == 'excluded_business_activities':
            blocked = {str(x).lower() for x in threshold}
            for issuer, acts in activities.items():
                if acts is None:
                    errors.append(f'{issuer}: business classification not verified')
                elif any(x.lower() in blocked for x in acts):
                    bad[issuer] = exposures.get(issuer, 0)
            observed = f'{len(bad)} excluded-activity issuers found'
            description = 'Business activity exclusions use separately verified issuer classifications, not LLM speculation.'
        elif type_ == 'max_top_n_issuers':
            n = threshold['n']
            cap = threshold['max_weight']
            top = sorted(exposures.items(), key=lambda x: x[1], reverse=True)[:n]
            combined = sum(w for _, w in top)
            if combined > cap + TOL:
                bad = {'top_n_total': combined}
            observed = f'Top {n} total: {combined:.2%}; members: ' + ', '.join(f'{k} {w:.2%}' for k, w in top)
            description = f'The {n} largest issuers combined cannot exceed {cap:.1%} of NAV; aggregate before ranking.'
        elif type_ == 'sector_specific_issuer_cap':
            default_cap = threshold['default']
            overrides = threshold['overrides']
            capped = []
            for issuer, w in exposures.items():
                sector = issuer_sectors.get(issuer)
                if not sector:
                    errors.append(f'{issuer}: sector required for issuer cap')
                    continue
                cap = overrides.get(sector, default_cap)
                if w > cap + TOL:
                    bad[issuer] = w
                capped.append((issuer, sector, w, cap))
            observed = '; '.join(f'{i} ({s}): {w:.2%} / {c:.1%}' for i, s, w, c in capped[:6])
            description = (f'Default issuer cap {default_cap:.1%}; sector exceptions: ' +
                           ', '.join(f'{s} {v:.1%}' for s, v in overrides.items()) + '.')
        else:
            errors.append(f'unsupported rule {type_}')
        # Preserve data-quality precedence, including errors discovered while checking business activities.
        status = 'DATA_ISSUE' if errors else 'FAIL' if bad else 'PASS'
        results.append({'rule_id': r['id'], 'type': type_, 'status': status,
                        'offenders': bad, 'source': r.get('clause_text', ''),
                        'data_issues': list(dict.fromkeys(errors)),
                        'observed': observed, 'explanation': description})
    if errors:
        for result in results:
            result['status'] = 'DATA_ISSUE'
            result['data_issues'] = list(dict.fromkeys(errors))
    return {'nav': nav, 'issuer_weights': exposures, 'sector_weights': sector_weights,
            'cash_weight': cash / nav if nav > 0 else None,
            'results': results, 'data_issues': list(dict.fromkeys(errors)),
            'overall': 'DATA_ISSUE' if errors else 'FLAGGED' if any(x['status'] == 'FAIL' for x in results) else 'COMPLIANT'}
