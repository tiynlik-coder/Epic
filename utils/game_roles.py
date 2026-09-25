"""Role distribution for a new game."""

import random

from config import MAFIA, ROLES, SOLO, TOWN
from models.admin_data import active_roles_for, forced_role
from models.database import db


# Role balance: no new role types. At 30 players all 30 role types appear once.
# For smaller lobbies, use a deterministic faction-balanced subset; above 30 repeat roles.
def role_balance(n):
    mafia = max(1, min(8, round(n*0.27)))
    town = max(2, round(n*0.43))
    solo = n-mafia-town
    if solo<0: solo=0; town=n-mafia
    # Guarantee the main information role at normal sizes.
    town_roles=["Komissar Katani","Shifokor","Daydi","Kezuvchi","Serjant","Koldun","Sotqin","Folbin","Zodagon","Tinch axoli","Kamikaze"]
    mafia_roles=["Don","Mafia","Advokat","Ayg‘oqchi","Labarant","Manipulyator","Ruhoniy","Undiruvchi"]
    solo_roles=[r for r in ROLES if r not in TOWN and r not in MAFIA]
    out=[]
    if n>=4:
        # Main role guarantees without exceeding faction targets.
        if town>=1: out.append("Komissar Katani")
        if town>=2: out.append("Shifokor")
        while sum(1 for r in out if r in TOWN)<town:
            pool=[r for r in town_roles if r not in out]
            if not pool: pool=["Tinch axoli"]
            out.append(random.choice(pool))
    out += random.sample(mafia_roles, min(mafia,len(mafia_roles)))
    while sum(1 for r in out if r in MAFIA)<mafia: out.append(random.choice(mafia_roles))
    out += random.sample(solo_roles, min(solo,len(solo_roles)))
    while sum(1 for r in out if r in SOLO):
        if len(out)>=n: break
        out.append(random.choice(solo_roles))
    while len(out)<n:
        out.append("Tinch axoli")
    random.shuffle(out)
    return out[:n]


def apply_admin_roles(g, role_list):
    """Assignment order: admin-forced roles first, then purchased active roles, then remaining roles."""
    players=list(g.get("players",{}).values())
    assigned={}
    used_role_indices=set()
    used_active_ids=[]

    # 1) Forced admin roles always win over the random pool.
    for p in players:
        r=forced_role(p["id"])
        if not r: continue
        assigned[p["id"]]=r
        # Consume one matching random slot if available; otherwise replace a later slot.
        try:
            idx=next(i for i,x in enumerate(role_list) if i not in used_role_indices and x==r)
            used_role_indices.add(idx)
        except StopIteration:
            pass

    # 2) Purchased active roles: use the first active role whose role exists in the pool.
    # Do not apply to a player that already has an admin-forced role.
    remaining_indices=[i for i in range(len(role_list)) if i not in used_role_indices]
    for p in players:
        if p["id"] in assigned: continue
        ars=active_roles_for(p["id"])
        chosen=None
        chosen_idx=None
        for ar in ars:
            for idx in remaining_indices:
                if role_list[idx]==ar[1]:
                    chosen=(ar[1],ar[0]); chosen_idx=idx; break
            if chosen: break
        if chosen:
            assigned[p["id"]]=chosen[0]
            used_role_indices.add(chosen_idx)
            remaining_indices.remove(chosen_idx)
            used_active_ids.append(chosen[1])

    # 3) Fill unassigned players with all remaining roles in stable shuffled order.
    remaining_roles=[r for i,r in enumerate(role_list) if i not in used_role_indices]
    random.shuffle(remaining_roles)
    for p in players:
        if p["id"] not in assigned and remaining_roles:
            assigned[p["id"]]=remaining_roles.pop(0)

    # If forced roles replaced slots, make sure every player still gets a role.
    while remaining_roles and len(assigned)<len(players):
        for p in players:
            if p["id"] not in assigned:
                assigned[p["id"]]=remaining_roles.pop(0); break
    while len(assigned)<len(players):
        for p in players:
            if p["id"] not in assigned:
                assigned[p["id"]]="Tinch axoli"; break

    if used_active_ids:
        con=db(); con.executemany("UPDATE admin_active_roles SET is_active=0 WHERE id=?",[(int(x),) for x in used_active_ids]); con.commit(); con.close()
    return [assigned[p["id"]] for p in players]
