"""เอนจินห้องเล่นแบบ Manual ของ Date Destiny TCG (เก็บสถานะในหน่วยความจำ)
เซิร์ฟเวอร์เป็นผู้ถือสถานะจริง และซ่อนข้อมูลที่อีกฝ่ายไม่ควรเห็น (มือ/เด็ค/HP คว่ำ) ก่อนส่งให้ client
"""
import random
import time
from threading import RLock

LOCK = RLock()
ROOMS = {}
ZONES = ('deck', 'hand', 'attack', 'protect', 'partners', 'server', 'hp', 'delect')
LIMITS = {'attack': 4, 'protect': 3}
MAX_CODE = 10
COUNTER_DAMAGE = True     # แบบ Hearthstone: เป้าหมายสวนกลับด้วยค่า ATK ของตัวเอง (ตั้งเป็น False ถ้าไม่ต้องการให้สวนกลับ)
NEUROUS = ('entity', 'partners')
LINK_MAX = 3              # Ship ที่ Link เข้ากับ Neurous หนึ่งใบได้ไม่เกิน 3 ใบ
DICE_TURNS = (3, 5, 7, 9) # เทิร์นที่ n ของผู้เล่นแต่ละคน ที่ได้ทอยลูกเต๋า D4 เป็นโค้ดโบนัส
DICE_SIDES = 4
HP_START = 8
HAND_START = 4
Z_TH = {'deck': 'Deck', 'hand': 'มือ', 'attack': 'Attack Zone', 'protect': 'Protect Zone',
        'partners': 'Partners Zone', 'server': 'Server Zone', 'hp': 'Firewall Zone (HP)',
        'delect': 'Delect Zone'}


def _log(room, who, text, kind='sys'):
    room['log'].append({'t': int(time.time()), 'who': who, 'text': text, 'k': kind})
    del room['log'][:-200]


def create_room(code, name, host_uid, solo=False):
    room = dict(code=code, name=name, host=host_uid, solo=solo, created=time.time(), players=[],
                spectators={}, cards={}, log=[], seq=0, state=None)
    ROOMS[code] = room
    return room


def seat(room, uid):
    return next((p for p in room['players'] if p['uid'] == uid), None)


def other(room, uid):
    return next((p for p in room['players'] if p['uid'] != uid), None)


def _inst(room, cid):
    room['seq'] += 1
    return {'iid': room['seq'], 'cid': int(cid), 'up': False, 'tap': False, 'ctr': 0, 'dmg': 0, 'links': []}


def _new_state():
    return {'first': None, 'turn': None, 'phase': 'setup', 'turn_no': 0, 'combat_no': 1,
            'acts': [], 'attacked': [], 'roll': None, 'roll_seq': 0, 'winner': None, 'p': {}}


def _build(room, p):
    """สร้างการ์ดทุกใบของผู้เล่นตามเด็คที่เลือก"""
    deck = p['deck']
    main = []
    for cid, q in deck['main'].items():
        main += [_inst(room, cid) for _ in range(q)]
    random.shuffle(main)
    z = {k: [] for k in ZONES}
    z['deck'] = main
    room['state']['p'][p['uid']] = {
        'z': z, 'code': 0, 'turns': 0,
        'pre_partners': [_inst(room, c) for c in deck['partners']],
        'setup': {'placed': False, 'drew': False, 'mull': False, 'hp': False, 'ready': False},
    }


def add_player(room, uid, name, avatar, deck, cards):
    room['cards'].update({str(k): v for k, v in cards.items()})
    p = dict(uid=uid, name=name, avatar=avatar, sid=None, online=True, deck=deck, sleeve=deck.get('sleeve', ''))
    room['players'].append(p)
    if room['state'] is None:
        room['state'] = _new_state()
    _build(room, p)
    _log(room, name, 'เข้าร่วมห้อง')
    return p


def reset(room):
    room['state'] = _new_state()
    room['seq'] = 0
    for p in room['players']:
        _build(room, p)
    _log(room, 'ระบบ', 'รีเซ็ตเกมใหม่ เริ่ม Setup อีกครั้ง')


def list_rooms():
    now = time.time()
    for k in [k for k, r in ROOMS.items() if now - r['created'] > 6 * 3600
              or (not any(p['online'] for p in r['players']) and now - r['created'] > 600)]:
        ROOMS.pop(k, None)
    return [dict(code=r['code'], name=r['name'], host=(r['players'][0]['name'] if r['players'] else '-'),
                 players=len(r['players']), started=bool(r['state'] and r['state']['phase'] != 'setup'))
            for r in ROOMS.values() if not r.get('solo')]


