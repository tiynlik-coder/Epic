"""Win conditions."""

from config import CONDITIONAL_SOLO, HOSTILE_SOLO, MAFIA, SOLO, SURVIVAL_SOLO, TOWN
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


def real_mode_result(ps):
    """Real role set (Baku): a side wins only when it is the only one left; no mixed wins.
    With two players left: Don beats anyone but the Komissar, the Komissar anyone but the Don,
    and a Qotil wins. Returns the winners, or None while the game goes on."""
    if not ps: return []
    for side in (TOWN, MAFIA, SOLO):
        if all(p["role"] in side for p in ps): return list(ps)
    if len(ps)==2:
        a,b=ps
        for x,y in ((a,b),(b,a)):
            if x["role"]=="Don" and y["role"]!="Komissar Katani": return [x]
            if x["role"]=="Komissar Katani" and y["role"]!="Don": return [x]
        killers=[p for p in ps if p["role"]=="Qotil"]
        if killers: return killers
    return None


def last_pair(g, ps):
    """Para mode: the survivors are one registered pair (or what is left of it)."""
    if not ps or len(ps)>2: return None
    ids={p["id"] for p in ps}
    for a,b in g.get("pairs") or []:
        if ids<= {a,b}: return list(ps)
    return None


def is_real(g):
    return g.get("roleset")=="real" and g.get("mode") not in {"vs","zombie","uniform"}


def winners(g):
    ps=living(g)
    if g.get("mode")=="para" and last_pair(g,ps): return last_pair(g,ps)
    if is_real(g): return real_mode_result(ps) or []
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
    # Kamikaze and the conditional solos win (even dead) once their goal was met during the game.
    result += [p for p in g["players"].values() if (p["role"]=="Kamikaze" and p.get("kamikaze_used")) or (p["role"] in CONDITIONAL_SOLO and p.get("won_flag"))]
    uniq=[]; seen=set()
    for p in result:
        if p["id"] not in seen: uniq.append(p); seen.add(p["id"])
    return uniq


def game_over(g):
    ps=living(g)
    if not ps: return True
    if g.get("mode") == "uniform":
        return len(ps) <= 1
    if g.get("mode") == "para" and last_pair(g,ps): return True
    if is_real(g): return real_mode_result(ps) is not None
    if g.get("mode") == "vs":
        teams={p.get("team") for p in ps if p.get("team")}
        return len(teams) <= 1
    if g.get("mode") == "zombie":
        zombies=[p for p in ps if p.get("role")=="Zombi"]
        humans=[p for p in ps if p.get("role")!="Zombi"]
        return not zombies or not humans
    # Over once at most one of Town / Mafia / hostile solos is left standing.
    return sum(1 for grp in faction_groups(ps) if grp) <= 1
