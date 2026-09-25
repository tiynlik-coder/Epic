"""Win conditions."""

from config import HOSTILE_SOLO, MAFIA, SURVIVAL_SOLO, TOWN
from utils.players import living


def faction_groups(ps):
    m=[p for p in ps if p["role"] in MAFIA]
    t=[p for p in ps if p["role"] in TOWN]
    h=[p for p in ps if p["role"] in HOSTILE_SOLO]
    return m,t,h


def zombie_mode_winner(players):
    alive=[p for p in players if p.get("alive")]
    z=sum(p.get("role")=="Zombi" for p in alive)
    h=len(alive)-z
    if z==0 or h==0:
        return [p for p in alive if (p.get("role")=="Zombi")== (z>0)]
    return []


def winners(g):
    ps=living(g)
    if g.get("mode") == "vs" and ps:
        teams={p.get("team") for p in ps if p.get("team")}
        if len(teams) == 1:
            winning_team=next(iter(teams))
            return [p for p in ps if p.get("team") == winning_team]
    if g.get("mode") == "zombie":
        return zombie_mode_winner(g["players"].values())
    # Suidsid only wins by hanging; handled in resolve_vote.
    m,t,h=faction_groups(ps)
    result=[]
    if not m and not h: result += t
    elif not t and not h: result += m
    elif not t and not m: result += h
    # Survival solos win just by being alive at the end.
    result += [p for p in ps if p["role"] in SURVIVAL_SOLO]
    # Kamikaze also wins on its own (even dead) once its retaliation took its killers down.
    result += [p for p in g["players"].values() if p["role"]=="Kamikaze" and p.get("kamikaze_used")]
    uniq=[]; seen=set()
    for p in result:
        if p["id"] not in seen: uniq.append(p); seen.add(p["id"])
    return uniq


def game_over(g):
    ps=living(g)
    if not ps: return True
    if g.get("mode") == "uniform":
        return len(ps) <= 1
    if g.get("mode") == "vs":
        teams={p.get("team") for p in ps if p.get("team")}
        return len(teams) <= 1
    if g.get("mode") == "zombie":
        zombies=[p for p in ps if p.get("role")=="Zombi"]
        humans=[p for p in ps if p.get("role")!="Zombi"]
        return not zombies or not humans
    # Over once at most one of Town / Mafia / hostile solos is left standing.
    return sum(1 for grp in faction_groups(ps) if grp) <= 1