# ---------- มุมมองตามผู้ชม (ซ่อนข้อมูล) ----------
def _vis(c, zone, owner):
    if zone == 'deck':
        return {'iid': c['iid'], 'h': 1}
    if owner or c['up']:
        return dict(c)
    return {'iid': c['iid'], 'h': 1, 'tap': c['tap']}


def view(room, viewer):
    s = room['state']
    reveal = bool(room.get('solo')) and viewer == room['host']      # ห้องทดสอบ: เจ้าของห้องเห็นทุกฝั่ง
    out = dict(code=room['code'], name=room['name'], host=room['host'], solo=bool(room.get('solo')), rules={'counter': COUNTER_DAMAGE}, cards=room['cards'],
               players=[{k: p[k] for k in ('uid', 'name', 'avatar', 'online', 'sleeve')} for p in room['players']],
               log=room['log'][-80:], spectators=len(room['spectators']), state=None)
    if s:
        st = {k: s[k] for k in ('first', 'turn', 'phase', 'turn_no', 'combat_no', 'acts', 'attacked', 'roll', 'winner')}
        st['p'] = {}
        for uid, p in s['p'].items():
            owner = uid == viewer or reveal
            zs = {zn: ([_vis(c, zn, owner) for c in lst] if zn != 'deck' else len(lst))
                  for zn, lst in p['z'].items()}
            st['p'][uid] = {'z': zs, 'code': p['code'], 'turns': p['turns'], 'setup': p['setup']}
        out['state'] = st
    return out


def _hit(room, victim_uid, n, by_uid):
    """ลด HP ของ victim ลง n ใบ (ไปกอง Delect) ถ้า HP หมดแล้วยังโดนอีก = by_uid ชนะ"""
    s = room['state']
    z = s['p'][victim_uid]['z']
    for _ in range(n):
        if z['hp']:
            c = z['hp'].pop(0)
            c['up'] = True
            z['delect'].append(c)
        else:
            s['winner'] = by_uid
            _log(room, 'ระบบ', f"{seat(room, victim_uid)['name']} ไม่มี HP เหลือ → {seat(room, by_uid)['name']} ชนะ!")
            return
    _log(room, 'ระบบ', f"HP ของ {seat(room, victim_uid)['name']} เหลือ {len(z['hp'])}")


def _eff(room, c):
    """ค่าพลังจริงของ Neurous = ค่าพื้นฐาน + ผลรวมค่า Link ของ Ship ที่ลิงก์อยู่"""
    info = room['cards'].get(str(c['cid']), {})
    a, k, d = info.get('atk', 0), info.get('crit', 0), info.get('def', 0)
    for ln in c.get('links', []):
        li = room['cards'].get(str(ln['cid']), {})
        a += li.get('link_atk', 0)
        k += li.get('link_crit', 0)
        d += li.get('link_def', 0)
    return {'atk': max(0, a), 'crit': max(0, k), 'def': d}


def _drop_links(z, c):
    """Neurous ออกจากสนาม → Ship ที่ลิงก์อยู่ทั้งหมดลง Delect Zone"""
    for ln in c.get('links', []):
        ln['up'], ln['tap'] = True, False
        z['delect'].append(ln)
    c['links'] = []


def find(me, iid):
    for zn, lst in me['z'].items():
        for i, c in enumerate(lst):
            if c['iid'] == iid:
                return zn, i, c
    return None, None, None


def _draw_n(me, n):
    got = 0
    for _ in range(n):
        if not me['z']['deck']:
            break
        c = me['z']['deck'].pop(0)
        c['up'] = False
        c['tap'] = False
        me['z']['hand'].append(c)
        got += 1
    return got


def _cname(room, c):
    return room['cards'].get(str(c['cid']), {}).get('name', '?')


# ---------- การกระทำของผู้เล่น ----------
def act(room, uid, d):
    """คืนค่า (error, extra)"""
    s = room['state']
    if not s or uid not in s['p']:
        return 'คุณไม่ได้เป็นผู้เล่นในห้องนี้', None
    t = d.get('type')
    me = s['p'][uid]
    z = me['z']
    pl = seat(room, uid)
    opp = other(room, uid)
    name = pl['name']
    my_turn = s['turn'] == uid

    def L(text):
        _log(room, name, text)

    if t == 'chat':
        text = str(d.get('text', '')).strip()[:300]
        if text:
            _log(room, name, text, 'chat')
        return None, None
    if t == 'reset':
        if uid != room['host'] and not (room.get('solo') and uid == -room['host']):
            return 'เฉพาะเจ้าของห้องเท่านั้นที่รีเซ็ตได้', None
        reset(room)
        return None, None
    if t == 'solo_setup':
        if not room.get('solo') or s['phase'] != 'setup':
            return 'ใช้ได้เฉพาะห้องทดสอบก่อนเริ่มเกม', None
        s['first'] = room['host']
        for p in room['players']:
            for step in ('place', 'setup_draw', 'setup_hp'):
                act(room, p['uid'], {'type': step})
        for p in room['players']:
            act(room, p['uid'], {'type': 'ready'})
        return None, None
    if s['winner'] is not None:
        return 'เกมจบแล้ว (เจ้าของห้องกดรีเซ็ตเพื่อเล่นใหม่)', None

    # ----- Setup -----
    if t == 'first':
        if s['phase'] != 'setup':
            return 'เริ่มเกมไปแล้ว', None
        if not opp:
            return 'ต้องรอผู้เล่นอีกคนก่อน', None
        who = d.get('who', 'random')
        s['first'] = random.choice([uid, opp['uid']]) if who == 'random' else (uid if who == 'me' else opp['uid'])
        L(f"กำหนดผู้เริ่มเล่น: {seat(room, s['first'])['name']}")
        return None, None
    su = me['setup']
    if t == 'place':
        if su['placed']:
            return 'วางไปแล้ว', None
        z['partners'] = me['pre_partners']
        for c in z['partners']:
            c['up'] = True
        me['pre_partners'] = []
        random.shuffle(z['deck'])
        su['placed'] = True
        L('วาง Partners 4 ใบลง Partners Zone และสับเด็คแล้ว')
        return None, None
    if t == 'setup_draw':
        if not su['placed'] or su['drew']:
            return 'ต้องวางการ์ดก่อน (หรือจั่วไปแล้ว)', None
        _draw_n(me, HAND_START)
        su['drew'] = True
        L(f'จั่วการ์ด {HAND_START} ใบขึ้นมือ')
        return None, None
    if t == 'mulligan':
        if not su['drew'] or su['mull'] or su['hp']:
            return 'เปลี่ยนมือได้ 1 ครั้ง และต้องทำก่อนวาง HP', None
        n = len(z['hand'])
        z['deck'] += z['hand']
        z['hand'] = []
        random.shuffle(z['deck'])
        _draw_n(me, n)
        su['mull'] = True
        L(f'เปลี่ยนการ์ดบนมือ ({n} ใบ)')
        return None, None
    if t == 'setup_hp':
        if not su['drew'] or su['hp']:
            return 'ต้องจั่วมือก่อน (หรือวาง HP ไปแล้ว)', None
        for _ in range(HP_START):
            if z['deck']:
                c = z['deck'].pop(0)
                c['up'] = False
                z['hp'].append(c)
        su['hp'] = True
        L(f'วางการ์ด {HP_START} ใบลง HP คว่ำหน้า')
        return None, None
    if t == 'ready':
        if not (su['placed'] and su['drew'] and su['hp']):
            return 'ทำขั้นตอน Setup ให้ครบก่อน', None
        if not s['first']:
            return 'ยังไม่ได้กำหนดผู้เริ่มเล่น', None
        su['ready'] = True
        L('พร้อมแล้ว')
        if opp and s['p'][opp['uid']]['setup']['ready']:
            s['phase'], s['turn'], s['turn_no'] = 'generate', s['first'], 1
            s['p'][s['first']]['turns'] = 1
            _log(room, 'ระบบ', f"เริ่มเกม! เทิร์นของ {seat(room, s['first'])['name']}")
        return None, None

    # ----- ลำดับเทิร์น -----
    if t in ('generate', 'phase', 'combat_act', 'undo_act', 'add_combat', 'end_turn', 'attack'):
        if s['phase'] == 'setup':
            return 'ยังอยู่ในขั้น Setup', None
        if not my_turn:
            return 'ไม่ใช่เทิร์นของคุณ', None
    if t == 'generate':          # Generate: จั่วการ์ด 1 ใบ และได้รับ 2 Code ทันที (เทิร์น 3/5/7/9 ทอย D4 เป็นโบนัส)
        if s['phase'] != 'generate':
            return 'ไม่ได้อยู่ใน Generate Phase', None
        got = _draw_n(me, 1)
        me['code'] = min(MAX_CODE, me['code'] + 2)
        msg = ('Generate: จั่วการ์ด 1 ใบ' if got else 'Generate: เด็คหมด จั่วไม่ได้') + ' และได้ 2 Code'
        if me['turns'] in DICE_TURNS:
            v = random.randint(1, DICE_SIDES)
            s['roll_seq'] += 1
            s['roll'] = {'id': s['roll_seq'], 'uid': uid, 'v': v, 'turn': me['turns'], 'ts': int(time.time() * 1000)}
            me['code'] = min(MAX_CODE, me['code'] + v)
            msg += f' · ทอยลูกเต๋า D4 ได้ {v} → โบนัส +{v} Code'
        L(msg + f' (รวม {me["code"]})')
        s['phase'] = 'combat'
        return None, None
    if t == 'phase':
        to = d.get('to')
        if to not in ('generate', 'combat'):
            return 'เฟสไม่ถูกต้อง', None
        s['phase'] = to
        L(f'ข้ามไปยัง {to.capitalize()} Phase (manual)')
        return None, None
    if t == 'combat_act':
        a = d.get('name')
        if s['phase'] != 'combat' or a not in ('summon', 'combat', 'move'):
            return 'ใช้ได้เฉพาะใน Combat Phase', None
        if len(s['acts']) >= s['combat_no']:
            return 'เฟสนี้ใช้แอคชันไปแล้ว (เพิ่ม Combat Phase ได้สูงสุด 2)', None
        s['acts'].append(a)
        L(f'Combat Phase {s["combat_no"]}: เลือก {a.capitalize()}')
        return None, None
    if t == 'undo_act':
        if s['acts']:
            s['acts'].pop()
        return None, None
    if t == 'add_combat':
        if s['combat_no'] >= 2:
            return 'Combat Phase มีได้สูงสุด 2 เฟส', None
        s['combat_no'] += 1
        s['attacked'] = []
        L('เพิ่ม Combat Phase (2/2)')
        return None, None
    if t == 'end_turn':
        s['turn'] = opp['uid'] if opp else uid
        s['phase'], s['combat_no'], s['acts'], s['attacked'] = 'generate', 1, [], []
        s['p'][s['turn']]['turns'] += 1
        if opp:                                        # เริ่มเทิร์นใหม่: ตั้งการ์ดของผู้เล่นที่ได้เล่นให้ตรง
            for lst in s['p'][opp['uid']]['z'].values():
                for c in lst:
                    c['tap'] = False
        s['turn_no'] += 1
        _log(room, 'ระบบ', f"จบเทิร์น → เทิร์นของ {seat(room, s['turn'])['name']}")
        return None, None

    if t == 'attack':
        if s['phase'] != 'combat' or 'combat' not in s['acts']:
            return 'ต้องเลือก Combat ใน Combat Phase ก่อน', None
        if not opp:
            return 'ไม่มีคู่ต่อสู้', None
        ac = azone = None                     # ผู้โจมตี: Neurous ใบไหนก็ได้บนสนามเรา (Attack หรือ Protect Zone)
        for zn in ('attack', 'protect'):
            ac = next((c for c in z[zn] if c['iid'] == d.get('iid')), None)
            if ac:
                azone = zn
                break
        if not ac:
            return 'ผู้โจมตีต้องอยู่ใน Attack Zone หรือ Protect Zone ของคุณ', None
        ai = room['cards'].get(str(ac['cid']), {})
        if ai.get('type') not in NEUROUS:
            return 'การ์ดใบนี้โจมตีไม่ได้', None
        if ac['iid'] in s['attacked']:
            return 'ใบนี้โจมตีไปแล้วใน Combat Phase นี้', None
        ba = max(-9999, min(9999, int(d.get('atk_bonus', 0) or 0)))
        bd = max(-9999, min(9999, int(d.get('def_bonus', 0) or 0)))
        oz = s['p'][opp['uid']]['z']
        ae = _eff(room, ac)
        atk = ae['atk'] + ba
        an = ai.get('name', '?')
        if d.get('target') == 'player':
            if oz['protect']:
                return 'ต้องทำให้ Protect Zone ของฝั่งตรงข้ามว่างก่อนจึงโจมตีผู้เล่นได้', None
            dmg = max(1, ae['crit'])
            s['attacked'].append(ac['iid'])
            ac['tap'], ac['up'] = True, True
            L(f"{an} โจมตี {opp['name']} โดยตรง (CRIT {ae['crit']}) → HP −{dmg}")
            _hit(room, opp['uid'], dmg, uid)
            return None, None
        tc = tzone = None                     # เป้าหมาย: การ์ดใบไหนก็ได้บนสนามฝั่งตรงข้าม
        for zn in ('protect', 'attack'):
            tc = next((c for c in oz[zn] if c['iid'] == d.get('target')), None)
            if tc:
                tzone = zn
                break
        if not tc:
            return 'เลือกเป้าหมายจากการ์ดบนสนามของฝั่งตรงข้าม', None
        ti = room['cards'].get(str(tc['cid']), {})
        if ti.get('type') not in NEUROUS:
            return 'เป้าหมายนี้โจมตีไม่ได้', None
        te = _eff(room, tc)
        full = te['def'] + bd                              # DEF ทั้งหมดของเป้าหมาย (รวม Link และโบนัส)
        s['attacked'].append(ac['iid'])
        ac['tap'], ac['up'], tc['up'] = True, True, True
        before = full - tc['dmg']
        tc['dmg'] += max(0, atk)                           # ดาเมจสะสมแบบ Hearthstone
        after = full - tc['dmg']
        tn = ti.get('name', '?')
        msg = f"{an} (ATK {atk}) โจมตี {tn} (DEF {before}) → DEF เหลือ {max(after, 0)}"
        dead_t, dead_a = after <= 0, False
        if COUNTER_DAMAGE:
            back = te['atk']
            ac['dmg'] += back
            a_after = ae['def'] - ac['dmg']
            msg += f" · {tn} สวนกลับ {back} → DEF ของ {an} เหลือ {max(a_after, 0)}"
            dead_a = a_after <= 0
        if dead_t:
            oz[tzone].remove(tc)
            tc['tap'], tc['dmg'] = False, 0
            _drop_links(oz, tc)
            oz['delect'].append(tc)
            msg += f" · {tn} ถูกทำลาย"
        if dead_a:
            z[azone].remove(ac)
            ac['tap'], ac['dmg'] = False, 0
            _drop_links(z, ac)
            z['delect'].append(ac)
            msg += f" · {an} ถูกทำลาย"
        L(msg)
        return None, None

    # ----- แอคชันอิสระ (manual) -----
    if t == 'draw':
        n = max(1, min(10, int(d.get('n', 1))))
        got = _draw_n(me, n)
        L(f'จั่วการ์ด {got} ใบ')
        return None, None
    if t == 'shuffle':
        random.shuffle(z['deck'])
        L('สับเด็ค')
        return None, None
    if t == 'peek':
        n = int(d.get('n', 0)) or len(z['deck'])
        return None, [{'iid': c['iid'], 'cid': c['cid']} for c in z['deck'][:n]]
    if t == 'code':
        v = me['code'] + int(d['delta']) if 'delta' in d else int(d.get('set', 0))
        me['code'] = max(0, min(MAX_CODE, v))
        return None, None
    if t == 'hp_hit':
        n = max(1, min(10, int(d.get('n', 1))))
        for _ in range(n):
            if z['hp']:
                c = z['hp'].pop(0)
                c['up'] = True
                z['delect'].append(c)
            else:
                s['winner'] = opp['uid'] if opp else None
                _log(room, 'ระบบ', f'{name} ไม่มี HP เหลือ → {opp["name"] if opp else "-"} ชนะ!')
                return None, None
        L(f'HP ลดลง {n} (เหลือ {len(z["hp"])})')
        return None, None
    if t == 'concede':
        s['winner'] = opp['uid'] if opp else None
        L('ยอมแพ้')
        return None, None

    if t == 'unlink':            # ถอด Ship ออกจาก Neurous → Delect Zone หรือมือ
        tgt = next((x for zn in ('attack', 'protect') for x in z[zn] if x['iid'] == d.get('target')), None)
        ln = next((x for x in (tgt['links'] if tgt else []) if x['iid'] == d.get('iid')), None)
        if not ln:
            return 'ไม่พบ Link นี้', None
        to = d.get('to') if d.get('to') in ('hand', 'delect') else 'delect'
        tgt['links'].remove(ln)
        ln['up'] = to != 'hand'
        z[to].append(ln)
        L(f"ถอด Link {_cname(room, ln)} ออกจาก {_cname(room, tgt)} → {Z_TH[to]}")
        return None, None
    iid = d.get('iid')
    fr, i, c = find(me, iid)
    if t == 'link':              # Link: เอา Ship ไปติดกับ Neurous บนสนาม (ได้ไม่เกิน LINK_MAX ใบต่อ Neurous)
        if not c:
            return 'ไม่พบการ์ด', None
        si = room['cards'].get(str(c['cid']), {})
        if si.get('type') != 'ship':
            return 'เฉพาะการ์ด Ship เท่านั้นที่ Link ได้', None
        if fr not in ('hand', 'server', 'partners', 'attack', 'protect'):
            return 'ย้าย Ship มาที่มือหรือสนามก่อน', None
        tgt = next((x for zn in ('attack', 'protect') for x in z[zn] if x['iid'] == d.get('target')), None)
        if not tgt or tgt is c:
            return 'เลือก Neurous บนสนามของคุณเป็นเป้าหมาย Link', None
        if room['cards'].get(str(tgt['cid']), {}).get('type') not in NEUROUS:
            return 'Link ได้เฉพาะกับ Neurous', None
        if len(tgt['links']) >= LINK_MAX:
            return f'Link ได้ไม่เกิน {LINK_MAX} ใบต่อ Neurous', None
        cost = si.get('cost', 0) if d.get('pay') and fr == 'hand' else 0
        if cost > me['code']:
            return f'Code ไม่พอ (ต้องใช้ {cost}, มี {me["code"]})', None
        me['code'] -= cost
        z[fr].pop(i)
        c['up'], c['tap'], c['dmg'] = True, False, 0
        tgt['links'].append(c)
        L(f"Link {si.get('name', '?')} → {_cname(room, tgt)} ({len(tgt['links'])}/{LINK_MAX})" + (f' (จ่าย {cost} Code)' if cost else ''))
        return None, None
    if t in ('tap', 'flip', 'ctr', 'move', 'dmg') and not c:
        return 'ไม่พบการ์ด', None
    if t == 'tap':
        c['tap'] = not c['tap']
        return None, None
    if t == 'flip':
        c['up'] = not c['up']
        return None, None
    if t == 'dmg':
        c['dmg'] = max(0, c['dmg'] + int(d.get('delta', 1)))
        info = room['cards'].get(str(c['cid']), {})
        if fr in ('attack', 'protect') and c['dmg'] > 0 and c['dmg'] >= _eff(room, c)['def']:
            z[fr].remove(c)                       # DEF หมด = ถูกทำลาย ลง Delect Zone
            c['tap'], c['up'], c['dmg'] = False, True, 0
            _drop_links(z, c)
            z['delect'].append(c)
            L(f"{info.get('name', '?')} ถูกทำลาย (ดาเมจถึงค่า DEF)")
        return None, None
    if t == 'ctr':
        c['ctr'] = max(-99, min(99, c['ctr'] + int(d.get('delta', 1))))
        return None, None
    if t == 'move':
        to = d.get('to')
        if to not in ZONES:
            return 'โซนไม่ถูกต้อง', None
        if fr == to and to not in ('deck',):
            return None, None
        if to in LIMITS and fr != to and len(z[to]) >= LIMITS[to]:
            return f'{Z_TH[to]} เต็มแล้ว (สูงสุด {LIMITS[to]})', None
        cost = 0
        info = room['cards'].get(str(c['cid']), {})
        if d.get('pay'):
            if to in ('attack', 'protect') and fr in ('partners', 'hand'):
                cost = info.get('cost', 0)
            elif fr in ('attack', 'protect') and to in ('attack', 'protect'):
                cost = 1
        if cost > me['code']:
            return f'Code ไม่พอ (ต้องใช้ {cost}, มี {me["code"]})', None
        me['code'] -= cost
        z[fr].pop(i)
        if fr in ('attack', 'protect') and to not in ('attack', 'protect'):
            _drop_links(z, c)
        c['tap'] = False
        c['dmg'] = 0
        c['up'] = bool(d['up']) if 'up' in d else (to not in ('deck', 'hand', 'hp'))
        if to == 'deck':
            z['deck'].insert(0, c) if d.get('pos', 'top') == 'top' else z['deck'].append(c)
        else:
            z[to].append(c)
        shown = c['up'] and to not in ('hand', 'deck', 'hp')
        who = _cname(room, c) if shown else 'การ์ด 1 ใบ'
        L(f'ย้าย {who}: {Z_TH[fr]} → {Z_TH[to]}' + (f' (จ่าย {cost} Code)' if cost else ''))
        return None, None
    return 'คำสั่งไม่ถูกต้อง', None
